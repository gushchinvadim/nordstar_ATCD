# docs/views.py
import json
import re
from datetime import date, datetime
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMessage
from django.db import models
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from weasyprint import HTML
from execution.models import Group, Enrollment, ScheduleItem, Assessment
from people.models import Staff
from training.models import Section, Stage
import os
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required  # или staff_member_required, как у вас принято
from django.http import FileResponse, HttpResponse
from django.contrib import messages
from execution.models import Group, Enrollment
from docs.services.document_registry import DocumentRegistry
from docs.services.document_storage import DocumentStorageService
from .utils import get_logo_base64, get_exam_date_for_enrollment


@staff_member_required
def group_grades_view(request, group_id):
    """Журнал оценок группы — табличный ввод"""
    group = get_object_or_404(Group, id=group_id)

    students = Enrollment.objects.filter(
        group=group,
        status__in=['enrolled', 'in_progress', 'completed', 'dismissed']  # Добавили dismissed, чтобы видеть отчисленных
    ).select_related('student', 'student__profession').order_by('number_in_group')

    sections = Section.objects.filter(
        stage__module=group.module,
        grade_type__in=['numeric', 'binary']
    ).order_by('stage__order', 'order')

    instructors_from_schedule = Staff.objects.filter(
        scheduleitem__group=group
    ).distinct().order_by('full_name')

    # Получаем даты из расписания для подстановки по умолчанию
    schedule_dates = {}
    for section_id, date_val in ScheduleItem.objects.filter(
            group=group, section__in=sections
    ).values_list('section_id', 'date'):
        if section_id not in schedule_dates:  # Берем первую дату для раздела
            schedule_dates[section_id] = date_val

    if request.method == 'POST':
        saved_count = 0

        for enrollment in students:
            for section in sections:
                score_key = f'score_{enrollment.id}_{section.id}'
                date_key = f'date_{enrollment.id}_{section.id}'
                instructor_key = f'instructor_{enrollment.id}_{section.id}'

                score_value = request.POST.get(score_key, '').strip()
                date_value = request.POST.get(date_key, '').strip()
                instructor_id = request.POST.get(instructor_key, '').strip()

                if score_value == '':
                    continue

                try:
                    score = int(float(score_value))
                except (ValueError, TypeError):
                    continue

                # Обработка даты
                assessment_date = None
                if date_value:
                    try:
                        assessment_date = datetime.strptime(date_value, '%Y-%m-%d').date()
                    except ValueError:
                        pass

                if not assessment_date:
                    assessment_date = schedule_dates.get(section.id) or date.today()

                # Инструктор
                instructor = None
                if instructor_id:
                    try:
                        instructor = Staff.objects.get(id=instructor_id)
                    except Staff.DoesNotExist:
                        pass

                if not instructor:
                    schedule_item = ScheduleItem.objects.filter(group=group, section=section).select_related(
                        'instructor').first()
                    if schedule_item and schedule_item.instructor:
                        instructor = schedule_item.instructor

                assessment, created = Assessment.objects.get_or_create(
                    enrollment=enrollment, section=section, attempt_number=1,
                    defaults={'score': score, 'assessment_type': 'test', 'assessment_date': assessment_date,
                              'instructor': instructor}
                )

                if not created:
                    assessment.score = score
                    assessment.assessment_date = assessment_date
                    assessment.instructor = instructor
                    assessment.save()

                saved_count += 1

        messages.success(request, f'Сохранено оценок: {saved_count}')
        return redirect('docs:group_grades', group_id=group.id)

    # Подготовка данных
    students_data = []
    for enrollment in students:
        assessments_dict = {}
        for assessment in enrollment.assessments.filter(attempt_number=1).select_related('instructor'):
            assessments_dict[assessment.section_id] = assessment

        assessments_list = []
        for section in sections:
            assessment = assessments_dict.get(section.id)
            instructor = assessment.instructor if assessment else None
            if not instructor:
                schedule_item = ScheduleItem.objects.filter(group=group, section=section).select_related(
                    'instructor').first()
                if schedule_item and schedule_item.instructor: instructor = schedule_item.instructor

            # Определяем дату: сначала из оценки, потом из расписания
            current_date = assessment.assessment_date if assessment else schedule_dates.get(section.id)

            assessments_list.append({
                'section': section,
                'assessment': assessment,
                'score': int(assessment.score) if assessment and assessment.score is not None else None,
                'has_assessment': assessment is not None,
                'instructor': instructor,
                'current_date': current_date,  # <-- Передаем дату в шаблон
            })

        students_data.append({'enrollment': enrollment, 'assessments_list': assessments_list})

    context = {
        'group': group, 'students_data': students_data, 'students': students,
        'sections': sections, 'instructors': instructors_from_schedule, 'today': date.today(),
    }
    return render(request, 'docs/grades/group_grades.html', context)


@staff_member_required
@require_POST
def complete_enrollment(request, enrollment_id):
    """Индивидуальное завершение обучения"""
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)

    if enrollment.check_all_sections_passed():
        exam_date = get_exam_date_for_enrollment(enrollment)

        # Проверяем: есть ли завершённые студенты с ДРУГОЙ датой?
        other_date_completed = Enrollment.objects.filter(
            group=enrollment.group,
            status='completed'
        ).exclude(order_out_date=exam_date).exists()

        if other_date_completed:
            # Есть студенты с другой датой → индивидуальный приказ с суффиксом
            enrollment.status = 'completed'
            enrollment.completed_at = exam_date
            enrollment.final_result = 'passed'
            enrollment.order_out_number = enrollment.generate_order_out_number('completed', is_individual=True)
            enrollment.order_out_date = exam_date
            enrollment.save()

            messages.success(request, f'{enrollment.student} завершил обучение. Приказ: {enrollment.order_out_number}')
        else:
            # Все в один день (или первый) → групповой приказ
            same_day_completed = Enrollment.objects.filter(
                group=enrollment.group,
                status='completed',
                order_out_date=exam_date
            ).first()

            if same_day_completed:
                # Берём номер у первого в этот день
                enrollment.status = 'completed'
                enrollment.completed_at = exam_date
                enrollment.final_result = 'passed'
                enrollment.order_out_number = same_day_completed.order_out_number
                enrollment.order_out_date = exam_date
                enrollment.save()
            else:
                # Первый в этот день - создаём групповой номер
                enrollment.status = 'completed'
                enrollment.completed_at = exam_date
                enrollment.final_result = 'passed'
                enrollment.order_out_number = enrollment.generate_order_out_number('completed', is_individual=False)
                enrollment.order_out_date = exam_date
                enrollment.save()

            messages.success(request, f'{enrollment.student} завершил обучение. Приказ: {enrollment.order_out_number}')

        check_and_close_group(enrollment.group)
    else:
        messages.error(request, f'{enrollment.student} не сдал все разделы')

    return redirect('docs:group_grades', group_id=enrollment.group.id)


@staff_member_required
@require_POST
def complete_all_enrollments(request, group_id):
    """Массовое завершение обучения для всех, кто сдал"""
    group = get_object_or_404(Group, id=group_id)
    count = 0

    for enrollment in Enrollment.objects.filter(group=group, status__in=['enrolled', 'in_progress']):
        if enrollment.check_all_sections_passed():
            exam_date = get_exam_date_for_enrollment(enrollment)

            # Проверяем: есть ли завершённые с ДРУГОЙ датой?
            other_date_completed = Enrollment.objects.filter(
                group=group,
                status='completed'
            ).exclude(order_out_date=exam_date).exists()

            enrollment.status = 'completed'
            enrollment.completed_at = exam_date
            enrollment.final_result = 'passed'

            if other_date_completed:
                # Индивидуальный приказ
                enrollment.order_out_number = enrollment.generate_order_out_number('completed', is_individual=True)
            else:
                # Групповой приказ - проверяем, есть ли уже в этот день
                same_day_completed = Enrollment.objects.filter(
                    group=group,
                    status='completed',
                    order_out_date=exam_date
                ).first()

                if same_day_completed:
                    enrollment.order_out_number = same_day_completed.order_out_number
                else:
                    enrollment.order_out_number = enrollment.generate_order_out_number('completed', is_individual=False)

            enrollment.order_out_date = exam_date
            enrollment.save()
            count += 1

    if count > 0:
        check_and_close_group(group)
        messages.success(request, f'Успешно завершили обучение: {count} чел.')
    else:
        messages.warning(request, 'Нет студентов, готовых к завершению')

    return redirect('docs:group_grades', group_id=group.id)


def check_and_close_group(group):
    """Автоматически меняет статус группы на completed, если все студенты обработаны"""
    total = Enrollment.objects.filter(group=group).count()
    if total == 0: return

    finished = Enrollment.objects.filter(group=group, status__in=['completed', 'dismissed']).count()
    if total == finished:
        group.status = 'completed'  # Убедитесь, что такой статус есть в Group.STATUS_CHOICES
        group.save()


@staff_member_required
@require_POST
def dismiss_enrollments(request, group_id):
    """Массовое отчисление по неуспеваемости"""
    group = get_object_or_404(Group, id=group_id)

    to_dismiss = Enrollment.objects.filter(
        group=group,
        status__in=['enrolled', 'in_progress']
    )

    count = 0
    for enrollment in to_dismiss:
        enrollment.status = 'dismissed'
        # Дата отчисления = дата принятия решения (сегодня)
        enrollment.dismissal_date = date.today()
        enrollment.dismissal_reason = 'Неуспеваемость (истёк срок обучения)'
        enrollment.order_out_number = enrollment.generate_order_out_number('dismissed')
        enrollment.order_out_date = date.today()  # ← Оставляем сегодня, это дата решения
        enrollment.save()
        count += 1

    messages.success(request, f'Отчислено студентов: {count}')
    check_and_close_group(group)
    return redirect('docs:group_grades', group_id=group.id)

@staff_member_required
def land_training_task_view(request, group_id):
    """Задание на тренировку АСП Суша"""
    from docs.utils import get_logo_base64

    group = get_object_or_404(Group, id=group_id)

    # Получаем всех зачисленных студентов
    enrollments = Enrollment.objects.filter(
        group=group
    ).select_related('student', 'student__profession').order_by('number_in_group')

    # Находим инструктора АСП Суша из расписания
    instructor = None
    asp_item = ScheduleItem.objects.filter(
        group=group,
        session_type='asp-l'
    ).select_related('instructor').first()

    if asp_item and asp_item.instructor:
        instructor = asp_item.instructor.full_name

    # Получаем тип ВС
    aircraft_type = group.module.aircraft_type if group.module else None

    # ← ДИНАМИЧЕСКИЙ ВЫБОР ШАБЛОНА
    module_code = (group.module.code or "").upper() if group.module else ""
    if '01' in module_code or 'C1' in module_code:
        template_name = 'docs/training_tasks/course_1/land_training_task.html'
    else:
        template_name = 'docs/training_tasks/course_2/land_training_task.html'

    context = {
        'group': group,
        'enrollments': enrollments,
        'instructor_name': instructor,
        'aircraft_type': aircraft_type,
        'logo_base64': get_logo_base64(),
    }

    return render(request, template_name, context)


@staff_member_required
def water_training_task_view(request, group_id):
    """Задание на тренировку АСП Вода"""
    from docs.utils import get_logo_base64

    group = get_object_or_404(Group, id=group_id)

    # Получаем всех зачисленных студентов
    enrollments = Enrollment.objects.filter(
        group=group
    ).select_related('student', 'student__profession').order_by('number_in_group')

    # Находим инструктора АСП Вода из расписания
    instructor = None
    asp_item = ScheduleItem.objects.filter(
        group=group,
        session_type='asp-w'
    ).select_related('instructor').first()

    if asp_item and asp_item.instructor:
        instructor = asp_item.instructor.full_name

    # Получаем тип ВС
    aircraft_type = group.module.aircraft_type if group.module else None

    # ← ДИНАМИЧЕСКИЙ ВЫБОР ШАБЛОНА
    module_code = (group.module.code or "").upper() if group.module else ""
    if '01' in module_code or 'C1' in module_code:
        template_name = 'docs/training_tasks/course_1/water_training_task.html'
    else:
        template_name = 'docs/training_tasks/course_2/water_training_task.html'

    context = {
        'group': group,
        'enrollments': enrollments,
        'instructor_name': instructor,
        'aircraft_type': aircraft_type,
        'logo_base64': get_logo_base64(),
    }

    return render(request, template_name, context)

def _build_attendance_by_stage(group):
    """Формирует структуру посещаемости: этапы → даты очных занятий"""
    # Берём только очные занятия (не SDO), отсортированные по дате
    items = ScheduleItem.objects.filter(
        group=group,
        session_type__in=['base-1', 'base-2', 'base-3', 'base-4',
                          'base-5', 'base-6', 'base-7', 'base-8', 'base-9', 'sim']
    ).select_related('section', 'section__stage').order_by(
        'section__stage__order', 'section__order', 'date'
    )

    stages_dict = {}
    for item in items:
        stage = item.section.stage
        if stage.id not in stages_dict:
            stages_dict[stage.id] = {
                'stage': stage,
                'stage_title': stage.title,
                'dates': [],
            }

        # Проверяем, нет ли уже такой даты в этом этапе
        date_exists = any(d['date'] == item.date for d in stages_dict[stage.id]['dates'])
        if not date_exists:
            stages_dict[stage.id]['dates'].append({
                'date': item.date,
                'date_display': item.date.strftime('%d.%m.%Y'),
                'section_title': item.section.title,
            })

    # Сортируем этапы по order и даты внутри этапов
    stages_list = sorted(stages_dict.values(), key=lambda x: x['stage'].order)
    for stage_data in stages_list:
        stage_data['dates'].sort(key=lambda x: x['date'])

    return stages_list


def _build_thematic_plan(group, rows_per_page=22):
    """Формирует постраничный тематический план"""
    items = ScheduleItem.objects.filter(
        group=group
    ).select_related(
        'section', 'section__stage', 'subsection',
        'instructor', 'classroom'
    ).order_by('section__stage__order', 'section__order', 'subsection__order')

    rows = []
    prev_stage_id = None
    stage_items_cache = {}  # кэш для подсчёта итогов по этапу

    # Предварительно считаем часы по этапам
    for item in items:
        stage_id = item.section.stage.id
        if stage_id not in stage_items_cache:
            stage_items_cache[stage_id] = {
                'stage': item.section.stage,
                'total_hours': 0,
            }
        hours = float(
            item.subsection.duration_hours if item.subsection and item.subsection.duration_hours else item.section.duration_hours)
        stage_items_cache[stage_id]['total_hours'] += hours

    number = 1
    for item in items:
        stage = item.section.stage
        is_first_of_stage = (prev_stage_id != stage.id)

        # Проверяем, последний ли это элемент этапа
        # (следующий item имеет другой stage или это последний item)
        is_last_of_stage = False

        hours = float(
            item.subsection.duration_hours if item.subsection and item.subsection.duration_hours else item.section.duration_hours)

        # Формируем время
        time_str = ''
        if item.start_time and item.end_time:
            time_str = f"{item.start_time.strftime('%H:%M')} – {item.end_time.strftime('%H:%M')}"
        elif item.session_type == 'sdo':
            time_str = '09:00'

        # Место проведения
        location = ''
        if item.session_type == 'sdo':
            location = 'СДО (ispringlearn.ru)'
        elif item.classroom:
            parts = []

            # Добавляем название организации
            if item.classroom.organization:
                parts.append(item.classroom.organization.company_name)

            # Добавляем адрес (используем full_address)
            if item.classroom.full_address:
                parts.append(item.classroom.full_address)

            # Добавляем название и аудиторию
            classroom_details = []
            if item.classroom.title:
                classroom_details.append(item.classroom.title)
            if item.classroom.audience:
                classroom_details.append(f"ауд. {item.classroom.audience}")

            if classroom_details:
                parts.append(', '.join(classroom_details))

            location = '\n'.join(parts)

        # Инструктор
        instructor = item.instructor.full_name if item.instructor else ''

        rows.append({
            'number': number,
            'title': item.section.title,
            'subtitle': item.subsection.title if item.subsection else '',
            'hours': hours,
            'location': location,
            'date': item.date.strftime('%d.%m.%Y') if item.date else '',
            'start_time': time_str,
            'instructor': instructor,
            'is_first_of_stage': is_first_of_stage,
            'is_last_of_stage': False,
            'stage': stage,
            'stage_total_hours': stage_items_cache[stage.id]['total_hours'],  # ← ДОБАВЛЕНО
        })

        prev_stage_id = stage.id
        number += 1

    # Помечаем последние элементы этапов
    for i, row in enumerate(rows):
        if i + 1 < len(rows):
            if rows[i + 1]['stage'].id != row['stage'].id:
                row['is_last_of_stage'] = True
        else:
            row['is_last_of_stage'] = True

    # Разбиваем на страницы
    pages = []
    current_page_rows = []
    for row in rows:
        current_page_rows.append(row)
        if len(current_page_rows) >= rows_per_page:
            pages.append({'rows': current_page_rows})
            current_page_rows = []
    if current_page_rows:
        pages.append({'rows': current_page_rows})

    # Считаем общие часы модуля
    module_total_hours = sum(s['total_hours'] for s in stage_items_cache.values())

    return pages, module_total_hours


def _split_attendance_into_pages(attendance_by_stage, max_dates_per_page=14):
    """Разбивает структуру посещаемости на страницы по max_dates_per_page дат"""
    if not attendance_by_stage:
        return []

    # Собираем все даты в плоский список, сохраняя привязку к этапам
    all_dates = []
    for stage_data in attendance_by_stage:
        for date_info in stage_data['dates']:
            all_dates.append({
                'stage_title': stage_data['stage_title'],
                'date': date_info['date'],
                'date_display': date_info['date_display'],
                'section_title': date_info['section_title'],
            })

    # Разбиваем на страницы
    pages = []
    for i in range(0, len(all_dates), max_dates_per_page):
        page_dates = all_dates[i:i + max_dates_per_page]

        # Группируем даты внутри страницы по этапам (для заголовков)
        page_stages = {}
        for d in page_dates:
            stage_title = d['stage_title']
            if stage_title not in page_stages:
                page_stages[stage_title] = []
            page_stages[stage_title].append(d)

        # Формируем структуру, аналогичную attendance_by_stage
        page_structure = []
        for stage_title, dates in page_stages.items():
            page_structure.append({
                'stage_title': stage_title,
                'dates': dates,
            })

        pages.append(page_structure)

    return pages


def get_journal_context(group):
    """Собирает контекст для журнала (используется и для просмотра, и для сохранения)"""

    students = Enrollment.objects.filter(
        group=group
    ).order_by('number_in_group')

    attendance_by_stage = _build_attendance_by_stage(group)

    # АВТОВЫБОР ОРИЕНТАЦИИ
    total_items_count = ScheduleItem.objects.filter(group=group).count()
    use_landscape = total_items_count > 16

    # Разбивка посещаемости
    if use_landscape:
        attendance_pages = _split_attendance_into_pages(attendance_by_stage, max_dates_per_page=10)
    else:
        attendance_pages = [attendance_by_stage] if attendance_by_stage else []

    # Тематический план
    rows_per_page = 10 if use_landscape else 9
    thematic_plan_pages, module_total_hours = _build_thematic_plan(group, rows_per_page=rows_per_page)

    # === НАЙТИ ИНСТРУКТОРА ИТОГОВОГО ЭКЗАМЕНА ===
    module = group.module
    sections = Section.objects.filter(stage__module=module).order_by('stage__order', 'order')

    # Ищем секцию экзамена
    final_exam_section = next((s for s in sections if
                               'итогов' in s.title.lower() or 'экзамен' in s.title.lower() or 'аттестац' in s.title.lower()),
                              None)

    # Находим инструктора через расписание
    exam_instructor = None
    if final_exam_section:
        exam_schedule = ScheduleItem.objects.filter(
            group=group,
            section=final_exam_section
        ).select_related('instructor').first()

        if exam_schedule and exam_schedule.instructor:
            exam_instructor = exam_schedule.instructor


    # === ПРОВЕРКА НАЛИЧИЯ ЗАДАНИЙ НА ТРЕНИРОВКУ (АСП) ===
    has_asp_training = ScheduleItem.objects.filter(
        group=group,
        session_type__in=['asp-w', 'asp-l']
    ).exists()
    # ====================================================

    num_plan_pages = len(thematic_plan_pages) if thematic_plan_pages else 0
    attendance_count = len(attendance_pages) if attendance_pages else 0

    zk18_pages = 2 + attendance_count + num_plan_pages + 1
    zk13_pages = 1
    zk21_pages = 1


    return {
        'group': group,
        'students': students,
        'attendance_by_stage': attendance_by_stage,
        'attendance_pages': attendance_pages,
        'thematic_plan_pages': thematic_plan_pages,
        'module_total_hours': module_total_hours,
        # 'num_plan_pages': num_plan_pages,
        # 'total_pages': total_pages,
        'total_columns_students': 4,
        'total_columns_attendance': 2 + sum(len(s['dates']) for s in attendance_by_stage),
        'attendance_pages_count': len(attendance_pages),
        'logo_base64': get_logo_base64(),
        'use_landscape': use_landscape,
        'exam_instructor': exam_instructor,  # ← ДОБАВИТЬ

        # НОВЫЕ ПЕРЕМЕННЫЕ ДЛЯ ШАБЛОНА:
        'zk18_pages': zk18_pages,
        'zk13_pages': zk13_pages,
        'zk21_pages': zk21_pages,
        'has_asp_training': has_asp_training,
    }

@staff_member_required
def journal_view(request, group_id):
    """Отображение журнала подготовки группы"""
    group = get_object_or_404(Group, id=group_id)
    context = get_journal_context(group)

    template_name = 'docs/journal/journal_landscape.html' if context['use_landscape'] else 'docs/journal/journal.html'


    return render(request, template_name, context)

@staff_member_required
def send_enrollment_order_email(request, group_id):
    """AJAX: Генерация PDF приказа и отправка на email"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        email_to = data.get('email')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not email_to:
        return JsonResponse({'error': 'Email адрес не указан'}, status=400)

    group = get_object_or_404(Group, id=group_id)

    # 1. Собираем контекст (как в обычном view)
    enrollments = Enrollment.objects.filter(
        group=group,
        status='enrolled'
    ).order_by('number_in_group').select_related('student')

    context = {
        'group': group,
        'enrollments': enrollments,
    }

    # 2. Рендерим HTML в строку
    html_content = render_to_string('docs/orders/enrollment.html', context)

    # 3. Генерируем PDF в памяти (без сохранения на диск)
    try:
        base_url = f'file://{settings.BASE_DIR}/'
        pdf_file = HTML(string=html_content).write_pdf(
            base_url=base_url,
            presentational_hints=True
        )
    except Exception as e:
        return JsonResponse({'error': f'Ошибка генерации PDF: {str(e)}'}, status=500)

    # 4. Формируем и отправляем письмо
    subject = f"Приказ о зачислении - Группа {group.assigned_number}"
    body = (
        f"Добрый день!\n\n"
        f"Во вложении направляю приказ о зачислении группы {group.assigned_number} "
        f"({group.module.code}).\n\n"
        f"С уважением,\nАУЦ"
    )

    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            to=[email_to],
        )
        # Прикрепляем PDF из памяти
        email.attach(f'Приказ_{group.assigned_number}.pdf', pdf_file, 'application/pdf')
        email.send()

        return JsonResponse({
            'success': True,
            'message': f'Письмо успешно отправлено на {email_to}'
        })
    except Exception as e:
        return JsonResponse({'error': f'Ошибка отправки почты: {str(e)}'}, status=500)


@staff_member_required
def save_document_view(request, group_id):
    """AJAX: Сохранение документа в папку группы (только PDF)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    import json
    import os
    from django.conf import settings
    data = json.loads(request.body)
    doc_type = data.get('document_type')

    group = get_object_or_404(Group, id=group_id)
    service = DocumentStorageService(group)

    try:
        # Маппинг типов документов на методы сервиса
        save_methods = {
            'enrollment_order': service.save_enrollment_order,
            'schedule': service.save_schedule,
            'journal': service.save_journal,
            'land_training_task': service.save_land_training_task,
            'water_training_task': service.save_water_training_task,
            'dismissal_ok': service.save_dismissal_ok,
            'dismissal_ot': service.save_dismissal_ot,
            'certificate': service.save_certificate,  # ← Универсальный метод
        }

        if doc_type not in save_methods:
            return JsonResponse({'error': f'Unknown document type: {doc_type}'}, status=400)

        # Вызываем соответствующий метод
        pdf_path = save_methods[doc_type]()

        return JsonResponse({
            'success': True,
            'pdf_path': os.path.relpath(pdf_path, settings.MEDIA_ROOT),
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@staff_member_required
def enrollment_order_view(request, group_id):
    """Отображение приказа о зачислении"""
    group = get_object_or_404(Group, id=group_id)

    # Получаем ВСЕХ студентов группы (независимо от статуса)
    enrollments = Enrollment.objects.filter(
        group=group
    ).order_by('number_in_group').select_related('student')

    context = {
        'group': group,
        'enrollments': enrollments,
        'logo_base64': get_logo_base64(),
    }

    return render(request, 'docs/orders/enrollment.html', context)


@staff_member_required
def schedule_view(request, group_id):
    """Отображение расписания группы"""
    group = get_object_or_404(Group, id=group_id)

    # Явно сортируем занятия по порядку секции и подраздела
    schedule_items = group.schedule.all().order_by(
        'section__stage__order',
        'section__order',
        'subsection__order'
    ).select_related('section', 'subsection', 'section__stage')

    context = {
        'group': group,
        'schedule_items': schedule_items,
        'logo_base64': get_logo_base64(),
    }

    return render(request, 'docs/schedules/schedule.html', context)


@staff_member_required
def send_schedule_email(request, group_id):
    """AJAX: Генерация PDF расписания и отправка на email"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        email_to = data.get('email')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not email_to:
        return JsonResponse({'error': 'Email адрес не указан'}, status=400)

    group = get_object_or_404(Group, id=group_id)

    # 1. Собираем контекст
    context = {
        'group': group,
        'logo_base64': get_logo_base64(),
    }

    # 2. Рендерим HTML в строку
    html_content = render_to_string('docs/schedules/schedule.html', context)

    # 3. Генерируем PDF в памяти
    try:
        base_url = f'file://{settings.BASE_DIR}/'
        pdf_file = HTML(string=html_content).write_pdf(
            base_url=base_url,
            presentational_hints=True
        )
    except Exception as e:
        return JsonResponse({'error': f'Ошибка генерации PDF: {str(e)}'}, status=500)

    # 4. Формируем и отправляем письмо
    subject = f"Расписание - Группа {group.assigned_number}"
    body = (
        f"Добрый день!\n\n"
        f"Во вложении направляю расписание для группы {group.assigned_number} "
        f"({group.module.code}).\n\n"
        f"С уважением,\nАУЦ"
    )

    try:
        email = EmailMessage(
            subject=subject,
            body=body,
            to=[email_to],
        )
        # Прикрепляем PDF из памяти
        email.attach(f'Расписание_{group.assigned_number}.pdf', pdf_file, 'application/pdf')
        email.send()

        return JsonResponse({
            'success': True,
            'message': f'Письмо успешно отправлено на {email_to}'
        })
    except Exception as e:
        return JsonResponse({'error': f'Ошибка отправки почты: {str(e)}'}, status=500)


@staff_member_required
def dismissal_ot_list_view(request, group_id):
    """Список уникальных приказов об отчислении для группы"""
    group = get_object_or_404(Group, id=group_id)

    # 1. Получаем уникальные номера приказов и даты
    orders_data = Enrollment.objects.filter(
        group=group,
        status='dismissed'
    ).exclude(
        order_out_number=''
    ).values('order_out_number', 'order_out_date').distinct().order_by('-order_out_date')

    # 2. Формируем список, сразу подсчитывая студентов для каждого приказа
    orders_list = []
    for order in orders_data:
        count = Enrollment.objects.filter(
            group=group,
            status='dismissed',
            order_out_number=order['order_out_number']
        ).count()

        orders_list.append({
            'order_out_number': order['order_out_number'],
            'order_out_date': order['order_out_date'],
            'student_count': count  # <-- Передаем готовое число
        })

    context = {
        'group': group,
        'orders': orders_list,
    }
    return render(request, 'docs/orders/dismissal_ot_list.html', context)

@staff_member_required
def dismissal_ok_view(request, group_id):
    """Приказ об успешном окончании (ОК)"""
    group = get_object_or_404(Group, id=group_id)
    enrollments = Enrollment.objects.filter(
        group=group,
        status='completed'
    ).select_related('student').order_by('number_in_group')

    # Берем дату приказа из первой записи
    order_date = enrollments.first().order_out_date if enrollments.exists() else date.today()

    context = {
        'group': group,
        'enrollments': enrollments,
        'order_date': order_date,  # ← ОБЯЗАТЕЛЬНО
        'logo_base64': get_logo_base64(),
    }
    return render(request, 'docs/orders/dismissal_ok.html', context)


@staff_member_required
def dismissal_ot_view(request, group_id):
    """Приказ об отчислении (ОТ) по конкретному номеру приказа"""
    from django.http import HttpResponseBadRequest

    group = get_object_or_404(Group, id=group_id)
    order_number = request.GET.get('order_number')

    if not order_number:
        return HttpResponseBadRequest("Не указан номер приказа. Используйте список приказов.")

    # ФИЛЬТРУЕМ строго по номеру приказа!
    enrollments = Enrollment.objects.filter(
        group=group,
        status='dismissed',
        order_out_number=order_number
    ).select_related('student').order_by('number_in_group')

    if not enrollments.exists():
        messages.error(request, "Студенты с таким номером приказа не найдены")
        return redirect('docs:dismissal_ot_list', group_id=group_id)

    order_date = enrollments.first().order_out_date

    context = {
        'group': group,
        'enrollments': enrollments,
        'order_date': order_date,
        'order_number': order_number,  # Передаем в шаблон
        'logo_base64': get_logo_base64(),
    }
    return render(request, 'docs/orders/dismissal_ot.html', context)


@staff_member_required
def download_document(request, file_path):
    """
    Скачивание документа из папки группы.
    URL: /docs/download/documents/2026/groups/008.2026/orders/Приказ_ОК.pdf
    """
    # Проверяем, что путь начинается с documents/ (защита от path traversal)
    if not file_path.startswith('documents/'):
        raise Http404("Недопустимый путь к файлу")

    # Полный путь к файлу
    full_path = os.path.join(settings.MEDIA_ROOT, file_path)

    # Проверяем существование файла
    if not os.path.exists(full_path):
        raise Http404("Файл не найден")

    # Определяем MIME-тип
    if file_path.endswith('.pdf'):
        content_type = 'application/pdf'
    elif file_path.endswith('.html'):
        content_type = 'text/html'
    else:
        content_type = 'application/octet-stream'

    # Извлекаем имя файла для заголовка Content-Disposition
    filename = os.path.basename(file_path)

    response = FileResponse(
        open(full_path, 'rb'),
        content_type=content_type,
        as_attachment=True,
        filename=filename
    )

    return response


@staff_member_required
@require_POST
def generate_all_documents(request, group_id):
    """Массовая генерация всех активных документов"""
    group = get_object_or_404(Group, id=group_id)
    service = DocumentStorageService(group)

    generated = []
    errors = []

    for doc_key, doc_info in DocumentRegistry.get_active_documents().items():
        try:
            method = getattr(service, doc_info['save_method'], None)
            if method:
                method()  # Вызываем метод сохранения
                generated.append(doc_info['name'])
        except Exception as e:
            errors.append(f"{doc_info['name']}: {str(e)}")

    if generated:
        messages.success(request, f'Сгенерировано документов: {len(generated)}')
    if errors:
        messages.error(request, f'Ошибки: {"; ".join(errors)}')


    return redirect('docs:documents_dashboard', group_id=group_id)



@staff_member_required
def group_documents_dashboard(request, group_id):
    """Единая панель управления документами группы"""
    group = get_object_or_404(Group, id=group_id)

    # 1. Сканируем папку и собираем файлы с ПРАВИЛЬНЫМИ путями
    saved_files = []

    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'

    group_folder_name = f"documents/{year}/groups/{module_code}/{group.assigned_number}"
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

                        saved_files.append({
                            'filename': file,
                            'lower_name': file.lower(),
                            'full_path': full_relative_path,
                        })

    # 2. Правила сопоставления
    doc_identifiers = {
        'enrollment_order': ['зачисл', 'enrollment', '-сз', '_сз', '-з.pdf'],
        'dismissal_ok': ['_ок', '-ок', '_ok', '-ok', 'оконч'],
        'dismissal_ot': ['_от', '-от', '_ot', '-ot', 'отчисл'],
        'journal': ['журнал', 'journal'],
        'schedule': ['распис', 'schedule'],
        'land_training_task': ['суша', 'land', 'asp-l', 'суш'],
        'water_training_task': ['вода', 'water', 'asp-w', 'вод'],
        'certificate': ['удостовер', 'модуль', 'certificate', 'cert'],
    }

    # 3. Сопоставляем файлы с типами документов
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

        documents_list.append({
            'key': doc_key,
            'name': doc_info['name'],
            'icon': doc_info['icon'],
            'status': doc_info['status'],
            'is_saved': is_saved,
            'saved_file_path': saved_file_path,
            'view_url': reverse(doc_info['view_name'], args=[group_id]) if doc_info['view_name'] else None,
        })

    # === ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ РАУЦ ===
    reports_folder = os.path.join(expected_base, 'reports')
    rauc_excel_saved = False
    rauc_xml_saved = False
    rauc_excel_path = None
    rauc_xml_path = None

    if os.path.exists(reports_folder):
        for file in os.listdir(reports_folder):
            if file.startswith('РАУЦ_') and file.endswith('.xlsx'):
                rauc_excel_saved = True
                # Формируем относительный путь
                rel_path = os.path.relpath(
                    os.path.join(reports_folder, file),
                    settings.MEDIA_ROOT
                ).replace('\\', '/')
                rauc_excel_path = rel_path
            elif file.startswith('РАУЦ_') and file.endswith('.xml'):
                rauc_xml_saved = True
                rel_path = os.path.relpath(
                    os.path.join(reports_folder, file),
                    settings.MEDIA_ROOT
                ).replace('\\', '/')
                rauc_xml_path = rel_path
    # ==========================================

    context = {
        'group': group,
        'documents': documents_list,
        'rauc_excel_saved': rauc_excel_saved,  # ← ДОБАВЛЕНО
        'rauc_xml_saved': rauc_xml_saved,      # ← ДОБАВЛЕНО
        'rauc_excel_path': rauc_excel_path,    # ← ДОБАВЛЕНО
        'rauc_xml_path': rauc_xml_path,        # ← ДОБАВЛЕНО
    }

    # === ПРОВЕРКА НАЛИЧИЯ ФАЙЛОВ ФРДО ===
    frdo_excel_saved = False
    frdo_excel_path = None

    if os.path.exists(reports_folder):
        for file in os.listdir(reports_folder):
            if file.startswith('ФРДО_') and file.endswith('.xlsx'):
                frdo_excel_saved = True
                rel_path = os.path.relpath(
                    os.path.join(reports_folder, file),
                    settings.MEDIA_ROOT
                ).replace('\\', '/')
                frdo_excel_path = rel_path
    # ==========================================

    context = {
        'group': group,
        'documents': documents_list,
        'rauc_excel_saved': rauc_excel_saved,
        'rauc_xml_saved': rauc_xml_saved,
        'rauc_excel_path': rauc_excel_path,
        'rauc_xml_path': rauc_xml_path,
        'frdo_excel_saved': frdo_excel_saved,  # ← ДОБАВЛЕНО
        'frdo_excel_path': frdo_excel_path,    # ← ДОБАВЛЕНО
    }

    return render(request, 'docs/dashboard/documents_dashboard.html', context)

@staff_member_required
def certificate_batch_view(request, group_id):
    """
    Универсальный просмотр/генерация сертификатов для группы.
    Шаблон автоматически выбирается сервисом на основе поля certificate_template в Module.
    """
    group = get_object_or_404(Group, id=group_id)

    # Проверка: есть ли кого сертифицировать
    if not Enrollment.objects.filter(group=group, status='completed').exists():
        messages.warning(request, "В группе нет слушателей со статусом 'Завершил' для выписки удостоверений.")
        return redirect('docs:group_documents_dashboard', group_id=group.id)

    service = DocumentStorageService(group)

    try:
        # Вызываем универсальный метод. Он сам возьмет правильный template из module.certificate_template
        pdf_path = service.save_certificate()

        # Проверяем, что файл существует
        if not os.path.exists(pdf_path):
            messages.error(request, f"Файл сертификата не найден: {pdf_path}")
            return redirect('docs:group_documents_dashboard', group_id=group.id)

        # Отдаем сгенерированный PDF файл браузеру
        filename = os.path.basename(pdf_path)

        # ← ИСПРАВЛЕНО: Открываем файл без with, FileResponse сам закроет его после отправки
        pdf_file = open(pdf_path, 'rb')
        response = FileResponse(pdf_file, content_type='application/pdf', as_attachment=False)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['Content-Length'] = os.path.getsize(pdf_path)

        return response

    except ValueError as ve:
        # Ловим нашу кастомную ошибку, если не заполнен certificate_template в админке
        messages.error(request,
                       f"Ошибка настройки: {str(ve)} Пожалуйста, заполните поле 'Шаблон сертификата' в карточке Модуля.")
        return redirect('docs:group_documents_dashboard', group_id=group.id)
    except Exception as e:
        messages.error(request, f"Ошибка генерации сертификата: {str(e)}")
        return redirect('docs:group_documents_dashboard', group_id=group.id)

