# execution/api_views.py
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import generics, permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
from people.models import Staff, Student
from training.models import Section
from .models import ScheduleItem, Assessment, Enrollment, Group
from .serializers import (
    InstructorScheduleSerializer,
    InstructorGradesSerializer, StudentCreateSerializer,
)
from .models import ScheduleItem, ComplianceLog
from rest_framework.permissions import IsAuthenticated
from rest_framework import status


class InstructorScheduleView(generics.ListAPIView):
    """
    GET /api/instructor/schedule/
    Возвращает расписание преподавателя на сегодня и в будущем.
    """
    serializer_class = InstructorScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        today = timezone.now().date()

        # Безопасно получаем профиль Staff. Если его нет - вернем пустой QuerySet
        staff = getattr(self.request.user, 'staff', None)
        if not staff:
            return ScheduleItem.objects.none()

        return ScheduleItem.objects.filter(
            instructor=staff,
            date__gte=today,
            status__in=['planned', 'in_progress']
        ).select_related(
            'group', 'section', 'subsection', 'classroom', 'instructor'
        ).order_by('date', 'start_time')

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def confirm_schedule_item(request, pk):
    """
    POST /api/instructor/schedule/<pk>/confirm/
    Преподаватель подтверждает проведение занятия.
    """
    try:
        schedule_item = ScheduleItem.objects.get(pk=pk, instructor=request.user.staff)
    except ScheduleItem.DoesNotExist:
        return Response(
            {'error': 'Занятие не найдено или вы не назначены инструктором'},
            status=status.HTTP_404_NOT_FOUND
        )

    if schedule_item.is_confirmed:
        return Response(
            {'message': 'Занятие уже подтверждено'},
            status=status.HTTP_200_OK
        )

    schedule_item.is_confirmed = True
    schedule_item.confirmed_by = request.user.staff
    schedule_item.confirmed_at = timezone.now()
    schedule_item.save(update_fields=['is_confirmed', 'confirmed_by', 'confirmed_at'])

    return Response({
        'message': 'Занятие подтверждено',
        'confirmed_at': schedule_item.confirmed_at.isoformat()
    })


class InstructorGradesView(generics.ListAPIView):
    """
    GET /api/instructor/grades/<group_id>/
    Возвращает журнал оценок для преподавателя.
    Показывает только те разделы, которые ведет этот преподаватель.
    """
    serializer_class = InstructorGradesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs['group_id']
        # Получаем все зачисления в эту группу
        return Enrollment.objects.filter(
            group_id=group_id,
            status__in=['enrolled', 'in_progress']
        ).select_related('student').order_by('number_in_group')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        group_id = self.kwargs['group_id']

        # Находим разделы, которые ведет этот преподаватель в данной группе
        instructor_sections = ScheduleItem.objects.filter(
            group_id=group_id,
            instructor=self.request.user.staff
        ).values_list('section_id', flat=True).distinct()

        context['instructor_sections'] = list(instructor_sections)
        return context



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_instructor_grades(request):
    """
    POST /api/execution/instructor/grades/
    Сохраняет оценки от преподавателя с защитой от преждевременного ввода
    и автоматическим созданием системной подписи (ComplianceLog).
    """
    group_id = request.data.get('group_id')
    grades_data = request.data.get('grades', [])

    if not group_id or not grades_data:
        return Response(
            {'error': 'Не указаны group_id или grades'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    # Проверяем, что преподаватель имеет право редактировать эти разделы
    allowed_sections = ScheduleItem.objects.filter(
        group_id=group_id,
        instructor=staff
    ).values_list('section_id', flat=True)

    ip_address = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() or request.META.get('REMOTE_ADDR')
    saved_count = 0

    for grade_item in grades_data:
        enrollment_id = grade_item.get('enrollment_id')
        section_id = grade_item.get('section_id')
        score = grade_item.get('score')
        notes = grade_item.get('notes', '')

        # 1. Проверяем права
        if section_id not in allowed_sections:
            return Response(
                {'error': f'Раздел ID {section_id} не назначен вам для группы {group_id}'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 2. ЗАЩИТА: Проверка времени занятия перед сохранением оценки
        schedule_item = ScheduleItem.objects.filter(group_id=group_id, section_id=section_id).first()
        if schedule_item and schedule_item.date:
            # Склеиваем дату и время начала занятия в один datetime объект
            if schedule_item.start_time:
                schedule_dt = datetime.combine(schedule_item.date, schedule_item.start_time)
            else:
                # Если время не указано, используем начало дня (00:00)
                schedule_dt = datetime.combine(schedule_item.date, datetime.min.time())

            # Делаем время "осознанным" (aware) для корректного сравнения
            if timezone.is_naive(schedule_dt):
                schedule_dt = timezone.make_aware(schedule_dt)

            if schedule_dt > timezone.now():
                section_title = schedule_item.section.title if schedule_item.section else f"Раздел {section_id}"
                time_str = schedule_dt.strftime("%d.%m.%Y %H:%M")
                return Response({
                    'error': f'Нельзя выставить оценку по разделу "{section_title}". '
                             f'Время занятия ({time_str}) еще не наступило.'
                }, status=status.HTTP_400_BAD_REQUEST)

        # 3. Находим или создаем оценку
        assessment, created = Assessment.objects.get_or_create(
            enrollment_id=enrollment_id,
            section_id=section_id,
            attempt_number=1,
            defaults={
                'score': score,
                'notes': notes,
                'instructor': staff,
                'assessment_date': timezone.localdate()
            }
        )

        if not created:
            # Обновляем существующую оценку
            assessment.score = score
            assessment.notes = notes
            assessment.instructor = staff
            assessment.assessment_date = timezone.localdate()
            assessment.save()

        # 4. НОВОЕ: Создание ComplianceLog (системной подписи)
        existing_log = ComplianceLog.objects.filter(
            enrollment_id=enrollment_id,
            staff=staff,
            action_type='grades_submitted',
            assessment=assessment
        ).first()

        if not existing_log:
            ComplianceLog.objects.create(
                enrollment_id=enrollment_id,
                staff=staff,
                action_type='grades_submitted',
                assessment=assessment,
                ip_address=ip_address,
                notes='Оценки внесены инструктором через API'
            )

        saved_count += 1

    return Response({
        'message': f'Успешно сохранено оценок: {saved_count}',
        'saved_count': saved_count
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def log_schedule_action(request, pk):
    """
    POST /api/instructor/schedule/<pk>/log/
    Фиксирует действие преподавателя с проверкой времени.
    """
    try:
        schedule_item = ScheduleItem.objects.get(pk=pk, instructor=request.user.staff)
    except ScheduleItem.DoesNotExist:
        return Response({'error': 'Занятие не найдено или вы не назначены инструктором'},
                        status=status.HTTP_404_NOT_FOUND)

    # === ПРОВЕРКА ВРЕМЕНИ (с учетом локации группы) ===
    from execution.utils import check_schedule_time_allowed

    is_allowed, error_msg = check_schedule_time_allowed(schedule_item)
    if not is_allowed:
        return Response({'error': error_msg}, status=status.HTTP_400_BAD_REQUEST)
    # ==================================================

    action_type = request.data.get('action_type')
    valid_actions = ['instructor_familiarized', 'grades_submitted', 'lesson_completed']

    if action_type not in valid_actions:
        return Response({'error': 'Недопустимый тип действия'}, status=status.HTTP_400_BAD_REQUEST)

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')

    log = ComplianceLog.objects.create(
        schedule_item=schedule_item,
        staff=request.user.staff,
        action_type=action_type,
        ip_address=ip,
        notes=request.data.get('notes', '')
    )

    if action_type == 'lesson_completed':
        schedule_item.is_completed = True
        schedule_item.save(update_fields=['is_completed'])

    return Response({
        'message': 'Действие успешно зафиксировано',
        'signature': log.signature_string,
        'is_completed': schedule_item.is_completed
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def instructor_groups_view(request):
    """
    GET /api/instructor/groups/
    Возвращает данные, сгруппированные по группам, для аккордеона инструктора.
    ИСКЛЮЧАЕТ завершенные группы.
    """
    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    # Находим все группы, где этот инструктор ведет занятия, ИСКЛЮЧАЯ завершенные
    group_ids = ScheduleItem.objects.filter(instructor=staff).values_list('group_id', flat=True).distinct()
    groups = Group.objects.filter(id__in=group_ids).exclude(status='completed').select_related('module')

    result = []
    for group in groups:
        # 1. Документ расписания и ознакомление инструктора
        schedule_doc_url = request.build_absolute_uri(f"/docs/schedule/{group.id}/")

        schedule_ack = ComplianceLog.objects.filter(
            staff=staff,
            action_type='instructor_schedule_ack',
            notes__contains=f"Группа ID: {group.id}"
        ).first()

        if not schedule_ack:
            schedule_ack = ComplianceLog.objects.filter(
                schedule_item__group=group,
                staff=staff,
                action_type='instructor_schedule_ack'
            ).first()

        # 1.1. Проверка: проводился ли инструктаж по ТБ в этой группе (методистом или кем-то еще)
        group_has_safety_ack = ComplianceLog.objects.filter(
            enrollment__group=group,
            action_type='student_safety_ack'
        ).exists()

        # 2. Студенты группы с их оценками и статусом инструктажа
        enrollments = Enrollment.objects.filter(group=group).select_related('student').order_by('number_in_group')
        students_data = []

        for enr in enrollments:
            # --- Промежуточные оценки ---
            inter_assessments = Assessment.objects.filter(
                enrollment=enr
            ).exclude(
                section__title__icontains='итогов'
            ).exclude(
                section__title__icontains='экзамен'
            ).exclude(
                section__title__icontains='итоговая'
            ).select_related('section')

            inter_grades = []
            for assessment in inter_assessments:
                score_display = assessment.score
                grade_type = assessment.section.grade_type if assessment.section else 'numeric'

                if grade_type == 'binary':
                    if assessment.score == 1:
                        score_display = 'Зачет'
                    elif assessment.score == 0:
                        score_display = 'Не зачет'
                    else:
                        score_display = assessment.score

                inter_grades.append({
                    'section_title': assessment.section.title if assessment.section else None,
                    'score': score_display,
                    'passed': assessment.passed,
                    'section_grade_type': grade_type,
                })

            # --- ИТОГОВАЯ ОЦЕНКА ---
            final_section = Section.objects.filter(
                stage__module=group.module
            ).filter(
                Q(title__icontains='итогов') | Q(title__icontains='экзамен') | Q(title__icontains='итоговая')
            ).first()

            final_assessment = None
            if final_section:
                final_assessment = Assessment.objects.filter(
                    enrollment=enr,
                    section=final_section
                ).first()

            # --- Статус инструктажа для этого студента ---
            briefing_log = ComplianceLog.objects.filter(
                enrollment=enr,
                action_type='instructor_briefing_done'  # Проверяем любой лог инструктажа, не только текущего staff
            ).first()

            students_data.append({
                'enrollment_id': enr.id,
                'student_name': f"{enr.student.surname} {enr.student.name} {enr.student.patronymic or ''}".strip(),
                'number': enr.number_in_group,
                'intermediate_grades': inter_grades,
                'final_section_id': final_section.id if final_section else None,
                'final_section_title': final_section.title if final_section else None,
                'final_score': final_assessment.score if final_assessment else None,
                'final_grade_type': final_section.grade_type if final_section else 'numeric',
                'final_passed': final_assessment.passed if final_assessment else None,
                'briefing_done': briefing_log is not None,
                'briefing_date': briefing_log.timestamp if briefing_log else None
            })

        # 3. Занятия (расписание) этой группы
        schedule_items = ScheduleItem.objects.filter(group=group, instructor=staff).select_related('section',
                                                                                                   'subsection').order_by(
            'date', 'start_time')
        classes_data = []
        for item in schedule_items:
            completion_log = ComplianceLog.objects.filter(
                schedule_item=item, staff=staff, action_type='lesson_completed'
            ).first()
            classes_data.append({
                'id': item.id,
                'date': item.date,
                'time': f"{item.start_time}-{item.end_time}" if item.start_time else "СДО",
                'section_title': item.section.title if item.section else "Занятие",
                'subsection_title': item.subsection.title if item.subsection else "",
                'is_completed': item.is_completed,
                'completion_signature': completion_log.signature_string if completion_log else None
            })

        result.append({
            'group_id': group.id,
            'group_number': group.assigned_number,
            'module_title': group.module.title,
            'status': group.status,
            'group_has_safety_ack': group_has_safety_ack,  # <-- НОВОЕ ПОЛЕ
            'schedule_doc': {
                'url': schedule_doc_url,
                'has_ack': schedule_ack is not None,
                'ack_date': schedule_ack.timestamp if schedule_ack else None
            },
            'students': students_data,
            'classes': classes_data
        })

    return Response(result)


# ==============================================================================
# НОВЫЙ ЭНДПОИНТ: ЗАВЕРШЕНИЕ ГРУППЫ С ВАЛИДАЦИЕЙ
# ==============================================================================
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def instructor_complete_group(request, group_id):
    """
    POST /api/instructor/groups/<group_id>/complete/
    Проверяет готовность группы к завершению: ВСЕ инструкторы должны завершить занятия и оценки.
    """
    try:
        instructor = request.user.staff
        group = Group.objects.get(id=group_id)
    except Group.DoesNotExist:
        return Response({'error': 'Группа не найдена'}, status=status.HTTP_404_NOT_FOUND)
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    missing_items = []

    # ======================================================================
    # 1. Проверка инструктажа по ТБ (ВСЕ студенты должны подтвердить)
    # ======================================================================
    total_students = Enrollment.objects.filter(group=group).count()
    students_with_safety_ack = ComplianceLog.objects.filter(
        enrollment__group=group,
        action_type='student_safety_ack'
    ).values('enrollment').distinct().count()

    if students_with_safety_ack < total_students:
        missing_count = total_students - students_with_safety_ack
        missing_items.append(
            f"Не все слушатели подтвердили инструктаж по ОТ, ТБ и ППБ "
            f"({missing_count} из {total_students} не ознакомились)."
        )

    # ======================================================================
    # 2. НОВОЕ: Проверка ВСЕХ инструкторов группы (не только текущего)
    # ======================================================================
    # Находим всех уникальных инструкторов, назначенных на занятия этой группы
    all_instructors = ScheduleItem.objects.filter(
        group=group,
        instructor__isnull=False
    ).values_list('instructor', flat=True).distinct()

    # Для каждого инструктора проверяем незавершенные занятия
    for instructor_id in all_instructors:
        try:
            staff_member = Staff.objects.get(id=instructor_id)
        except Staff.DoesNotExist:
            continue

        # Считаем незавершенные занятия этого инструктора
        pending_sessions = ScheduleItem.objects.filter(
            group=group,
            instructor=staff_member,
            is_completed=False
        ).count()

        if pending_sessions > 0:
            missing_items.append(
                f"Инструктор {staff_member.full_name} не завершил {pending_sessions} занятий."
            )

    # ======================================================================
    # 3. Проверка итоговых оценок (ВСЕХ студентов, независимо от инструктора)
    # ======================================================================

    print(f"\n🔍 ПРОВЕРКА ИТОГОВЫХ ОЦЕНОК для группы {group.id}:")

    # 3.1. Ищем именно ИТОГОВЫЕ разделы (строгий фильтр)
    true_final_sections = Section.objects.filter(
        stage__module=group.module
    ).filter(
        Q(title__icontains='итоговая') |
        Q(title__icontains='экзамен') |
        Q(title__icontains='аттестац')
    ).distinct()

    # Если строгий фильтр ничего не дал, используем расширенный, НО исключаем слово "промежуточная"
    if not true_final_sections.exists():
        true_final_sections = Section.objects.filter(
            stage__module=group.module
        ).filter(
            Q(title__icontains='итогов') |
            Q(title__icontains='оценка знаний')
        ).exclude(
            title__icontains='промежуточная'  # Ключевое исправление!
        ).distinct()

    print(f"  - Найдено итоговых разделов для проверки: {true_final_sections.count()}")
    for fs in true_final_sections:
        print(f"    • {fs.title} (ID: {fs.id})")

    if true_final_sections.exists():
        total_students = Enrollment.objects.filter(group=group).count()

        # Считаем количество УНИКАЛЬНЫХ студентов, у которых ЕСТЬ оценка (score не null) в итоговых разделах
        students_with_final_grade = Assessment.objects.filter(
            enrollment__group=group,
            section__in=true_final_sections,
            score__isnull=False
        ).values('enrollment').distinct().count()

        missing_grades = total_students - students_with_final_grade

        print(f"  - Всего студентов: {total_students}")
        print(f"  - Студентов с выставленной итоговой оценкой: {students_with_final_grade}")
        print(f"  - Отсутствует итоговых оценок: {missing_grades}")

        if missing_grades > 0:
            section_names = ", ".join([s.title for s in true_final_sections])
            missing_items.append(
                f"Не выставлены итоговые оценки ({missing_grades} из {total_students} слушателей). "
                f"Проверьте разделы: {section_names}"
            )
    else:
        print(f"  ⚠️ В модуле '{group.module.title}' не найдено итоговых разделов для проверки!")
        missing_items.append(
            f"В модуле '{group.module.title}' не найден итоговый раздел. Невозможно проверить оценки."
        )

    print("")  # Пустая строка для читаемости

    # ======================================================================
    # 4. Если есть ошибки — возвращаем список
    # ======================================================================
    if missing_items:
        return Response({
            'error': 'Невозможно завершить группу. Не выполнены следующие условия:',
            'missing_items': missing_items
        }, status=status.HTTP_400_BAD_REQUEST)

    # ======================================================================
    # 5. Если всё отлично — завершаем группу
    # ======================================================================
    group.status = 'completed'
    group.save(update_fields=['status'])

    return Response({
        'message': 'Группа успешно завершена и передана методисту для архивации и печати документов.'
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def instructor_log_action(request):
    action_type = request.data.get('action_type')
    valid_actions = ['instructor_schedule_ack', 'instructor_briefing_done']

    if action_type not in valid_actions:
        return Response({'error': f'Недопустимое действие: {action_type}'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        staff = request.user.staff
    except ObjectDoesNotExist:
        return Response({'error': 'Профиль сотрудника не найден'}, status=status.HTTP_403_FORBIDDEN)

    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')

    log_data = {
        'staff': staff,
        'action_type': action_type,
        'ip_address': ip,
        'notes': request.data.get('notes', '')
    }

    try:
        if action_type == 'instructor_schedule_ack':
            group_id = request.data.get('group_id')
            log_data['notes'] = f"Группа ID: {group_id}. " + log_data['notes']

        elif action_type == 'instructor_briefing_done':
            enrollment_id = request.data.get('enrollment_id')
            enrollment = Enrollment.objects.get(pk=enrollment_id)
            log_data['enrollment'] = enrollment

            # Для порядка привяжем лог к первому занятию этой группы
            first_item = ScheduleItem.objects.filter(group=enrollment.group).first()
            if first_item:
                log_data['schedule_item'] = first_item

        ComplianceLog.objects.create(**log_data)
        return Response({'message': 'Действие успешно зафиксировано'}, status=status.HTTP_200_OK)

    except Enrollment.DoesNotExist:
        return Response({'error': 'Назначение (enrollment) не найдено'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """Смена пароля пользователя"""
    old_password = request.data.get('old_password')
    new_password = request.data.get('new_password')

    if not old_password or not new_password:
        return Response({'error': 'Укажите старый и новый пароль'}, status=status.HTTP_400_BAD_REQUEST)

    if len(new_password) < 8:
        return Response({'error': 'Пароль должен содержать минимум 8 символов'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    if not user.check_password(old_password):
        return Response({'error': 'Неверный старый пароль'}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    # Обновляем last_login, чтобы модалка больше не показывалась при первом входе
    from django.utils import timezone
    user.last_login = timezone.now()
    user.save(update_fields=['last_login'])

    return Response({'success': 'Пароль успешно изменен'}, status=status.HTTP_200_OK)




class StudentCreateAPIView(generics.CreateAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentCreateSerializer
    permission_classes = [IsAuthenticated]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Возвращаем успешный ответ с данными
        return Response({
            "message": "Слушатель успешно создан",
            "student": serializer.data
        }, status=status.HTTP_201_CREATED)