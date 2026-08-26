# docs/views.py
import io
import json
import re
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import EmailMessage
from django.db import models
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST, require_GET
from weasyprint import HTML
from execution.models import Group, Enrollment, ScheduleItem, Assessment, IndividualStudyPlan
from execution.services.iup_service import IUPService
from people.models import Staff
from references.models import Location, Classroom
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
    rows_per_page = 10 if use_landscape else 7
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
            'dismissal_reference': service.save_dismissal_reference,  # ← ДОБАВЛЕНО
            'certificate': service.save_certificate,
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
def dismissal_ot_view(request, group_id):
    """Приказ об отчислении (ОТ) — предпросмотр (поддерживает группировку по приказам)"""
    from collections import defaultdict

    group = get_object_or_404(Group, id=group_id)
    target_order_number = request.GET.get('order_number')

    # Получаем всех отчисленных
    enrollments = Enrollment.objects.filter(
        group=group,
        status='dismissed'
    ).select_related('student').order_by('order_out_date', 'order_out_number', 'number_in_group')

    if not enrollments.exists():
        messages.error(request, "Нет отчисленных студентов для формирования приказа.")
        return redirect('docs:dismissal_ot_list', group_id=group_id)

    # Группируем по номеру приказа
    orders_dict = defaultdict(list)
    for enrollment in enrollments:
        # Если запрошен конкретный номер приказа (переход из списка), игнорируем остальные
        if target_order_number and enrollment.order_out_number != target_order_number:
            continue

        order_key = enrollment.order_out_number or f"Б/Н-{enrollment.id}"
        orders_dict[order_key].append(enrollment)

    # Если искали конкретный номер и не нашли
    if target_order_number and not orders_dict:
        messages.error(request, "Студенты с таким номером приказа не найдены")
        return redirect('docs:dismissal_ot_list', group_id=group_id)

    # Формируем список для шаблона (точно такой же, как в save_dismissal_ot)
    orders_list = []
    for order_number, ens in orders_dict.items():
        orders_list.append({
            'order_number': order_number,
            'order_date': ens[0].order_out_date,
            'enrollments': ens
        })

    context = {
        'group': group,
        'orders_list': orders_list,  # <-- ТЕПЕРЬ ШАБЛОН ПОЛУЧИТ ТО, ЧТО ОЖИДАЕТ
        'logo_base64': get_logo_base64(),
    }

    return render(request, 'docs/orders/dismissal_ot.html', context)


@staff_member_required
def dismissal_ok_view(request, group_id):
    """Генерирует один PDF со всеми приказами ОК группы (сгруппированными по дате/номеру)"""
    group = get_object_or_404(Group, id=group_id)

    # Получаем всех зачисленных со статусом completed
    enrollments = Enrollment.objects.filter(
        group=group,
        status='completed'
    ).select_related('student').order_by('order_out_date', 'order_out_number', 'number_in_group')

    # Группируем их по номеру приказа
    orders_dict = defaultdict(list)
    for enrollment in enrollments:
        # Если номера нет (редкий случай), используем заглушку
        order_key = enrollment.order_out_number or f"Б/Н-{enrollment.id}"
        orders_dict[order_key].append(enrollment)

    # Преобразуем в список для удобного цикла в шаблоне
    orders_list = []
    for order_number, ens in orders_dict.items():
        orders_list.append({
            'order_number': order_number,
            'order_date': ens[0].order_out_date,
            'enrollments': ens
        })

    context = {
        'group': group,
        'orders_list': orders_list,
        'logo_base64': get_logo_base64(),
    }
    return render(request, 'docs/orders/dismissal_ok.html', context)

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
        'dismissal_reference': ['справк', 'reference'],  # ← ДОБАВЛЕНО
        'journal': ['журнал', 'journal'],
        'schedule': ['распис', 'schedule'],
        'land_training_task': ['суша', 'land', 'asp-l', 'суш'],
        'water_training_task': ['вода', 'water', 'asp-w', 'вод'],
        'certificate': ['удостовер', 'сертификат', 'модуль', 'certificate', 'cert'],
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

    # === ПОЛУЧЕНИЕ СПИСКА ИУП ДЛЯ ГРУППЫ ===
    iup_documents = []
    year = str(group.start_date.year) if group.start_date else str(date.today().year)
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    iup_folder_rel = f"documents/{year}/groups/{module_code}/{group.assigned_number}/iup"

    iups = IndividualStudyPlan.objects.filter(
        group=group
    ).select_related('student').order_by('-created_at')

    for iup in iups:
        surname = iup.student.surname
        name = iup.student.name
        patronymic = iup.student.patronymic or ''

        sched_rel_path = f"{iup_folder_rel}/ИУП_{surname}_{name}_расписание.pdf"
        theme_rel_path = f"{iup_folder_rel}/ИУП_{surname}_{name}_тематический_план.pdf"

        sched_exists = os.path.exists(os.path.join(settings.MEDIA_ROOT, sched_rel_path))
        theme_exists = os.path.exists(os.path.join(settings.MEDIA_ROOT, theme_rel_path))

        iup_documents.append({
            'id': iup.id,  # <--- ДОБАВЛЕНО: ID необходим для кнопки перегенерации
            'student_name': f"{surname} {name} {patronymic}".strip(),
            'reason': iup.reason,
            'created_at': iup.created_at,
            'status': iup.get_status_display(),
            'schedule_path': sched_rel_path,
            'thematic_path': theme_rel_path,
            'schedule_exists': sched_exists,
            'thematic_exists': theme_exists,
        })

    context['iup_documents'] = iup_documents
    # ==========================================

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


@staff_member_required
def create_iup_view(request, enrollment_id):
    """Создание индивидуального учебного плана для студента"""

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    student = enrollment.student
    group = enrollment.group

    if request.method == 'POST':
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        start_face_to_face = request.POST.get('start_face_to_face')
        reason = request.POST.get('reason', '')
        reason_details = request.POST.get('reason_details', '')
        schedule_data_json = request.POST.get('schedule_data', '[]')

        if not start_date or not end_date:
            messages.error(request, 'Укажите даты начала и окончания ИУП')
            return redirect('docs:create_iup', enrollment_id=enrollment.id)

        if not reason:
            messages.error(request, 'Выберите причину назначения ИУП')
            return redirect('docs:create_iup', enrollment_id=enrollment.id)

        # Объединяем основную причину и детали
        if reason_details:
            reason = f"{reason} | {reason_details}"

        try:
            schedule_data = json.loads(schedule_data_json)
        except json.JSONDecodeError:
            messages.error(request, 'Ошибка в данных расписания')
            return redirect('docs:create_iup', enrollment_id=enrollment.id)

        new_dates = {
            'start_date': date.fromisoformat(start_date),
            'end_date': date.fromisoformat(end_date),
            'start_face_to_face': date.fromisoformat(start_face_to_face) if start_face_to_face else None,
            'schedule_data': schedule_data,
        }

        try:
            service = IUPService(enrollment, new_dates)

            staff_user = getattr(request.user, 'staff', None)
            result = service.create_iup(
                reason=reason,
                created_by=staff_user
            )

            messages.success(
                request,
                f'✅ ИУП создан для {student.surname} {student.name}. '
                f'Документы сохранены в папку группы.'
            )

        except Exception as e:
            messages.error(request, f'Ошибка создания ИУП: {str(e)}')

        return redirect('docs:group_grades', group_id=group.id)

    context = {
        'enrollment': enrollment,
        'student': student,
        'group': group,
    }
    return render(request, 'docs/iup/create_iup.html', context)



@staff_member_required
@require_GET
def iup_preview_schedule(request, enrollment_id):
    """AJAX: возвращает список занятий для предпросмотра ИУП"""

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    group = enrollment.group

    start_date_str = request.GET.get('start_date')
    start_face_to_face_str = request.GET.get('start_face_to_face')

    if not start_date_str:
        return JsonResponse({'error': 'Не указана дата начала'}, status=400)


    start_date = date.fromisoformat(start_date_str)
    start_face_to_face = date.fromisoformat(start_face_to_face_str) if start_face_to_face_str else None

    # Получаем расписание группы
    schedule_items = ScheduleItem.objects.filter(
        group=group
    ).select_related(
        'section', 'section__stage', 'instructor', 'classroom'
    ).order_by('section__stage__order', 'section__order', 'date')

    # Списки для select
    instructors = Staff.objects.filter(is_active=True).order_by('full_name')
    classrooms = Classroom.objects.all().order_by('title')

    # === РАЗДЕЛЬНЫЙ РАСЧЁТ ДАТ ДЛЯ СДО И ОЧНЫХ ===
    # Для очных: offset от даты начала очных занятий группы
    face_to_face_offset = 0
    if start_face_to_face and group.start_face_to_face:
        face_to_face_offset = (start_face_to_face - group.start_face_to_face).days
    elif not start_face_to_face and group.start_date:
        # Если дата очных не указана, используем offset от общей даты начала
        face_to_face_offset = (start_date - group.start_date).days

    virtual_schedule = []
    for item in schedule_items:
        # КЛЮЧЕВОЕ РАЗЛИЧИЕ:
        if item.session_type == 'sdo':
            # СДО: дата = start_date ИУП (которую указал методист)
            virtual_date = start_date
            is_sdo = True
        else:
            # Очные: дата = оригинальная дата + offset
            virtual_date = item.date + timedelta(days=face_to_face_offset) if item.date else None
            is_sdo = False

        virtual_schedule.append({
            'id': item.id,
            'section_id': item.section_id,
            'section_title': item.section.title,
            'stage_title': item.section.stage.title,
            'session_type': item.session_type,
            'is_sdo': is_sdo,
            'original_date': item.date.strftime('%Y-%m-%d') if item.date else None,
            'new_date': virtual_date.strftime('%Y-%m-%d') if virtual_date else None,
            'start_time': item.start_time.strftime('%H:%M') if item.start_time else '',
            'end_time': item.end_time.strftime('%H:%M') if item.end_time else '',
            'instructor_id': item.instructor_id,
            'instructor_name': item.instructor.full_name if item.instructor else '',
            'classroom_id': item.classroom_id,
            'classroom_name': item.classroom.title if item.classroom else '',
        })

    instructors_list = [{'id': i.id, 'name': i.full_name} for i in instructors]
    classrooms_list = [{'id': c.id, 'name': c.title} for c in classrooms]

    return JsonResponse({
        'schedule': virtual_schedule,
        'instructors': instructors_list,
        'classrooms': classrooms_list,
        'offset_days': face_to_face_offset,
        'iup_start_date': start_date.strftime('%Y-%m-%d'),
    })


@staff_member_required
@require_POST
def regenerate_iup(request, iup_id):
    """Перегенерирует PDF-файлы ИУП из данных, сохраненных в БД"""

    from execution.models import IndividualStudyPlan
    from execution.services.iup_service import IUPService

    iup = get_object_or_404(IndividualStudyPlan, id=iup_id)

    try:
        # Находим зачисление студента в эту группу
        enrollment = Enrollment.objects.get(
            student=iup.student,
            group=iup.group
        )

        # Создаем сервис с существующими данными
        new_dates = {
            'start_date': iup.start_date,
            'end_date': iup.end_date,
            'start_face_to_face': iup.start_face_to_face,
            'schedule_data': iup.schedule_data or [],
        }

        service = IUPService(enrollment, new_dates)
        result = service.create_iup(
            reason=iup.reason,
            created_by=iup.created_by
        )

        messages.success(
            request,
            f'✅ ИУП для {iup.student} перегенерирован. '
            f'Файлы сохранены в папку группы.'
        )

    except Enrollment.DoesNotExist:
        messages.error(
            request,
            f'Ошибка: не найдено зачисление студента {iup.student} в группу {iup.group.assigned_number}'
        )
    except Exception as e:
        messages.error(request, f'Ошибка перегенерации ИУП: {str(e)}')

    return redirect('docs:documents_dashboard', group_id=iup.group.id)


@staff_member_required
def download_group_folder(request, group_id):
    """Скачивание всей папки группы в виде ZIP-архива"""


    group = get_object_or_404(Group, id=group_id)

    # Формируем путь к папке группы
    year = str(group.start_date.year) if group.start_date else 'unknown'
    module_code = re.sub(r'[^\w\-]', '_', group.module.code) if group.module else 'unknown_module'
    group_folder = os.path.join(
        settings.MEDIA_ROOT,
        'documents', str(year), 'groups', module_code, group.assigned_number
    )

    # Проверяем существование папки
    if not os.path.exists(group_folder):
        raise Http404(f"Папка группы не найдена: {group.assigned_number}")

    # Подсчет файлов
    file_count = 0
    total_size = 0
    for root, dirs, files in os.walk(group_folder):
        for file in files:
            file_count += 1
            file_path = os.path.join(root, file)
            total_size += os.path.getsize(file_path)

    # Можно передать в контекст и показать в шаблоне
    # или просто создать архив
    # Создаем ZIP-архив в памяти
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Проходим по всем файлам в папке
        for root, dirs, files in os.walk(group_folder):
            for file in files:
                file_path = os.path.join(root, file)
                # Получаем относительный путь для сохранения в архиве
                arcname = os.path.relpath(file_path, group_folder)
                zip_file.write(file_path, arcname)

    # Возвращаем архив
    zip_buffer.seek(0)
    response = HttpResponse(
        zip_buffer.getvalue(),
        content_type='application/zip'
    )
    response['Content-Disposition'] = f'attachment; filename="Group_{group.assigned_number}.zip"'

    return response


@staff_member_required
def dismissal_reference_view(request, group_id):
    """Предпросмотр справок об обучении для отчисленных"""
    from training.models import Section

    group = get_object_or_404(Group, id=group_id)

    enrollments = Enrollment.objects.filter(
        group=group, status='dismissed'
    ).select_related('student', 'group', 'group__module').order_by('number_in_group')

    if not enrollments.exists():
        messages.warning(request, "Нет отчисленных студентов для формирования справок.")
        return redirect('docs:documents_dashboard', group_id=group.id)

    # Получаем ВСЕ разделы модуля
    all_sections = Section.objects.filter(
        stage__module=group.module
    ).select_related('stage').order_by('stage__order', 'order')

    students_data = []
    for enrollment in enrollments:
        # Словарь оценок студента
        assessments_dict = {
            a.section_id: a
            for a in enrollment.assessments.select_related('section').all()
        }

        passed_sections = []
        total_hours_passed = 0

        # Итерируемся по ВСЕМ разделам модуля
        for section in all_sections:
            assessment = assessments_dict.get(section.id)

            if assessment and assessment.score is not None:
                grade = assessment.score
                total_hours_passed += float(section.duration_hours or 0)
            else:
                grade = None  # "Не явка"

            passed_sections.append({
                'title': section.title,
                'hours': float(section.duration_hours or 0),
                'stage_title': section.stage.title if section.stage else '',
                'grade': grade,
                'grade_type': section.grade_type,
            })

        sections_per_page = 15
        total_pages = max(1, (len(passed_sections) + sections_per_page - 1) // sections_per_page)

        students_data.append({
            'enrollment': enrollment,
            'student': enrollment.student,
            'dismissal_order_number': enrollment.order_out_number,
            'dismissal_order_date': enrollment.order_out_date,
            'dismissal_reason': enrollment.dismissal_reason,
            'passed_sections': passed_sections,
            'total_hours_passed': total_hours_passed,
            'total_pages': total_pages,
        })

    zk20_pages = len(students_data)

    context = {
        'group': group,
        'students_data': students_data,
        'logo_base64': get_logo_base64(),
        'zk20_pages': zk20_pages,
    }
    return render(request, 'docs/references/dismissal_reference.html', context)