# docs/services/document_storage.py
import os
import re
from datetime import date

from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML

from docs.utils import get_logo_base64
from execution.models import Enrollment, Certificate, ScheduleItem
from references.models import License
from training.models import Section


def sanitize_filename(filename):
    """Заменяет запрещённые символы в имени файла на _"""
    return re.sub(r'[^\w\.\-]', '_', filename)


class DocumentStorageService:
    """Сервис для сохранения документов группы"""

    def __init__(self, group):
        self.group = group
        self.year = group.start_date.year if group.start_date else date.today().year

        # Формируем уникальный путь: год / код_модуля / номер_группы
        # Это гарантирует, что группы с одинаковыми номерами, но из разных программ, не пересекутся
        module_code = group.module.code if group.module else 'unknown_module'
        safe_module_code = re.sub(r'[^\w\-]', '_', module_code)

        self.base_path = os.path.join(
            settings.MEDIA_ROOT,
            'documents',
            str(self.year),
            'groups',
            safe_module_code,
            group.assigned_number
        )

    def get_or_create_folder(self, *subfolders):
        """Создаёт папку если не существует"""
        folder_path = os.path.join(self.base_path, *subfolders)
        os.makedirs(folder_path, exist_ok=True)
        return folder_path

    def save_both(self, template_name, context, subfolder, filename):
        """Генерирует и сохраняет PDF (и HTML, если нужно)"""
        folder = self.get_or_create_folder(*subfolder) if subfolder else self.base_path
        pdf_filename = filename.replace('.html', '.pdf')
        file_path = os.path.join(folder, pdf_filename)

        html_content = render_to_string(template_name, context)
        base_url = f'file://{settings.BASE_DIR}/'

        HTML(string=html_content).write_pdf(
            file_path,
            base_url=base_url,
            presentational_hints=True
        )
        return file_path

    # === Основные документы ===

    def save_enrollment_order(self):
        """Сохраняет приказ о зачислении"""
        enrollments = Enrollment.objects.filter(group=self.group).order_by('number_in_group').select_related('student')
        context = {
            'group': self.group,
            'enrollments': enrollments,
            'logo_base64': get_logo_base64(),
        }
        raw_filename = f"{self.group.assigned_number}-{self.group.application}-З.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both('docs/orders/enrollment.html', context, ['orders'], filename)

    def save_schedule(self):
        """Сохраняет расписание"""
        schedule_items = ScheduleItem.objects.filter(group=self.group).select_related(
            'section', 'subsection', 'section__stage', 'instructor', 'classroom'
        ).order_by('section__stage__order', 'section__order', 'subsection__order')

        context = {
            'group': self.group,
            'schedule_items': schedule_items,
            'logo_base64': get_logo_base64(),
        }
        filename = f"{self.group.assigned_number}_schedule_v.1.html"
        return self.save_both('docs/schedules/schedule.html', context, ['schedules'], filename)

    def save_journal(self):
        """Сохраняет журнал подготовки группы"""
        from docs.views import get_journal_context
        context = get_journal_context(self.group)
        template_name = 'docs/journal/journal_landscape.html' if context.get(
            'use_landscape') else 'docs/journal/journal.html'
        raw_filename = f"Журнал_{self.group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both(template_name, context, ['journal'], filename)

    def _get_training_task_template(self, task_type):
        """
        Динамически определяет путь к шаблону задания на тренировку.
        task_type: 'land' (Суша) или 'water' (Вода)
        """
        module_code = (self.group.module.code or "").upper()

        # Определяем номер курса по коду модуля
        if '01' in module_code or 'C1' in module_code:
            course_num = '1'
        else:
            course_num = '2'  # По умолчанию для 02, C2 и т.д.

        return f"docs/training_tasks/course_{course_num}/{task_type}_training_task.html"

    def save_land_training_task(self):
        """Сохраняет задание на тренировку АСП Суша"""
        enrollments = Enrollment.objects.filter(group=self.group).select_related('student',
                                                                                 'student__profession').order_by(
            'number_in_group')
        asp_item = ScheduleItem.objects.filter(group=self.group, session_type='asp-l').select_related(
            'instructor').first()
        instructor = asp_item.instructor.full_name if asp_item and asp_item.instructor else None
        aircraft_type = self.group.module.aircraft_type if self.group.module else None

        context = {
            'group': self.group, 'enrollments': enrollments, 'instructor_name': instructor,
            'aircraft_type': aircraft_type, 'logo_base64': get_logo_base64(),
        }

        # ← ДИНАМИЧЕСКИЙ ШАБЛОН
        template_name = self._get_training_task_template('land')

        raw_filename = f"Задание_АСП_Суша_{self.group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both(template_name, context, ['training_tasks'], filename)

    def save_water_training_task(self):
        """Сохраняет задание на тренировку АСП Вода"""
        enrollments = Enrollment.objects.filter(group=self.group).select_related('student',
                                                                                 'student__profession').order_by(
            'number_in_group')
        asp_item = ScheduleItem.objects.filter(group=self.group, session_type='asp-w').select_related(
            'instructor').first()
        instructor = asp_item.instructor.full_name if asp_item and asp_item.instructor else None
        aircraft_type = self.group.module.aircraft_type if self.group.module else None

        context = {
            'group': self.group, 'enrollments': enrollments, 'instructor_name': instructor,
            'aircraft_type': aircraft_type, 'logo_base64': get_logo_base64(),
        }

        # ← ДИНАМИЧЕСКИЙ ШАБЛОН
        template_name = self._get_training_task_template('water')

        raw_filename = f"Задание_АСП_Вода_{self.group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both(template_name, context, ['training_tasks'], filename)
    def save_dismissal_ok(self):
        """Сохраняет приказ об успешном окончании"""
        enrollments = Enrollment.objects.filter(group=self.group, status='completed').select_related(
            'student').order_by('number_in_group')
        context = {'group': self.group, 'enrollments': enrollments, 'logo_base64': get_logo_base64()}
        raw_filename = f"Приказ_ОК_{self.group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both('docs/orders/dismissal_ok.html', context, ['orders'], filename)

    def save_dismissal_ot(self):
        """Сохраняет приказ об отчислении"""
        enrollments = Enrollment.objects.filter(group=self.group, status='dismissed').select_related(
            'student').order_by('number_in_group')
        context = {'group': self.group, 'enrollments': enrollments, 'logo_base64': get_logo_base64()}
        raw_filename = f"Приказ_ОТ_{self.group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)
        return self.save_both('docs/orders/dismissal_ot.html', context, ['orders'], filename)

    # === Сертификаты (Удостоверения) ===

    def save_certificate(self):
        """
        Универсальный метод сохранения удостоверений.
        Использует данные из модели Module (prog_id, mod_id, template, approval_organ).
        """
        group = self.group
        module = group.module

        # Проверка наличия шаблона в модели
        if not module.certificate_template:
            raise ValueError(
                f"Для модуля '{module.code}' не указан путь к шаблону сертификата (certificate_template) в админке.")

        enrollments = Enrollment.objects.filter(group=group, status='completed').select_related('student').order_by(
            'number_in_group')
        if not enrollments.exists():
            raise Exception(f"Нет завершивших студентов в группе {group.assigned_number}")

        license_education = License.objects.filter(organ__icontains="Министерство").order_by(
            '-issue_date').first() or License.objects.filter(id=2).first()
        license_favt = License.objects.filter(organ__icontains="агентство").order_by(
            '-issue_date').first() or License.objects.filter(id=1).first()

        sections = Section.objects.filter(stage__module=module).order_by('stage__order', 'order')

        # Ищем экзамен
        final_exam_section = next((s for s in sections if
                                   'итогов' in s.title.lower() or 'экзамен' in s.title.lower() or 'аттестац' in s.title.lower()),
                                  None)
        final_exam_hours = float(
            final_exam_section.duration_hours) if final_exam_section and final_exam_section.duration_hours else 2.0

        # =====================================================================
        # РАСЧЕТ ЧАСОВ
        # =====================================================================
        # 1. Общее время модуля берем из плановых часов в БД (единственный источник истины)
        total_hours = float(module.duration) if module.duration else 0.0

        # 2. Часы СДО считаем ТОЛЬКО по разделам, где detail == 'sdo' (исключая экзамен)
        elearning_hours = sum(
            float(section.duration_hours)
            for section in sections
            if section.detail == 'sdo' and section != final_exam_section
        )
        # =====================================================================

        batch_data = []
        for enrollment in enrollments:
            assessments = {a.section_id: a for a in enrollment.assessments.select_related('section').all()}

            # =====================================================================
            # ГРУППИРОВКА РАЗДЕЛОВ ПО ЭТАПАМ
            # =====================================================================
            sections_by_stage = {}
            for section in sections:
                if section == final_exam_section:
                    continue

                stage = section.stage
                stage_key = stage.id

                if stage_key not in sections_by_stage:
                    sections_by_stage[stage_key] = {
                        'stage_title': stage.title,
                        'stage_order': stage.order,
                        'sections': []
                    }

                assessment = assessments.get(section.id)
                hours = float(section.duration_hours) if section.duration_hours else 0
                grade = assessment.score if assessment else None
                min_score = section.min_score if section.min_score else (1 if section.grade_type == 'binary' else 4)
                is_passed = grade >= min_score if grade is not None else False

                sections_by_stage[stage_key]['sections'].append({
                    'section__title': section.title,
                    'hours_completed': hours,  # ← Часы РАЗДЕЛА
                    'section__grade_type': section.grade_type,
                    'grade': grade,
                    'is_passed': is_passed,
                })

            # Сортируем этапы по порядку
            stages_data = sorted(sections_by_stage.values(), key=lambda x: x['stage_order'])
            # =====================================================================

            # Плоский список для обратной совместимости
            section_results = []
            for stage_data in stages_data:
                section_results.extend(stage_data['sections'])
            # =====================================================================

            final_grade = None
            if hasattr(enrollment, 'final_score') and enrollment.final_score:
                final_grade = enrollment.final_score
            elif final_exam_section and final_exam_section.id in assessments:
                final_grade = assessments[final_exam_section.id].score

            # Определение даты выдачи
            issue_date = None
            if final_exam_section:
                exam_schedule = ScheduleItem.objects.filter(group=group, section=final_exam_section).order_by(
                    'date').first()
                if exam_schedule and exam_schedule.date:
                    issue_date = exam_schedule.date
                else:
                    exam_schedule = ScheduleItem.objects.filter(group=group, section__stage__module=module).exclude(
                        date__isnull=True).order_by('date').last()
                    if exam_schedule:
                        issue_date = exam_schedule.date

            if not issue_date:
                exam_assessment = assessments.get(final_exam_section.id) if final_exam_section else None
                if exam_assessment and exam_assessment.assessment_date:
                    issue_date = exam_assessment.assessment_date
                elif enrollment.completed_at:
                    issue_date = enrollment.completed_at
                else:
                    issue_date = date.today()

            cert, created = Certificate.objects.get_or_create(
                enrollment=enrollment,
                defaults={
                    'number': Certificate.generate_number(enrollment),
                    'student_full_name': f"{enrollment.student.surname} {enrollment.student.name} {enrollment.student.patronymic}",
                    'student_profession': str(enrollment.student.profession) if enrollment.student.profession else '',
                    'module_code': module.code,
                    'module_title': module.title,
                    'certificate_type': module.course.default_certificate_type if module.course else 'credential',
                    # ← ИСПРАВЛЕНО
                    'issue_date': issue_date,
                    'total_hours': total_hours,
                    'aircraft_type': str(module.aircraft_type) if module.aircraft_type else '',
                }
            )

            batch_data.append({
                'student': enrollment.student,
                'enrollment': enrollment,
                'group': group,
                'module': module,
                'license_education': license_education,
                'license_favt': license_favt,
                'program_title': module.title,
                'prog_id': module.course.prog_id if module.course else '',
                'mod_id': module.mod_id,
                # БЕРЁМ ИЗ COURSE, А НЕ ИЗ MODULE
                'approval_organ': module.course.approved if module.course else '',
                'approval_date': module.course.approved_date.strftime(
                    '%d.%m.%Y') if module.course and module.course.approved_date else '',
                # Остальные данные
                'cert_number': cert.number,
                # ОБА ПОЛЯ ДЛЯ СОВМЕСТИМОСТИ:
                'section_results': section_results,  # Плоский список (для старых шаблонов)
                'stages_data': stages_data,  # Структура с этапами (для новых шаблонов)
                'total_hours': total_hours,
                'elearning_hours': elearning_hours,
                'final_exam_hours': final_exam_hours,
                'final_grade': final_grade,
                'logo_base64': get_logo_base64(),
            })

        # Используем шаблон, указанный в модели Module
        template_name = module.certificate_template
        raw_filename = f"Удостоверения_{module.code or 'module'}_{group.assigned_number}.html"
        filename = sanitize_filename(raw_filename)

        return self.save_both(template_name, {'batch_data': batch_data, 'group': group}, ['certificates'], filename)