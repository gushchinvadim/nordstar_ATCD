"""Read-only, narrowly scoped server-to-server export. No browser credentials."""
import secrets
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from django.conf import settings
from django.db.models import Q
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from .models import ScheduleItem, Enrollment


class IntegrationKey(BasePermission):
    def has_permission(self, request, view):
        expected = getattr(settings, 'SIM_TRAINING_EXPORT_KEY', '')
        provided = request.headers.get('X-SIM-Integration-Key', '')
        return bool(len(expected) >= 32 and provided and secrets.compare_digest(expected, provided))


def wall_time(day, clock, name):
    zone = ZoneInfo(name)
    naive = datetime.combine(day, clock)
    candidates = {naive.replace(tzinfo=zone, fold=f).astimezone(timezone.utc)
                  for f in (0, 1)
                  if naive.replace(tzinfo=zone, fold=f).astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) == naive}
    if len(candidates) != 1:
        raise ValueError('Время попадает в переход часового пояса. Уточните расписание.')
    return next(iter(candidates)).isoformat()


def export_row(row):
    group = row.group
    students = list(Enrollment.objects.filter(group=group).exclude(status__in=['dismissed', 'absent', 'academic_leave'])
                    .select_related('student').order_by('number_in_group', 'pk'))
    location = row.classroom.location if row.classroom_id else group.location
    name = location.timezone if location else ''
    errors = []
    if len(students) not in (1, 2): errors.append('Для сессии нужен один или два слушателя; уточните состав группы.')
    if not row.instructor_id: errors.append('Не назначен инструктор.')
    if not row.classroom_id: errors.append('Не назначен тренажёр.')
    if not name: errors.append('Не указан часовой пояс места проведения.')
    if not row.subsection_id: errors.append('Не указан подраздел с названием тренажёрной сессии.')
    start = end = None
    if row.start_time is None or row.end_time is None:
        errors.append('Укажите начало и окончание сессии.')
    elif name:
        try:
            end_day = row.date + timedelta(days=int(row.end_time < row.start_time))
            start, end = wall_time(row.date, row.start_time, name), wall_time(end_day, row.end_time, name)
            if end <= start: errors.append('Окончание должно быть позже начала.')
        except (ValueError, KeyError) as error:
            errors.append(str(error))
    return {
        'id': row.pk, 'group_id': group.pk, 'group': group.assigned_number,
        'module_id': group.module_id, 'module': group.module.code,
        'template_key': f'{group.module_id}:{row.section_id}:{row.subsection_id or 0}',
        'title': row.subsection.title if row.subsection_id else row.section.title,
        'starts_at': start, 'ends_at': end, 'timezone': name,
        'venue': str(row.classroom) if row.classroom_id else '',
        'status': 'cancelled' if group.was_cancelled or row.status == 'cancelled' else 'planned',
        'instructor': {'id': row.instructor_id, 'name': row.instructor.full_name if row.instructor_id else ''},
        'pilots': [{'id': e.student_id, 'name': str(e.student)} for e in students],
        'errors': errors,
    }


@api_view(['GET'])
@authentication_classes([])
@permission_classes([IntegrationKey])
def sim_schedule(request):
    try:
        start, end = (date.fromisoformat(request.query_params.get(key, '')) for key in ('from', 'to'))
        if not 0 <= (end - start).days <= 92: raise ValueError()
    except (ValueError, TypeError):
        return Response({'detail': 'Укажите from/to: YYYY-MM-DD, период не более 93 дней.'}, status=400)
    codes = getattr(settings, 'SIM_TRAINING_COURSE_CODES', ['ППП.АУЦ.11'])
    # Only live groups are candidates for new simulator assignments.
    rows = ScheduleItem.objects.filter(
        date__range=(start, end), group__status__in=('enrolling', 'in_progress'),
    ).filter(
        Q(session_type='sim') | Q(section__detail='sim') | Q(subsection__detail='sim')
    ).filter(Q(group__module__course__company_code__in=codes) | Q(group__module__course__prog_id__in=codes))
    rows = rows.select_related('group__module', 'group__location', 'classroom__location', 'subsection', 'section', 'instructor').order_by('pk')
    if rows.count() > 1000:
        return Response({'detail': 'Слишком много занятий, сократите период.'}, status=400)
    response = Response({'schema': 1, 'source': 'nordstar-atcd', 'rows': [export_row(row) for row in rows]})
    response['Cache-Control'] = 'no-store'
    return response
