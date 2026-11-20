from execution.local_time import group_today, schedule_start_datetime
from execution.group_lifecycle import group_write_guard
# docs/api_views.py
import os
import re
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from django.db.models import Q, Count, Exists, OuterRef
from django.utils import timezone
from datetime import datetime, date
from core.services.schedule_generator import generate_schedule_for_group
from docs.serializers import ScheduleItemUpdateSerializer
from docs.services.document_registry import DocumentRegistry
from docs.services.document_storage import DocumentStorageService
from execution.models import Group, Enrollment, ScheduleItem, Assessment, ComplianceLog
from people.models import Staff, Student
from references.models import Location, Classroom
from reporting.services.frdo_export import FRDOExportService
from reporting.services.rauc_export import RAUCExportService
from training.models import Course, Module, Section
from rest_framework import status
from django.conf import settings
from django.urls import reverse


def can_manage_group(user, group=None):
    staff = getattr(user, 'staff', None)
    if staff is not None and not staff.is_active:
        return False
    return (
        user.is_staff
        or (staff is not None and (
            staff.fptitle
            or (group is not None and staff.pk in (group.curator_id, group.director_id))
        ))
    )


def get_schedule_group(user, **lookup):
    group = get_object_or_404(Group, **lookup)
    if not can_manage_group(user, group):
        raise PermissionDenied()
    return group


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def groups_list(request):
    """API для получения списка групп с фильтрацией и пагинацией."""
    issuance_logs = ComplianceLog.objects.filter(
        enrollment_id=OuterRef('pk'),
        staff_id=OuterRef('group__curator_id'),
        action_type='methodist_documents_issued',
    )
    unsigned_enrollments = Enrollment.objects.filter(
        group_id=OuterRef('pk'), status='completed',
    ).exclude(Exists(issuance_logs))
    queryset = Group.objects.select_related(
        'module', 'module__course', 'mentor', 'curator'
    ).annotate(students_count=Count('enrollment'), has_unsigned_documents=Exists(unsigned_enrollments))

    status_param = request.query_params.get('status', 'in_progress,completed')
    if status_param:
        statuses = [s.strip() for s in status_param.split(',')]
        queryset = queryset.filter(status__in=statuses)

    direction = request.query_params.get('direction')
    if direction and direction != 'all':
        queryset = queryset.filter(module__course__frdo_template_type=direction)

    year = request.query_params.get('year')
    if year:
        try:
            queryset = queryset.filter(start_date__year=int(year))
        except ValueError:
            pass

    curator_id = request.query_params.get('curator')
    if curator_id and curator_id != 'all':
        queryset = queryset.filter(curator_id=curator_id)

    search = request.query_params.get('search')
    if search:
        queryset = queryset.filter(
            Q(assigned_number__icontains=search) |
            Q(module__title__icontains=search) |
            Q(module__code__icontains=search)
        )

    queryset = queryset.order_by('-assigned_at')

    try:
        page = int(request.query_params.get('page', 1))
    except ValueError:
        page = 1

    try:
        page_size = int(request.query_params.get('page_size', 15))
    except ValueError:
        page_size = 15

    page_size = min(page_size, 50)
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    groups = queryset[start:end]

    data = []
    for group in groups:
        data.append({
            'id': group.id,
            'assigned_number': group.assigned_number,
            'module_code': group.module.code if group.module else '',
            'module_title': group.module.title if group.module else '',
            'direction': group.module.course.frdo_template_type if group.module and group.module.course else '',
            'direction_display': group.module.course.get_frdo_template_type_display() if group.module and group.module.course else '',
            'start_date': group.start_date.strftime('%d.%m.%Y') if group.start_date else None,
            'end_date': group.end_date.strftime('%d.%m.%Y') if group.end_date else None,
            'status': group.status,
            'status_display': group.get_status_display(),
            'cancellation_date': group.cancellation_date,
            'cancellation_reason': group.cancellation_reason,
            'students_count': group.students_count,
            'has_unsigned_documents': group.has_unsigned_documents,
            'curator': group.curator.full_name if group.curator else None,
            'mentor': group.mentor.full_name if group.mentor else None,
        })

    return Response({
        'count': total,
        'page': page,
        'page_size': page_size,
        'total_pages': (total + page_size - 1) // page_size,
        'results': data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def directions_list(request):
    """API для получения списка направлений."""
    return Response(sorted(
        [{'code': code, 'title': title} for code, title in Course.FRDO_TEMPLATE_CHOICES],
        key=lambda item: item['title'],
    ))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_detail(request, group_id):
    """API для получения детальной информации о группе."""
    try:
        group = Group.objects.select_related('module', 'module__course', 'mentor', 'curator', 'location').get(
            id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    enrollments = Enrollment.objects.filter(group=group)
    students_by_status = enrollments.values('status').annotate(count=Count('id'))

    return Response({
        'id': group.id,
        'assigned_number': group.assigned_number,
        'module': {
            'code': group.module.code if group.module else '',
            'title': group.module.title if group.module else '',
            'direction': group.module.course.frdo_template_type if group.module and group.module.course else '',
            'direction_display': group.module.course.get_frdo_template_type_display() if group.module and group.module.course else '',
        },
        'start_date': group.start_date.strftime('%d.%m.%Y') if group.start_date else None,
        'start_face_to_face': group.start_face_to_face.strftime('%d.%m.%Y') if group.start_face_to_face else None,
        'end_date': group.end_date.strftime('%d.%m.%Y') if group.end_date else None,
        'status': group.status,
        'status_display': group.get_status_display(),
            'cancellation_date': group.cancellation_date,
            'cancellation_reason': group.cancellation_reason,
        'location': group.location.full_name if group.location else None,
        'mentor': group.mentor.full_name if group.mentor else None,
        'curator': group.curator.full_name if group.curator else None,
        'director': group.director.full_name if group.director else None,
        'students_count': enrollments.count(),
        'students_by_status': {item['status']: item['count'] for item in students_by_status},
        'is_sdo': group.is_sdo,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user_info(request):
    user = request.user
    is_student = hasattr(user, 'student')
    full_name = user.username
    fptitle = False
    has_lessons = False
    is_director = False

    if hasattr(user, 'staff') and user.staff:
        full_name = user.staff.full_name
        fptitle = getattr(user.staff, 'fptitle', False)
        has_lessons = ScheduleItem.objects.filter(instructor=user.staff).exists()
        is_director = getattr(user.staff, 'tptitle', False)

    return Response({
        'username': user.username,
        'full_name': full_name,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'fptitle': fptitle,
        'has_lessons': has_lessons,
        'is_student': is_student,
        'is_director': is_director,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def modules_list(request):
    modules = Module.objects.select_related('course').all().order_by('code')
    return Response([{
        'id': module.id,
        'code': module.code,
        'title': module.title,
        'course_title': module.course.title if module.course else '',
    } for module in modules])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_roles(request):
    user = request.user
    full_name = user.username
    fptitle = False
    tptitle = False
    has_lessons = False
    is_student = hasattr(user, 'student') and user.student is not None
    is_director = False
    is_instructor = False

    if hasattr(user, 'staff') and user.staff:
        staff = user.staff
        full_name = staff.full_name
        fptitle = getattr(staff, 'fptitle', False)
        tptitle = getattr(staff, 'tptitle', False)
        has_lessons = ScheduleItem.objects.filter(instructor=staff).exists()
        is_director = tptitle
        position_name = staff.position.name.lower() if staff.position else ''
        is_instructor_by_position = any(word in position_name for word in ['преподаватель', 'инструктор', 'учитель'])
        if staff.is_instructor or has_lessons or is_instructor_by_position:
            is_instructor = True

    available_roles = []
    if is_director: available_roles.append('director')
    if fptitle: available_roles.append('methodist')
    if is_instructor: available_roles.append('instructor')
    if is_student: available_roles.append('student')
    if not available_roles and (user.is_superuser or user.is_staff):
        available_roles.append('methodist')

    return Response({
        'username': user.username,
        'full_name': full_name,
        'available_roles': available_roles,
        'roles': {
            'is_director': is_director,
            'is_methodist': fptitle,
            'is_instructor': is_instructor,
            'is_student': is_student,
            'is_staff': user.is_staff,
            'is_superuser': user.is_superuser
        },
        'fptitle': fptitle,
        'tptitle': tptitle,
        'has_lessons': has_lessons,
        'is_student': is_student,
        'is_director': is_director,
        'is_first_login': user.last_login is None
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staff_list(request):
    staff = Staff.objects.filter(is_active=True).order_by('full_name')
    return Response(
        [{'id': s.id, 'full_name': s.full_name, 'position': s.position.name if s.position else ''} for s in staff])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def students_list(request):
    students = Student.objects.filter(is_active=True).order_by('surname', 'name')
    return Response([{'id': s.id, 'full_name': f"{s.surname} {s.name} {s.patronymic}".strip(),
                      'profession': s.profession.name if s.profession else ''} for s in students])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def locations_list(request):
    locations = Location.objects.all().order_by('name')
    return Response([{'id': loc.id, 'title': f"{loc.name} - {loc.full_name}" if loc.full_name else loc.name,
                      'code': loc.name, 'full_name': loc.full_name or ''} for loc in locations])


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group(request):
    if request.data.get("status") == "cancelled":
        return Response({"error": "Создайте группу, затем отмените с причиной и датой."}, status=400)
    if not can_manage_group(request.user):
        raise PermissionDenied()
    data = request.data
    try:
        serial_number = data.get('serial_number', '')
        application = data.get('application', '')
        assigned_number = f"{serial_number}-{application}" if serial_number and application else ''
        order_in_date = data.get('order_in_date')
        order_in_number = f"{assigned_number}-З" if assigned_number else ''

        with transaction.atomic():
            group = Group.objects.create(
                serial_number=serial_number,
                application=application,
                assigned_number=assigned_number,
                module_id=data.get('module_id'),
                status=data.get('status', 'enrolling'),
                location_id=data.get('location_id') if data.get('location_id') else None,
                start_date=data.get('start_date'),
                start_face_to_face=data.get('start_face_to_face') if data.get('start_face_to_face') else None,
                end_date=data.get('end_date') if data.get('end_date') else None,
                is_sdo=data.get('is_sdo', False),
                start_time_default=data.get('start_time_default', '09:00:00'),
                mentor_id=data.get('mentor_id') if data.get('mentor_id') else None,
                curator_id=data.get('curator_id') if data.get('curator_id') else None,
                director_id=data.get('director_id') if data.get('director_id') else None,
                order_in_number=order_in_number,
                order_in_date=order_in_date,
                assigned_by=request.user.staff if hasattr(request.user, 'staff') else None,
                assigned_at=timezone.now(),
            )

            from execution.funding import funding_values, FundingData, IsMethodist
            defaults = FundingData(data=data.get('funding_defaults', {})); defaults.is_valid(raise_exception=True)
            for enrollment_data in data.get('enrollments', []):
                finance = funding_values({**defaults.validated_data, **{key: enrollment_data[key] for key in ('funding_source', 'payer_organization', 'funding_reference') if key in enrollment_data}})
                if (finance['funding_source'] != 'unspecified' or finance['funding_reference']) and not IsMethodist().has_permission(request, None):
                    raise PermissionDenied('Финансирование заполняет методист.')
                Enrollment.objects.create(
                    group=group,
                    student_id=enrollment_data.get('student_id'),
                    number_in_group=enrollment_data.get('number_in_group'),
                    status=enrollment_data.get('status', 'enrolled'),
                    **finance,
                )

        return Response({'success': True, 'group_id': group.id, 'assigned_number': group.assigned_number,
                         'message': f'Группа {group.assigned_number} успешно создана'}, status=201)
    except PermissionDenied:
        raise
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_detail_edit(request, group_id):
    try:
        group = Group.objects.select_related('module', 'module__course', 'location', 'mentor', 'curator',
                                             'director').get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    enrollments_qs = Enrollment.objects.select_related('student', 'student__profession').filter(group=group).order_by(
        'number_in_group')
    enrollments_data = [{
        'id': e.id, 'student_id': e.student.id,
        'student_name': f"{e.student.surname} {e.student.name} {e.student.patronymic}".strip(),
        'profession': e.student.profession.name if e.student.profession else '',
        'number_in_group': e.number_in_group, 'status': e.status,
        'funding_source': e.funding_source, 'payer_organization': e.payer_organization_id,
        'funding_reference': e.funding_reference,
    } for e in enrollments_qs]

    def safe_date(d):
        return d.strftime('%Y-%m-%d') if d else ''

    def safe_time(t):
        return str(t)[:5] if t else '09:00'

    return Response({
        'id': group.id, 'serial_number': group.serial_number or '', 'application': group.application or '',
        'assigned_number': group.assigned_number or '', 'module_id': group.module.id if group.module else None,
        'status': group.status, 'location_id': group.location.id if group.location else None,
        'start_date': safe_date(group.start_date), 'start_face_to_face': safe_date(group.start_face_to_face),
        'end_date': safe_date(group.end_date), 'is_sdo': group.is_sdo,
        'start_time_default': safe_time(group.start_time_default),
        'mentor_id': group.mentor.id if group.mentor else None,
        'curator_id': group.curator.id if group.curator else None,
        'director_id': group.director.id if group.director else None, 'order_in_date': safe_date(group.order_in_date),
        'enrollments': enrollments_data,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@group_write_guard
def update_group(request, group_id):
    """Обновление данных группы"""
    try:
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=404)

    if not can_manage_group(request.user, group):
        raise PermissionDenied()

    data = request.data
    if data.get('status') == 'cancelled':
        return Response({'error': 'Используйте «Отменить группу» с причиной и датой.'}, status=400)

    # 1. Простые текстовые поля и ID
    if 'serial_number' in data: group.serial_number = data['serial_number']
    if 'application' in data: group.application = data['application']
    if 'module_id' in data: group.module_id = data['module_id']
    if 'status' in data: group.status = data['status']

    # 2. Поля, которые могут быть пустыми (None)
    if 'location_id' in data: group.location_id = data['location_id'] or None
    if 'start_face_to_face' in data: group.start_face_to_face = data['start_face_to_face'] or None
    if 'end_date' in data: group.end_date = data['end_date'] or None
    if 'mentor_id' in data: group.mentor_id = data['mentor_id'] or None
    if 'curator_id' in data: group.curator_id = data['curator_id'] or None
    if 'director_id' in data: group.director_id = data['director_id'] or None
    if 'order_in_date' in data: group.order_in_date = data['order_in_date'] or None

    # 3. 🔥 КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ ДЛЯ BOOLEAN (is_sdo)
    # Мы явно преобразуем значение в bool, чтобы избежать превращения False в None
    if 'is_sdo' in data:
        group.is_sdo = bool(data['is_sdo'])

    # 4. Обязательные даты и время
    if 'start_date' in data: group.start_date = data['start_date']
    if 'start_time_default' in data: group.start_time_default = data['start_time_default']

    # Автоматическое обновление номера группы и приказа при изменении составляющих
    if group.serial_number and group.application:
        group.assigned_number = f"{group.serial_number}-{group.application}"
        if group.order_in_date:
            group.order_in_number = f"{group.assigned_number}-З"

    group.save()

    # Preserve enrollment IDs and all their grades, signatures and financing.
    if 'enrollments' in data:
        from execution.funding import sync_group_enrollments
        reason = data.get('funding_reason', '')
        if not isinstance(reason, str) or len(reason) > 2000:
            from rest_framework.exceptions import ValidationError
            raise ValidationError('Некорректная причина изменения финансирования.')
        sync_group_enrollments(group, data['enrollments'], request.user, reason)

    return Response({
        'success': True,
        'message': f'Группа {group.assigned_number} успешно обновлена',
        'group_id': group.id
    })

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def generate_group_schedule(request, group_id):
    group = get_schedule_group(request.user, id=group_id)
    try:
        created_count = generate_schedule_for_group(group)
        return Response(
            {'success': True, 'message': f'Расписание успешно сгенерировано. Создано занятий: {created_count}'})
    except Exception as e:
        return Response({'success': False, 'error': f'Ошибка генерации: {str(e)}'}, status=500)


@api_view(['GET'])
@permission_classes([AllowAny])
def get_help_content(request):
    return Response([
        {"id": 1, "title": "1. Наполнение системы исходными данными",
         "content": "<p>Администратор программы загружает данные из Excel или вручную на страницах: слушатели, сотрудники, программы обучения, аудитории/тренажеры.</p>"},
        {"id": 2, "title": "2. Выдача допусков для работы персонала",
         "content": "<p>Администратор создает пользователей Django для сотрудников и слушателей.</p>"},
        {"id": 3, "title": "3. Как работает приложение методиста",
         "content": "<p>Методист создает группу, генерирует каркас расписания и редактирует его.</p>"},
        {"id": 8, "title": "8. Закрытие и сохранение документов",
         "content": "<p>После завершения группы преподавателем, методист нажимает «Завершить всех сдавших» и сохраняет документы.</p>"}
    ])


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def group_grades_api(request, group_id):
    group = get_object_or_404(Group, id=group_id)

    if request.method == 'GET':
        # 🔥 ИСПРАВЛЕНИЕ: Убрали 'dismissed' из списка. Отчисленные больше не придут на фронтенд
        students = Enrollment.objects.filter(
            group=group,
            status__in=['enrolled', 'in_progress', 'completed']
        ).select_related('student').order_by('number_in_group')

        sections = Section.objects.filter(stage__module=group.module, grade_type__in=['numeric', 'binary']).order_by(
            'stage__order', 'order')
        instructors = Staff.objects.filter(scheduleitem__group=group).distinct().order_by('full_name')
        schedule_dates = {item['section_id']: item['date'] for item in
                          ScheduleItem.objects.filter(group=group, section__in=sections).values('section_id', 'date')}

        students_data = []
        for enrollment in students:
            assessments_dict = {a.section_id: a for a in
                                enrollment.assessments.filter(attempt_number=1).select_related('instructor')}
            assessments_list = []
            for section in sections:
                assessment = assessments_dict.get(section.id)
                instructor = assessment.instructor if assessment else None
                if not instructor:
                    si = ScheduleItem.objects.filter(group=group, section=section).select_related('instructor').first()
                    if si and si.instructor: instructor = si.instructor

                assessments_list.append({
                    'section_id': section.id, 'section_title': section.title, 'grade_type': section.grade_type,
                    'score': int(assessment.score) if assessment and assessment.score is not None else None,
                    'date': assessment.assessment_date.isoformat() if assessment and assessment.assessment_date else (
                        schedule_dates.get(section.id).isoformat() if schedule_dates.get(section.id) else None),
                    'instructor_id': instructor.id if instructor else None,
                })
            students_data.append({
                'enrollment_id': enrollment.id, 'number_in_group': enrollment.number_in_group,
                'student_name': f"{enrollment.student.surname} {enrollment.student.name} {enrollment.student.patronymic or ''}".strip(),
                'status': enrollment.status, 'status_display': enrollment.get_status_display(),
                'assessments': assessments_list
            })

        return Response({
            'group_info': {'id': group.id, 'assigned_number': group.assigned_number, 'module_code': group.module.code,
                           'module_title': group.module.title, 'status': group.status},
            'instructors': [{'id': inst.id, 'name': inst.full_name} for inst in instructors],
            'students': students_data
        })


    if request.method == 'POST':
        updates = request.data.get('updates', [])
        saved_count = 0
        errors = []
        schedule_dates_cache = {}

        for update in updates:
            enrollment_id, section_id, score, date_str, instructor_id = update.get('enrollment_id'), update.get(
                'section_id'), update.get('score'), update.get('date'), update.get('instructor_id')
            if score is None or score == '': continue

            enrollment = Enrollment.objects.get(id=enrollment_id)
            section = Section.objects.get(id=section_id)

            cache_key = f"schedule_{group.id}_{section.id}"
            if cache_key not in schedule_dates_cache:
                schedule_dates_cache[cache_key] = ScheduleItem.objects.filter(group=group, section=section).first()

            schedule_item = schedule_dates_cache[cache_key]
            if schedule_item and schedule_item.date:
                schedule_dt = schedule_start_datetime(schedule_item)
                if schedule_dt > timezone.now():
                    errors.append(f'Нельзя выставить оценку по "{section.title}". Время занятия еще не наступило.')
                    continue

            assessment_date = None
            if date_str:
                try:
                    assessment_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    pass
            if not assessment_date:
                assessment_date = schedule_item.date if schedule_item and schedule_item.date else group_today(group)

            instructor = Staff.objects.get(id=instructor_id) if instructor_id else None
            if not instructor and schedule_item: instructor = schedule_item.instructor

            assessment, created = Assessment.objects.get_or_create(
                enrollment=enrollment, section=section, attempt_number=1,
                defaults={'score': score, 'assessment_type': 'test', 'assessment_date': assessment_date,
                          'instructor': instructor}
            )
            if not created:
                assessment.score, assessment.assessment_date, assessment.instructor = score, assessment_date, instructor
                assessment.save()
            saved_count += 1

            if request.user.is_authenticated and hasattr(request.user, 'staff'):
                if not ComplianceLog.objects.filter(enrollment=enrollment, staff=request.user.staff,
                                                    action_type='grades_submitted', assessment=assessment).exists():
                    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
                    ComplianceLog.objects.create(enrollment=enrollment, staff=request.user.staff,
                                                 action_type='grades_submitted', assessment=assessment, ip_address=ip,
                                                 notes='Оценки внесены через фронтенд-журнал группы')

        if errors:
            return Response({'success': True, 'saved_count': saved_count, 'warnings': errors},
                            status=status.HTTP_200_OK)
        return Response(
            {'success': True, 'saved_count': saved_count, 'message': f'Успешно сохранено {saved_count} оценок'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@transaction.atomic
@group_write_guard
def complete_all_passed(request, group_id):
    """Завершает всех студентов, сдавших все ОЦЕНИВАЕМЫЕ разделы"""
    group = get_object_or_404(Group.objects.select_for_update(), id=group_id)
    if not can_manage_group(request.user, group):
        return Response({'error': 'Завершение доступно методисту или куратору группы.'}, status=403)
    if group.status in ('completed', 'archived', 'cancelled'):
        return Response({'error': 'Группа уже закрыта или отменена.'}, status=400)
    from execution.completion import choose_completion_date, log_completion_date
    from execution.local_time import group_today
    completion_date, reason = choose_completion_date(group, request.data)

    # Берем только активных студентов
    students = Enrollment.objects.filter(group=group, status__in=['enrolled', 'in_progress'])
    sections = Section.objects.filter(stage__module=group.module, grade_type__in=['numeric', 'binary'])

    completed_count = 0
    today = group_today(group)

    for enrollment in students:
        assessments = Assessment.objects.filter(enrollment=enrollment, section__in=sections, passed=True)
        passed_section_ids = set(assessments.values_list('section_id', flat=True))
        required_section_ids = set(sections.values_list('id', flat=True))

        if passed_section_ids >= required_section_ids:
            enrollment.status = 'completed'
            enrollment.completed_at = completion_date
            enrollment.final_result = 'passed'
            if not enrollment.order_out_number or not enrollment.order_out_date:
                enrollment.order_out_number = enrollment.generate_order_out_number('completed', is_individual=False)
                enrollment.order_out_date = today
            enrollment.save()
            completed_count += 1

    if completed_count:
        log_completion_date(group, request.user, completion_date, reason, 'enrollments_completed')

    return Response({
        'success': True,
        'message': f'Завершено студентов: {completed_count}'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def dismiss_failed(request, group_id):
    """Отчисляет всех студентов, не сдавших ОЦЕНИВАЕМЫЕ разделы"""
    group = get_object_or_404(Group, id=group_id)
    students = Enrollment.objects.filter(group=group, status__in=['enrolled', 'in_progress'])

    # 🔥 ИСПРАВЛЕНИЕ: Берем ТОЛЬКО разделы, которые требуют оценки
    sections = Section.objects.filter(stage__module=group.module, grade_type__in=['numeric', 'binary'])

    dismissed_count = 0
    for enrollment in students:
        # 🔥 ИСПРАВЛЕНИЕ: Используем поле passed вместо score__gte=1
        assessments = Assessment.objects.filter(enrollment=enrollment, section__in=sections, passed=True)
        passed_section_ids = set(assessments.values_list('section_id', flat=True))

        required_section_ids = set(sections.values_list('id', flat=True))

        # Проверяем, что НЕ все оцениваемые разделы сданы
        if not (passed_section_ids >= required_section_ids):
            enrollment.status = 'dismissed'
            enrollment.dismissal_date = timezone.now().date()
            enrollment.dismissal_reason = 'Неуспеваемость (не сданы все оцениваемые разделы)'
            enrollment.save()
            dismissed_count += 1

    return Response({
        'success': True,
        'message': f'Отчислено студентов: {dismissed_count}'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def active_curators_list(request):
    curator_ids = Group.objects.exclude(curator__isnull=True).values_list('curator_id', flat=True).distinct()
    staff = Staff.objects.filter(id__in=curator_ids).order_by('full_name')
    return Response([{'id': s.id, 'full_name': s.full_name} for s in staff])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_documents_api(request, group_id):
    """API для получения списка документов группы и их статусов"""
    group = get_object_or_404(Group, id=group_id)

    saved_files = []
    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    safe_group_number = re.sub(r'[^\w\.\-]', '_', group.assigned_number)
    group_folder_name = f"documents/{year}/groups/{module_code}/{safe_group_number}"
    expected_base = os.path.join(settings.MEDIA_ROOT, group_folder_name.replace('/', os.sep))

    if os.path.exists(expected_base):
        for root, dirs, files in os.walk(expected_base):
            for file in files:
                if file.lower().endswith('.pdf'):
                    abs_root = os.path.abspath(root)
                    abs_media = os.path.abspath(settings.MEDIA_ROOT)
                    if abs_root.startswith(abs_media):
                        rel_part = abs_root[len(abs_media):].strip('/\\')
                        if not rel_part.lower().startswith('documents'):
                            rel_part = os.path.join('documents', rel_part)
                        full_relative_path = os.path.join(rel_part, file).replace('\\', '/')
                        saved_files.append(
                            {'filename': file, 'lower_name': file.lower(), 'full_path': full_relative_path})

    doc_identifiers = {
        'enrollment_order': ['зачисл', 'enrollment', '-з.pdf', '_з.pdf', '-3.pdf', '_3.pdf', 'приказ_з'],
        'dismissal_ok': ['_ок', '-ок', '_ok', '-ok', 'оконч'],
        'dismissal_ot': ['_от', '-от', '_ot', '-ot', 'отчисл'],
        'dismissal_reference': ['справк', 'reference'],
        'journal': ['журнал', 'journal'],
        'schedule': ['распис', 'schedule'],
        'land_training_task': ['суша', 'land', 'asp-l', 'суш'],
        'water_training_task': ['вода', 'water', 'asp-w', 'вод'],
        'certificate': ['удостовер', 'сертификат', 'модуль', 'certificate', 'cert'],
        'audit_log': ['аудит', 'audit', 'пэп', 'pep'],
    }

    documents_list = []
    for doc_key, doc_info in DocumentRegistry.get_documents_for_group(group).items():
        is_saved = False
        saved_file_path = None
        identifiers = doc_identifiers.get(doc_key, [])

        for saved_file in saved_files:
            if identifiers and any(marker in saved_file['lower_name'] for marker in identifiers):
                is_saved = True
                saved_file_path = saved_file['full_path']
                break

        view_url = None
        if doc_info.get('view_name'):
            try:
                view_url = reverse(doc_info['view_name'], args=[group_id])
            except:
                pass

        documents_list.append({
            'key': doc_key, 'name': doc_info['name'], 'icon': doc_info['icon'],
            'status': doc_info['status'], 'is_saved': is_saved,
            'saved_file_path': saved_file_path, 'view_url': view_url,
        })

    reports_folder = os.path.join(expected_base, 'reports')
    rauc_excel = {'saved': False, 'path': None}
    rauc_xml = {'saved': False, 'path': None}
    frdo_excel = {'saved': False, 'path': None}

    if os.path.exists(reports_folder):
        for file in os.listdir(reports_folder):
            if file.startswith('РАУЦ_') and file.endswith('.xlsx'):
                rauc_excel = {'saved': True,
                              'path': os.path.relpath(os.path.join(reports_folder, file), settings.MEDIA_ROOT).replace(
                                  '\\', '/')}
            elif file.startswith('РАУЦ_') and file.endswith('.xml'):
                rauc_xml = {'saved': True,
                            'path': os.path.relpath(os.path.join(reports_folder, file), settings.MEDIA_ROOT).replace(
                                '\\', '/')}
            elif file.startswith('ФРДО_') and file.endswith('.xlsx'):
                frdo_excel = {'saved': True,
                              'path': os.path.relpath(os.path.join(reports_folder, file), settings.MEDIA_ROOT).replace(
                                  '\\', '/')}

    return Response({
        'group': {
            'id': group.id, 'assigned_number': group.assigned_number,
            'module_code': group.module.code if group.module else '',
            'module_title': group.module.title if group.module else '',
            'start_date': group.start_date.strftime('%d.%m.%Y') if group.start_date else None,
            'end_date': group.end_date.strftime('%d.%m.%Y') if group.end_date else None,
        },
        'documents': documents_list,
        'reports': {'rauc_excel': rauc_excel, 'rauc_xml': rauc_xml, 'frdo_excel': frdo_excel}
    })


# ==============================================================================
# РЕАЛЬНЫЕ API ЭНДПОИНТЫ ДЛЯ ДОКУМЕНТОВ (БЕЗ ЗАГЛУШЕК)
# ==============================================================================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def save_single_document_api(request, group_id):
    """Сохраняет один конкретный документ через DocumentStorageService"""
    group = get_object_or_404(Group, id=group_id)
    doc_type = request.data.get('document_type')

    if not doc_type:
        return Response({'error': 'document_type is required'}, status=400)

    service = DocumentStorageService(group)

    try:
        save_methods = {
            'enrollment_order': service.save_enrollment_order,
            'schedule': service.save_schedule,
            'journal': service.save_journal,
            'land_training_task': service.save_land_training_task,
            'water_training_task': service.save_water_training_task,
            'dismissal_ok': service.save_dismissal_ok,
            'dismissal_ot': service.save_dismissal_ot,
            'dismissal_reference': service.save_dismissal_reference,
            'certificate': service.save_certificate,
            'audit_log': service.save_audit_log,
        }

        if doc_type not in save_methods:
            return Response({'error': f'Unknown document type: {doc_type}'}, status=400)

        pdf_path = save_methods[doc_type]()

        return Response({
            'success': True,
            'message': f'Документ {doc_type} успешно сгенерирован и сохранен.',
            'pdf_path': pdf_path,
        })
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def generate_all_documents_api(request, group_id):
    """Массовая генерация всех активных документов"""
    group = get_object_or_404(Group, id=group_id)
    service = DocumentStorageService(group)

    generated = []
    skipped = []
    errors = []

    for doc_key, doc_info in DocumentRegistry.get_active_documents().items():
        method_name = doc_info.get('save_method')
        doc_name = doc_info['name']

        if not method_name:
            continue

        try:
            method = getattr(service, method_name, None)
            if method:
                result = method()
                if result:
                    generated.append(doc_name)
                else:
                    skipped.append(f"{doc_name} (нет данных в расписании)")
        except ValueError as e:
            skipped.append(f"{doc_name} ({str(e)})")
        except Exception as e:
            errors.append(f"{doc_name}: {str(e)}")

    return Response({
        'success': True,
        'generated_count': len(generated),
        'skipped_count': len(skipped),
        'errors_count': len(errors),
        'details': {'generated': generated, 'skipped': skipped, 'errors': errors},
        'message': f'Успешно сгенерировано: {len(generated)}. Пропущено (нет данных): {len(skipped)}.'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def save_rauc_report_api(request, group_id, format_type):
    """Сохраняет отчет РАУЦ (excel или xml) через реальный сервис"""
    group = get_object_or_404(Group, id=group_id)
    try:
        service = RAUCExportService(group, user=request.user)

        if format_type == 'excel':
            filepath, rel_path, errors = service.generate_excel()
            report = service.save_to_database(excel_path=filepath, file_format='excel')
        elif format_type == 'xml':
            filepath, rel_path, errors = service.generate_xml()
            report = service.save_to_database(xml_path=filepath, file_format='xml')
        else:
            return Response({'success': False, 'error': f'Неизвестный формат: {format_type}'}, status=400)

        return Response({
            'success': True,
            'message': f'РАУЦ ({format_type}) успешно сохранен',
            'file_path': rel_path,
            'report_id': report.id,
            'warnings': [str(e) for e in errors] if errors else []
        })
    except ValueError as e:
        # 🔥 Обрабатываем ValueError как 400, а не 500
        return Response({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def save_frdo_report_api(request, group_id):
    """Сохраняет отчет ФРДО через реальный сервис"""
    group = get_object_or_404(Group, id=group_id)
    try:
        service = FRDOExportService(group, user=request.user)
        filepath, rel_path, errors = service.generate_excel()
        report = service.save_to_database(excel_path=filepath, file_format='excel')

        return Response({
            'success': True,
            'message': 'ФРДО успешно сохранен',
            'file_path': rel_path,
            'report_id': report.id,
            'warnings': [str(e) for e in errors] if errors else []
        })
    except ValueError as e:
        # 🔥 Обрабатываем ValueError как 400, а не 500
        return Response({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return Response({'success': False, 'error': str(e)}, status=500)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_document_pdf(request, group_id, doc_key):
    """Возвращает PDF-файл для просмотра в браузере"""
    group = get_object_or_404(Group, id=group_id)
    doc_info = DocumentRegistry.get_documents_for_group(group).get(doc_key)
    if not doc_info:
        return Response({'error': 'Документ не найден'}, status=404)

    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    safe_group_number = re.sub(r'[^\w\.\-]', '_', group.assigned_number)
    group_folder_name = f"documents/{year}/groups/{module_code}/{safe_group_number}"
    expected_base = os.path.join(settings.MEDIA_ROOT, group_folder_name.replace('/', os.sep))

    doc_identifiers = {
        'enrollment_order': ['зачисл', 'enrollment', '-з.pdf', '_з.pdf', '-3.pdf', '_3.pdf', 'приказ_з'],
        'dismissal_ok': ['_ок', '-ок', '_ok', '-ok', 'оконч'],
        'dismissal_ot': ['_от', '-от', '_ot', '-ot', 'отчисл'],
        'dismissal_reference': ['справк', 'reference'],
        'journal': ['журнал', 'journal'],
        'schedule': ['распис', 'schedule'],
        'land_training_task': ['суша', 'land', 'asp-l', 'суш'],
        'water_training_task': ['вода', 'water', 'asp-w', 'вод'],
        'certificate': ['удостовер', 'сертификат', 'модуль', 'certificate', 'cert'],
        'audit_log': ['аудит', 'audit', 'пэп', 'pep'],
    }

    identifiers = doc_identifiers.get(doc_key, [])
    saved_file_path = None

    if os.path.exists(expected_base):
        for root, dirs, files in os.walk(expected_base):
            for file in files:
                if file.lower().endswith('.pdf'):
                    if identifiers and any(marker in file.lower() for marker in identifiers):
                        abs_root = os.path.abspath(root)
                        abs_media = os.path.abspath(settings.MEDIA_ROOT)
                        if abs_root.startswith(abs_media):
                            rel_part = abs_root[len(abs_media):].strip('/\\')
                            if not rel_part.lower().startswith('documents'):
                                rel_part = os.path.join('documents', rel_part)
                            saved_file_path = os.path.join(rel_part, file).replace('\\', '/')
                            break
            if saved_file_path:
                break

    if not saved_file_path:
        return Response({'error': 'Файл не найден. Сначала сгенерируйте документ.'}, status=404)

    full_path = os.path.join(settings.MEDIA_ROOT, saved_file_path)
    if not os.path.exists(full_path):
        return Response({'error': 'Файл не существует на сервере'}, status=404)

    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/pdf',
        as_attachment=False
    )
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(full_path)}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_document_pdf(request, group_id, doc_key):
    """Скачивает PDF-файл документа"""
    group = get_object_or_404(Group, id=group_id)
    doc_info = DocumentRegistry.get_documents_for_group(group).get(doc_key)
    if not doc_info:
        return Response({'error': 'Документ не найден'}, status=404)

    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    safe_group_number = re.sub(r'[^\w\.\-]', '_', group.assigned_number)
    group_folder_name = f"documents/{year}/groups/{module_code}/{safe_group_number}"
    expected_base = os.path.join(settings.MEDIA_ROOT, group_folder_name.replace('/', os.sep))

    doc_identifiers = {
        'enrollment_order': ['зачисл', 'enrollment', '-сз', '_сз', '-з.pdf', 'приказ', 'order'],
        'dismissal_ok': ['_ок', '-ок', '_ok', '-ok', 'оконч'],
        'dismissal_ot': ['_от', '-от', '_ot', '-ot', 'отчисл'],
        'dismissal_reference': ['справк', 'reference'],
        'journal': ['журнал', 'journal'],
        'schedule': ['распис', 'schedule'],
        'land_training_task': ['суша', 'land', 'asp-l', 'суш'],
        'water_training_task': ['вода', 'water', 'asp-w', 'вод'],
        'certificate': ['удостовер', 'сертификат', 'модуль', 'certificate', 'cert'],
        'audit_log': ['аудит', 'audit', 'пэп', 'pep'],
    }

    identifiers = doc_identifiers.get(doc_key, [])
    saved_file_path = None

    if os.path.exists(expected_base):
        for root, dirs, files in os.walk(expected_base):
            for file in files:
                if file.lower().endswith('.pdf'):
                    if identifiers and any(marker in file.lower() for marker in identifiers):
                        abs_root = os.path.abspath(root)
                        abs_media = os.path.abspath(settings.MEDIA_ROOT)
                        if abs_root.startswith(abs_media):
                            rel_part = abs_root[len(abs_media):].strip('/\\')
                            if not rel_part.lower().startswith('documents'):
                                rel_part = os.path.join('documents', rel_part)
                            saved_file_path = os.path.join(rel_part, file).replace('\\', '/')
                            break
            if saved_file_path:
                break

    if not saved_file_path:
        return Response({'error': 'Файл не найден. Сначала сгенерируйте документ.'}, status=404)

    full_path = os.path.join(settings.MEDIA_ROOT, saved_file_path)
    if not os.path.exists(full_path):
        return Response({'error': 'Файл не существует на сервере'}, status=404)

    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/pdf',
        as_attachment=True
    )
    response['Content-Disposition'] = f'attachment; filename="{os.path.basename(full_path)}"'
    return response



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_rauc_report_api(request, group_id, format_type):
    """Скачивает отчёт РАУЦ (excel или xml)"""
    group = get_object_or_404(Group, id=group_id)

    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    safe_group_number = re.sub(r'[^\w\.\-]', '_', group.assigned_number)
    reports_folder = os.path.join(
        settings.MEDIA_ROOT, 'documents', year, 'groups', module_code, safe_group_number, 'reports'
    )

    if not os.path.exists(reports_folder):
        return Response({'error': 'Папка отчётов не найдена'}, status=404)

    # Ищем файл по префиксу и расширению
    target_file = None
    extension = '.xlsx' if format_type == 'excel' else '.xml'

    for file in os.listdir(reports_folder):
        if file.startswith('РАУЦ_') and file.endswith(extension):
            target_file = file
            break

    if not target_file:
        return Response({'error': f'Файл РАУЦ ({format_type}) не найден. Сначала сгенерируйте отчёт.'}, status=404)

    full_path = os.path.join(reports_folder, target_file)

    # Определяем MIME-тип
    if format_type == 'xml':
        content_type = 'application/xml'
    else:
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

    response = FileResponse(
        open(full_path, 'rb'),
        content_type=content_type,
        as_attachment=True
    )
    response['Content-Disposition'] = f'attachment; filename="{target_file}"'
    return response


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_frdo_report_api(request, group_id):
    """Скачивает отчёт ФРДО"""
    group = get_object_or_404(Group, id=group_id)

    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    safe_group_number = re.sub(r'[^\w\.\-]', '_', group.assigned_number)
    reports_folder = os.path.join(
        settings.MEDIA_ROOT, 'documents', year, 'groups', module_code, safe_group_number, 'reports'
    )

    if not os.path.exists(reports_folder):
        return Response({'error': 'Папка отчётов не найдена'}, status=404)

    # Ищем файл ФРДО
    target_file = None
    for file in os.listdir(reports_folder):
        if file.startswith('ФРДО_') and file.endswith('.xlsx'):
            target_file = file
            break

    if not target_file:
        return Response({'error': 'Файл ФРДО не найден. Сначала сгенерируйте отчёт.'}, status=404)

    full_path = os.path.join(reports_folder, target_file)

    response = FileResponse(
        open(full_path, 'rb'),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True
    )
    response['Content-Disposition'] = f'attachment; filename="{target_file}"'
    return response


# docs/api_views.py - функция group_schedule_list

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def group_schedule_list(request, group_id):
    """Получение полного расписания группы с подтянутыми связями"""
    group = get_schedule_group(request.user, id=group_id)

    items = ScheduleItem.objects.filter(group=group).select_related(
        'section', 'subsection', 'instructor', 'classroom', 'classroom__organization', 'classroom__location'
    ).order_by('date', 'start_time', 'section__order')

    data = []
    for item in items:
        data.append({
            'id': item.id,
            'date': item.date.strftime('%Y-%m-%d') if item.date else None,
            'deadline': item.deadline.strftime('%Y-%m-%d') if item.deadline else None,
            'start_time': item.start_time.strftime('%H:%M') if item.start_time else None,
            'end_time': item.end_time.strftime('%H:%M') if item.end_time else None,
            'session_type': item.session_type,
            'status': item.status,
            'notes': item.notes,
            'section': {'id': item.section.id, 'title': item.section.title,
                        'duration_hours': item.section.duration_hours} if item.section else None,
            'subsection': {'id': item.subsection.id, 'title': item.subsection.title} if item.subsection else None,
            'instructor': {'id': item.instructor.id, 'name': item.instructor.full_name} if item.instructor else None,
            'classroom': {
                'id': item.classroom.id,
                'title': item.classroom.title,
                'audience': item.classroom.audience,
                'full_address': item.classroom.full_address
            } if item.classroom else None,
        })

    return Response(data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
@group_write_guard
def update_schedule_item(request, item_id):
    """Частичное обновление одного занятия (для inline-редактирования)"""
    item = get_object_or_404(ScheduleItem.objects.select_related("group"), id=item_id)
    if not can_manage_group(request.user, item.group):
        raise PermissionDenied()

    serializer = ScheduleItemUpdateSerializer(
        item, data=request.data, partial=True, context={'group': item.group}
    )
    if serializer.is_valid():
        serializer.save()
        return Response({'success': True, 'data': serializer.data})
    return Response({'success': False, 'errors': serializer.errors}, status=400)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def schedule_dropdowns(request, group_id):
    """Получение справочников для выпадающих списков в редакторе"""
    group = get_schedule_group(request.user, id=group_id)

    # 1. Инструкторы (активные сотрудники)
    instructors_qs = Staff.objects.filter(is_active=True, is_instructor=True).order_by('full_name')
    eligibility_error = None
    if request.query_params.get('section_id'):
        from datetime import date as calendar_date
        from training.qualification_services import assignment_error
        try:
            target_section = Section.objects.get(pk=request.query_params['section_id'], stage__module=group.module)
            target_date = calendar_date.fromisoformat(request.query_params.get('date', ''))
            deadline = calendar_date.fromisoformat(request.query_params['deadline']) if request.query_params.get('deadline') else None
        except (ValueError, Section.DoesNotExist):
            return Response({'error': 'Укажите корректные раздел и дату занятия.'}, status=400)
        if not target_section.subject_id or not target_section.teaching_device_type:
            eligibility_error = 'В справочнике разделов укажите предмет и формат преподавания для проверки допуска.'
        allowed = [row.pk for row in instructors_qs if not assignment_error(row, target_section, target_date, deadline)]
        instructors_qs = instructors_qs.filter(pk__in=allowed)
    instructors = instructors_qs.values('id', 'full_name')

    # 2. Аудитории (с группировкой для удобного отображения)
    classrooms = Classroom.objects.select_related('location', 'organization').values(
        'id', 'title', 'audience', 'location__name', 'organization__company_name'
    ).order_by('title')

    # Формируем читаемые метки для аудиторий
    classroom_list = []
    for c in classrooms:
        loc = c['location__name'] or ''
        org = c['organization__company_name'] or ''
        aud = c['audience'] or ''
        label = f"{c['title']}"
        if aud: label += f" (ауд. {aud})"
        if loc: label += f" — {loc}"
        if org: label += f" ({org})"
        classroom_list.append({'id': c['id'], 'label': label})

    # 3. Разделы (Sections) для модуля этой группы
    sections = Section.objects.filter(stage__module=group.module).values('id', 'title', 'duration_hours').order_by(
        'stage__order', 'order')

    return Response({
        'instructors': list(instructors),
        'eligibility_error': eligibility_error,
        'classrooms': classroom_list,
        'sections': list(sections)
    })



@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
@group_write_guard
def delete_schedule_item(request, item_id):
    """Удаление занятия расписания"""
    item = get_object_or_404(ScheduleItem.objects.select_related("group"), id=item_id)
    if not can_manage_group(request.user, item.group):
        raise PermissionDenied()
    item.delete()
    return Response({'success': True, 'message': 'Занятие удалено'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@group_write_guard
def create_schedule_item(request, group_id):
    """Создание нового занятия расписания"""
    group = get_schedule_group(request.user, id=group_id)

    # Обязательные поля
    if not request.data.get('date') or not request.data.get('section'):
        return Response({'error': 'Дата и раздел обязательны'}, status=400)

    serializer = ScheduleItemUpdateSerializer(data=request.data, context={'group': group})
    if serializer.is_valid():
        serializer.save(group=group)
        return Response({'success': True, 'data': serializer.data}, status=201)
    return Response({'success': False, 'errors': serializer.errors}, status=400)