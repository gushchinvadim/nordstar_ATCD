# execution/services/iup_service.py

import os
import re
import json
from datetime import timedelta
from django.conf import settings
from django.template.loader import render_to_string
from weasyprint import HTML
from execution.models import Group, Enrollment, ScheduleItem, IndividualStudyPlan
from training.models import Section, Stage
from people.models import Staff
from references.models import Location


class IUPService:
    """
    Сервис генерации индивидуального учебного плана.
    Использует полное расписание из JSON, сохраненное в ИУП.
    """

    def __init__(self, enrollment, new_dates):
        self.enrollment = enrollment
        self.student = enrollment.student
        self.group = enrollment.group
        self.new_dates = new_dates
        self.schedule_data = new_dates.get('schedule_data', [])

        year = str(self.group.start_date.year) if self.group.start_date else 'unknown'
        module_code = re.sub(r'[^\w\-]', '_', self.group.module.code) if self.group.module else 'unknown'
        self.group_folder = os.path.join(
            settings.MEDIA_ROOT,
            'documents', year, 'groups', module_code, self.group.assigned_number, 'iup'
        )
        os.makedirs(self.group_folder, exist_ok=True)

    def create_iup(self, reason='', created_by=None):
        """Создает ИУП и генерирует все документы"""

        iup = IndividualStudyPlan.objects.create(
            student=self.student,
            group=self.group,
            start_date=self.new_dates['start_date'],
            end_date=self.new_dates['end_date'],
            start_face_to_face=self.new_dates.get('start_face_to_face'),
            schedule_data=self.schedule_data,  # ← Сохраняем JSON
            reason=reason,
            created_by=created_by,
            status='active'
        )

        schedule_pdf = self._generate_schedule_pdf()
        thematic_plan_pdf = self._generate_thematic_plan_pdf()

        return {
            'iup': iup,
            'schedule_path': schedule_pdf,
            'thematic_plan_path': thematic_plan_pdf
        }

    def _get_virtual_schedule_from_json(self):
        """Получает расписание из JSON, подставляя объекты Django"""
        from references.models import Classroom  # ← Импортируем правильную модель

        virtual_schedule = []

        for item in self.schedule_data:
            # Получаем объекты по ID
            instructor = Staff.objects.get(id=item['instructor_id']) if item.get('instructor_id') else None

            # ← ИСПРАВЛЕНО: используем Classroom вместо Location
            classroom = Classroom.objects.get(id=item['classroom_id']) if item.get('classroom_id') else None

            # Получаем section
            from training.models import Section
            section = Section.objects.get(id=item['section_id']) if item.get('section_id') else None

            virtual_schedule.append({
                'date': item.get('new_date'),
                'start_time': item.get('start_time'),
                'end_time': item.get('end_time'),
                'section': section,
                'instructor': instructor,
                'classroom': classroom,
                'session_type': item.get('session_type', ''),
            })

        return virtual_schedule

    def _generate_schedule_pdf(self):
        """Генерирует PDF расписания ИУП"""
        virtual_schedule = self._get_virtual_schedule_from_json()

        context = {
            'group': self.group,
            'schedule_items': virtual_schedule,
            'logo_base64': self._get_logo_base64(),
            'iup_mode': True,
            'iup_student': self.student,
            'iup_start_date': self.new_dates['start_date'],
            'iup_end_date': self.new_dates['end_date'],
        }

        html_content = render_to_string('docs/schedules/schedule.html', context)

        pdf_filename = f"ИУП_{self.student.surname}_{self.student.name}_расписание.pdf"
        pdf_path = os.path.join(self.group_folder, pdf_filename)

        HTML(string=html_content).write_pdf(pdf_path)

        return pdf_path

    def _generate_thematic_plan_pdf(self):
        """Генерирует PDF тематического плана ИУП"""
        # Используем ту же логику, что и для расписания
        virtual_schedule = self._get_virtual_schedule_from_json()

        # Преобразуем в формат тематического плана
        virtual_plan_pages = self._convert_to_thematic_plan(virtual_schedule)

        context = {
            'group': self.group,
            'thematic_plan_pages': virtual_plan_pages,
            'module_total_hours': sum(row['hours'] for page in virtual_plan_pages for row in page['rows']),
            'logo_base64': self._get_logo_base64(),
            'iup_mode': True,
            'iup_student': self.student,
            'iup_start_date': self.new_dates['start_date'],
            'iup_end_date': self.new_dates['end_date'],
        }

        html_content = render_to_string('docs/iup/iup_thematic_plan.html', context)

        pdf_filename = f"ИУП_{self.student.surname}_{self.student.name}_тематический_план.pdf"
        pdf_path = os.path.join(self.group_folder, pdf_filename)

        HTML(string=html_content).write_pdf(pdf_path)

        return pdf_path

    def _convert_to_thematic_plan(self, virtual_schedule):
        """Преобразует плоское расписание в структуру тематического плана"""
        rows = []
        prev_stage_id = None
        stage_hours = {}

        for idx, item in enumerate(virtual_schedule):
            if not item.get('section'):
                continue

            stage = item['section'].stage
            is_first = (prev_stage_id != stage.id)

            # Считаем часы по этапам
            if stage.id not in stage_hours:
                stage_hours[stage.id] = 0
            stage_hours[stage.id] += item['section'].duration_hours or 0

            # Формируем место
            location = ''
            if item.get('session_type') == 'sdo':
                location = 'СДО (ispringlearn.ru)'
            elif item.get('classroom'):
                location = item['classroom'].title or ''

            # Формируем время
            time_str = ''
            if item.get('start_time') and item.get('end_time'):
                time_str = f"{item['start_time']} – {item['end_time']}"

            rows.append({
                'number': idx + 1,
                'title': item['section'].title,
                'subtitle': '',
                'hours': item['section'].duration_hours or 0,
                'location': location,
                'date': item.get('date', ''),
                'start_time': time_str,
                'instructor': item['instructor'].full_name if item.get('instructor') else '',
                'is_first_of_stage': is_first,
                'is_last_of_stage': False,
                'stage': stage,
                'stage_total_hours': 0,  # заполним ниже
            })

            prev_stage_id = stage.id

        # Помечаем последние элементы этапов и заполняем итоги
        for i, row in enumerate(rows):
            if i + 1 < len(rows):
                if rows[i + 1]['stage'].id != row['stage'].id:
                    row['is_last_of_stage'] = True
                    row['stage_total_hours'] = stage_hours.get(row['stage'].id, 0)
            else:
                row['is_last_of_stage'] = True
                row['stage_total_hours'] = stage_hours.get(row['stage'].id, 0)

        return [{'rows': rows}]

    def _get_logo_base64(self):
        try:
            from docs.utils import get_logo_base64
            return get_logo_base64()
        except Exception:
            return None