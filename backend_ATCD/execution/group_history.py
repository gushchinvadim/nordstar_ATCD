"""Read-only group history and deletion rules shared with Django Admin."""
import json
from django.db.models import Q
from django.contrib.admin.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from .models import Group, Enrollment, Assessment, Certificate, ScheduleItem, ComplianceLog, IndividualStudyPlan
from .local_time import local_datetime


def group_signatures(group):
    return ComplianceLog.objects.filter(Q(group=group) | Q(enrollment__group=group) |
        Q(schedule_item__group=group) | Q(assessment__enrollment__group=group) |
        Q(certificate__enrollment__group=group)).distinct()


def training_delete_blockers(group):
    reasons = []
    if Assessment.objects.filter(enrollment__group=group).exists():
        reasons.append('Сохранены оценки или замечания по обучению.')
    if group_signatures(group).exists():
        reasons.append('Сохранены ПЭП и подтверждения участников.')
    if Certificate.objects.filter(enrollment__group=group).exists():
        reasons.append('Сохранены документы об обучении.')
    if ScheduleItem.objects.filter(group=group).filter(Q(is_completed=True) | Q(status__in=['in_progress', 'completed'])).exists():
        reasons.append('Есть начатые или проведённые занятия.')
    if Enrollment.objects.filter(group=group).filter(Q(completed_at__isnull=False) |
        Q(dismissal_date__isnull=False) | Q(order_out_date__isnull=False) | ~Q(order_out_number='') | ~Q(final_result='') | Q(total_hours_completed__gt=0) |
        Q(status__in=['completed', 'failed', 'partial'])).exists():
        reasons.append('Зафиксированы результаты или завершение обучения слушателей.')
    if IndividualStudyPlan.objects.filter(group=group).exclude(status='draft').exists():
        reasons.append('Есть действующие или завершённые индивидуальные планы.')
    return reasons


def group_delete_reasons(group):
    reasons = training_delete_blockers(group)
    if group.status not in ('draft', 'enrolling', 'cancelled') and not group.was_cancelled:
        reasons.insert(0, 'Удалять можно только ошибочную заявку до обучения или отменённую заявку без истории обучения.')
    return reasons


def group_history(group):
    enrollments = list(Enrollment.objects.filter(group=group).select_related('student').order_by('number_in_group'))
    assessments = Assessment.objects.filter(enrollment__group=group).select_related('section', 'instructor').order_by('pk')
    signatures = group_signatures(group).select_related('staff', 'student', 'group__location',
        'enrollment__group__location', 'schedule_item__group__location',
        'assessment__enrollment__group__location', 'certificate__enrollment__group__location').order_by('timestamp', 'pk')
    events = []
    for log in LogEntry.objects.filter(content_type=ContentType.objects.get_for_model(Group),
        object_id=str(group.pk)).select_related('user').order_by('action_time', 'pk'):
        try:
            details = json.loads(log.change_message)
        except (ValueError, TypeError):
            details = log.change_message
        events.append({'id': log.pk, 'at': local_datetime(log.action_time, group).isoformat(),
            'author': log.user.get_full_name() or log.user.username, 'details': details})
    return {
        'students': [{'id': row.pk, 'number': row.number_in_group, 'name': str(row.student).strip(),
            'status': row.get_status_display()} for row in enrollments],
        'assessments': [{'id': row.pk, 'enrollment_id': row.enrollment_id, 'section': row.section.title,
            'score': row.score, 'passed': row.passed, 'date': row.assessment_date, 'notes': row.notes,
            'instructor': row.instructor.full_name if row.instructor else None} for row in assessments],
        'signatures': [{'id': log.pk, 'action': log.get_action_type_display(),
            'signature': log.signature_string} for log in signatures],
        'schedule': list(ScheduleItem.objects.filter(group=group).order_by('date', 'start_time').values(
            'id', 'date', 'start_time', 'end_time', 'section__title', 'status', 'is_completed')),
        'certificates': list(Certificate.objects.filter(enrollment__group=group).values('id', 'number', 'issue_date')),
        'events': events,
    }
