# execution/student_views.py
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import ScheduleItem, ComplianceLog, Enrollment, Assessment, Certificate
from people.models import Student


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_modules(request):
    try:
        student = request.user.student
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль студента не найден'}, status=status.HTTP_403_FORBIDDEN)

    enrollments = Enrollment.objects.filter(student=student).select_related('group__module')
    modules_data = []

    for enrollment in enrollments:
        module = enrollment.group.module

        # === 1. Расписание занятий ===
        schedule_items = ScheduleItem.objects.filter(
            group=enrollment.group
        ).select_related('section', 'subsection', 'classroom', 'instructor').order_by('date', 'start_time')

        schedule_data = []
        for item in schedule_items:
            has_attendance = ComplianceLog.objects.filter(
                schedule_item=item,
                student=student,
                action_type='student_attendance_confirmed'
            ).exists()
            schedule_data.append({
                'id': item.id,
                'session_type': item.session_type,
                'date': item.date,
                'start_time': item.start_time,
                'end_time': item.end_time,
                'section_title': item.section.title if item.section else None,
                'subsection_title': item.subsection.title if item.subsection else None,
                'classroom': str(item.classroom) if item.classroom else None,
                'instructor': item.instructor.full_name if item.instructor else None,
                'has_attendance': has_attendance
            })

        # === 2. Инструктаж по ТБ ===
        safety_ack_log = ComplianceLog.objects.filter(
            enrollment=enrollment, student=student, action_type='student_safety_ack'
        ).first()
        has_safety_ack = safety_ack_log is not None
        instructing_doc_url = request.build_absolute_uri("/docs/instructing/")

        # === 3. Ознакомление с расписанием ===
        schedule_ack_log = ComplianceLog.objects.filter(
            enrollment=enrollment, student=student, action_type='student_schedule_ack'
        ).first()
        has_schedule_ack = schedule_ack_log is not None
        schedule_doc_url = request.build_absolute_uri(f"/docs/schedule/{enrollment.group.id}/")

        # === 4. Оценки ===
        # Получаем все разделы модуля, которые требуют оценки
        from training.models import Section

        required_sections = Section.objects.filter(
            stage__module=module,
            grade_type__in=['numeric', 'binary']
        ).order_by('stage__order', 'order')

        # Получаем существующие оценки
        assessments = Assessment.objects.filter(enrollment=enrollment).select_related('section').order_by(
            'section__stage__order', 'section__order')

        grades_data = []
        for assessment in assessments:
            has_grade_ack = ComplianceLog.objects.filter(
                assessment=assessment, student=student, action_type='student_grade_ack'
            ).exists()
            is_final = bool(assessment.section and any(
                word in assessment.section.title.lower() for word in ['итогов', 'экзамен', 'итоговая']))

            grades_data.append({
                'id': assessment.id,
                'section_title': assessment.section.title if assessment.section else None,
                'score': assessment.score,
                'grade_type': assessment.section.grade_type if assessment.section else 'none',
                'passed': assessment.passed,
                'assessment_date': assessment.assessment_date,
                'attempt_number': assessment.attempt_number,
                'is_final': is_final,
                'has_grade_ack': has_grade_ack
            })

        # === 5. Документы ===
        certificates = Certificate.objects.filter(enrollment=enrollment)
        certificates_data = []
        for cert in certificates:
            has_received = ComplianceLog.objects.filter(
                certificate=cert, student=student, action_type='certificate_received'
            ).exists()
            certificates_data.append({
                'id': cert.id,
                'type': cert.get_certificate_type_display(),
                'number': cert.number,
                'issue_date': cert.issue_date,
                'has_received': has_received
            })

        # === 6. Проверка полного завершения ===
        offline_items = [item for item in schedule_data if item.get('session_type') != 'sdo']
        all_offline_attendance_confirmed = all(
            item['has_attendance'] for item in offline_items) if offline_items else True

        # НОВОЕ: Проверяем, что для ВСЕХ требуемых разделов есть оценки
        all_grades_set = True
        all_grades_acknowledged = True

        if required_sections.exists():
            for section in required_sections:
                # Ищем оценку для этого раздела
                assessment = next((g for g in grades_data if g.get('section_title') == section.title), None)

                if not assessment or assessment['score'] is None:
                    all_grades_set = False
                    break

                if not assessment['has_grade_ack']:
                    all_grades_acknowledged = False
        else:
            # Если нет разделов с оценками — считаем, что всё ок
            all_grades_set = True
            all_grades_acknowledged = True

        has_certificates = len(certificates_data) > 0
        all_certificates_received = all(c['has_received'] for c in certificates_data) if has_certificates else True

        # === 7. Проверка ЗНТ (только для АСП Суша/Вода) ===
        has_znt = any(item['session_type'] in ['asp-l', 'asp-w'] for item in schedule_data)

        znt_log = ComplianceLog.objects.filter(
            enrollment=enrollment,
            student=student,
            action_type='znt_received'
        ).first()
        znt_received = znt_log is not None

        znt_issue_date = None
        if znt_log:
            znt_issue_date = znt_log.timestamp.date().isoformat()
        elif enrollment.completed_at:
            znt_issue_date = enrollment.completed_at.isoformat()

        # === ИТОГОВАЯ ПРОВЕРКА ЗАВЕРШЕНИЯ ===
        # Для АСП-модулей: нужны И сертификаты (и они должны быть получены), И ЗНТ
        # Для обычных модулей: если есть сертификаты - они должны быть получены

        if has_znt:
            # АСП-модуль: строго требуются оба документа
            documents_complete = has_certificates and all_certificates_received and znt_received
        else:
            # Обычный модуль: если есть сертификаты - они должны быть получены
            documents_complete = all_certificates_received

        is_fully_completed = (
                has_schedule_ack and
                has_safety_ack and
                all_offline_attendance_confirmed and
                all_grades_set and
                all_grades_acknowledged and
                documents_complete
        )
        # === Формируем ответ ===
        modules_data.append({
            'enrollment_id': enrollment.id,
            'module_id': module.id,
            'module_title': module.title,
            'module_code': module.code,
            'group_number': enrollment.group.assigned_number,
            'db_status': enrollment.get_status_display(),
            'is_fully_completed': is_fully_completed,

            'instructing_doc': {
                'url': instructing_doc_url,
                'has_ack': has_safety_ack,
                'ack_date': safety_ack_log.timestamp if safety_ack_log else None
            },
            'schedule_doc': {
                'url': schedule_doc_url,
                'has_ack': has_schedule_ack,
                'ack_date': schedule_ack_log.timestamp if schedule_ack_log else None
            },
            'schedule': schedule_data,
            'grades': grades_data,
            'certificates': certificates_data,

            'has_znt': has_znt,
            'znt_received': znt_received,
            'znt_issue_date': znt_issue_date,

            # НОВОЕ ПОЛЕ: флаг готовности оценок
            'all_grades_set': all_grades_set,
        })

    return Response(modules_data)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def student_confirm_action(request):
    """
    POST /api/student/confirm/
    Фиксирует действие студента
    """
    try:
        student = request.user.student
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль студента не найден'}, status=status.HTTP_403_FORBIDDEN)

    action_type = request.data.get('action_type')

    valid_actions = [
        'student_schedule_ack',
        'student_safety_ack',
        'student_attendance_confirmed',
        'student_grade_ack',
        'certificate_received',
        'znt_received'  # <-- ДОБАВЛЕНО
    ]

    if action_type not in valid_actions:
        return Response({'error': 'Недопустимый тип действия'}, status=status.HTTP_400_BAD_REQUEST)

    # Определяем IP
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')

    # Базовые данные для лога
    log_data = {
        'student': student,
        'action_type': action_type,
        'ip_address': ip,
        'notes': request.data.get('notes', '')
    }

    # === Обработчики по типу действия ===

    # 1. Ознакомление с расписанием
    if action_type == 'student_schedule_ack':
        enrollment_id = request.data.get('enrollment_id')
        if not enrollment_id:
            return Response({'error': 'Не указано зачисление'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            enrollment = Enrollment.objects.get(pk=enrollment_id, student=student)
        except Enrollment.DoesNotExist:
            return Response({'error': 'Зачисление не найдено'}, status=status.HTTP_404_NOT_FOUND)
        log_data['enrollment'] = enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Вы уже ознакомлены с расписанием'}, status=status.HTTP_400_BAD_REQUEST)

    # 2. Инструктаж по ТБ
    elif action_type == 'student_safety_ack':
        enrollment_id = request.data.get('enrollment_id')
        if not enrollment_id:
            return Response({'error': 'Не указано зачисление'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            enrollment = Enrollment.objects.get(pk=enrollment_id, student=student)
        except Enrollment.DoesNotExist:
            return Response({'error': 'Зачисление не найдено'}, status=status.HTTP_404_NOT_FOUND)
        log_data['enrollment'] = enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Вы уже ознакомлены с инструктажем'}, status=status.HTTP_400_BAD_REQUEST)

    # 3. Подтверждение присутствия
    elif action_type == 'student_attendance_confirmed':
        schedule_item_id = request.data.get('schedule_item_id')
        if not schedule_item_id:
            return Response({'error': 'Не указано занятие'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            schedule_item = ScheduleItem.objects.get(pk=schedule_item_id)
        except ScheduleItem.DoesNotExist:
            return Response({'error': 'Занятие не найдено'}, status=status.HTTP_404_NOT_FOUND)

        enrollment = Enrollment.objects.filter(student=student, group=schedule_item.group).first()
        if not enrollment:
            return Response({'error': 'Вы не зачислены в эту группу'}, status=status.HTTP_403_FORBIDDEN)

        # === ПРОВЕРКА ВРЕМЕНИ (с учетом локации группы) ===
        from execution.utils import check_schedule_time_allowed

        is_allowed, error_msg = check_schedule_time_allowed(schedule_item)
        if not is_allowed:
            return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
        # ==================================================

        log_data['schedule_item'] = schedule_item
        log_data['enrollment'] = enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Присутствие уже подтверждено'}, status=status.HTTP_400_BAD_REQUEST)

    # 4. Ознакомление с оценкой
    elif action_type == 'student_grade_ack':
        assessment_id = request.data.get('assessment_id')
        if not assessment_id:
            return Response({'error': 'Не указана оценка'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            assessment = Assessment.objects.get(pk=assessment_id, enrollment__student=student)
        except Assessment.DoesNotExist:
            return Response({'error': 'Оценка не найдена'}, status=status.HTTP_404_NOT_FOUND)

        # === ПРОВЕРКА 1: Оценка должна быть реально выставлена ===
        if assessment.score is None:
            return Response(
                {'error': 'Оценка ещё не выставлена преподавателем'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # === ПРОВЕРКА 2: Время занятия должно наступить ===
        from execution.utils import check_schedule_time_allowed

        schedule_item = ScheduleItem.objects.filter(
            group=assessment.enrollment.group,
            section=assessment.section
        ).first()

        if schedule_item:
            is_allowed, error_msg = check_schedule_time_allowed(schedule_item)
            if not is_allowed:
                return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
        # ==================================================

        log_data['assessment'] = assessment
        log_data['enrollment'] = assessment.enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Вы уже ознакомлены с этой оценкой'}, status=status.HTTP_400_BAD_REQUEST)

    # 5. Получение документа
    elif action_type == 'certificate_received':
        certificate_id = request.data.get('certificate_id')
        if not certificate_id:
            return Response({'error': 'Не указан документ'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            certificate = Certificate.objects.get(pk=certificate_id, enrollment__student=student)
        except Certificate.DoesNotExist:
            return Response({'error': 'Документ не найден'}, status=status.HTTP_404_NOT_FOUND)
        log_data['certificate'] = certificate
        log_data['enrollment'] = certificate.enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Вы уже получили этот документ'}, status=status.HTTP_400_BAD_REQUEST)

    # 6. Получение ЗНТ (НОВОЕ)
    elif action_type == 'znt_received':
        enrollment_id = request.data.get('enrollment_id')
        if not enrollment_id:
            return Response({'error': 'Не указано зачисление'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            enrollment = Enrollment.objects.get(pk=enrollment_id, student=student)
        except Enrollment.DoesNotExist:
            return Response({'error': 'Зачисление не найдено'}, status=status.HTTP_404_NOT_FOUND)
        log_data['enrollment'] = enrollment
        if ComplianceLog.objects.filter(**log_data).exists():
            return Response({'error': 'Вы уже подтвердили получение ЗНТ'}, status=status.HTTP_400_BAD_REQUEST)

    # === Создаём запись в логе ===
    log = ComplianceLog.objects.create(**log_data)

    return Response({
        'message': 'Действие успешно зафиксировано',
        'signature': log.signature_string,
        'timestamp': log.timestamp.isoformat()
    }, status=status.HTTP_200_OK)