# docs/utils.py
import base64
import os
from datetime import date

from django.conf import settings
from execution.models import ScheduleItem, ComplianceLog
from training.models import Section

def get_logo_base64():
    """Кодирует логотип в base64 для встраивания в HTML/PDF"""
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo-nordstar.png')
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            return base64.b64encode(f.read()).decode('utf-8')
    return None


def get_exam_date_for_enrollment(enrollment):
    """
    Находит фактическую дату сдачи экзамена для конкретного студента.
    Приоритет:
    1. Дата оценки из журнала (assessment.assessment_date) - фактическая дата сдачи
    2. Дата из расписания (ScheduleItem.date) - плановая дата
    3. Дата завершения enrollment
    4. Сегодня (только если ничего не нашли)
    """
    from execution.models import ScheduleItem
    from training.models import Section

    group = enrollment.group
    module = group.module

    # Находим секцию экзамена
    final_exam_section = None
    sections = Section.objects.filter(stage__module=module).order_by('stage__order', 'order')
    for section in sections:
        title_lower = section.title.lower()
        if 'итогов' in title_lower or 'экзамен' in title_lower or 'аттестац' in title_lower:
            final_exam_section = section
            break

    # ПРИОРИТЕТ 1: Дата из журнала оценок (фактическая дата сдачи)
    if final_exam_section:
        exam_assessment = enrollment.assessments.filter(section=final_exam_section).first()
        if exam_assessment and exam_assessment.assessment_date:
            return exam_assessment.assessment_date

    # ПРИОРИТЕТ 2: Дата из расписания (плановая)
    if final_exam_section:
        exam_schedule = ScheduleItem.objects.filter(
            group=group,
            section=final_exam_section,
            date__isnull=False
        ).order_by('date').first()
        if exam_schedule:
            return exam_schedule.date

    # ПРИОРИТЕТ 3: Дата завершения
    if enrollment.completed_at:
        return enrollment.completed_at

    # ПРИОРИТЕТ 4: Сегодня
    return date.today()


def get_instructor_final_signature(group, instructor):
    """
    Получает финальную подпись инструктора для группы.

    Приоритет поиска:
    1. grades_submitted — выставление оценок (итоговая аттестация)
    2. instructor_group_handed_over — передача группы методисту
    3. lesson_completed — любое завершённое занятие (последнее по времени)

    Returns:
        signature_string или None
    """
    if not instructor:
        return None

    # Приоритет 1: подпись при выставлении оценок
    log = ComplianceLog.objects.filter(
        staff=instructor,
        enrollment__group=group,
        action_type='grades_submitted'
    ).order_by('-timestamp').first()

    # Приоритет 2: подпись при передаче группы методисту
    if not log:
        log = ComplianceLog.objects.filter(
            staff=instructor,
            enrollment__group=group,
            action_type='instructor_group_handed_over'
        ).order_by('-timestamp').first()

    # Приоритет 3: последнее завершённое занятие (любой тип)
    if not log:
        log = ComplianceLog.objects.filter(
            staff=instructor,
            enrollment__group=group,
            action_type='lesson_completed'
        ).order_by('-timestamp').first()

    return log.signature_string if log else None