import math
from datetime import timedelta, time
from execution.models import Group, ScheduleItem
from training.models import Section

LESSON_MIN = 45
BREAK_MIN = 5
LUNCH_MIN = 40
MAX_HOURS_PER_DAY = 8

DAILY_LOAD = {
    'base-1': 1, 'base-2': 2, 'base-3': 3, 'base-4': 4,
    'base-5': 5, 'base-6': 6, 'base-7': 7, 'base-8': 8, 'base-9': 9,
}


def _fmt(minutes):
    """Форматирует минуты в ЧЧ:ММ"""
    return f"{(minutes // 60) % 24:02d}:{minutes % 60:02d}"


def calculate_day_schedule(start_minute, num_hours):
    """Рассчитывает время и формирует текст расписания для base-N"""
    current_min = start_minute
    slots = []

    for i in range(1, int(num_hours) + 1):
        end_min = current_min + LESSON_MIN
        slots.append(f"{i} ак.ч - {_fmt(current_min)} - {_fmt(end_min)}")
        current_min = end_min

        if i < int(num_hours):
            if i == 4:
                slots.append(f"Обед - {LUNCH_MIN} мин")
                current_min += LUNCH_MIN
            else:
                slots.append(f"Перерыв - {BREAK_MIN} мин")
                current_min += BREAK_MIN

    end_time = time(current_min // 60, current_min % 60)
    return end_time, "\n".join(slots)


def calculate_sim_schedule(start_minute):
    """Рассчитывает расписание для тренажера (1+4+1 = 6 часов)"""
    current_min = start_minute
    notes = (
        f"Брифинг - {_fmt(current_min)} - {_fmt(current_min + 60)}\n"
        f"Тренажер - {_fmt(current_min + 60)} - {_fmt(current_min + 300)}\n"
        f"Дебрифинг - {_fmt(current_min + 300)} - {_fmt(current_min + 360)}"
    )
    end_time = time((current_min + 360) // 60, (current_min + 360) % 60)
    return end_time, notes


def generate_schedule_for_group(group):
    """Генерирует расписание для группы на основе её модуля"""
    if not group.module:
        raise ValueError("У группы не выбран модуль")

    ScheduleItem.objects.filter(group=group).delete()

    # Сортируем секции строго по порядку
    sections = Section.objects.filter(stage__module=group.module).prefetch_related('subsections').order_by(
        'stage__order', 'order')

    sdo_start_date = group.start_date
    face_to_face_date = group.start_face_to_face or group.start_date

    if not face_to_face_date:
        raise ValueError("Не указана дата начала занятий")

    # 🔑 ГЛАВНОЕ УСЛОВИЕ: Смешанный или Раздельный режим?
    is_sequential = (sdo_start_date == face_to_face_date)

    created_count = 0
    default_start_min = group.start_time_default.hour * 60 + group.start_time_default.minute if group.start_time_default else 9 * 60

    # Инициализация счётчиков в зависимости от режима
    if is_sequential:
        current_date = sdo_start_date
        hours_used_today = 0
    else:
        sdo_current_date = sdo_start_date
        sdo_hours_used_today = 0
        face_to_face_current_date = face_to_face_date
        face_to_face_hours_used_today = 0

    for section in sections:
        detail = section.detail or 'none'
        total_section_hours = float(section.duration_hours or 0)

        if total_section_hours <= 0 and detail != 'sdo':
            continue

        subsections = list(section.subsections.all().order_by('order'))
        if not subsections:
            subsections = [None]

        for sub in subsections:
            if sub:
                item_hours = float(sub.duration_hours or 0)
                if item_hours == 0 and total_section_hours > 0:
                    item_hours = total_section_hours / len(subsections)
                sub_detail = sub.detail or detail
            else:
                item_hours = total_section_hours
                sub_detail = detail

            if item_hours <= 0:
                continue

            item_hours_int = int(math.ceil(item_hours))

            # ==========================================
            # 1. СДО
            # ==========================================
            if sub_detail == 'sdo':
                if is_sequential:
                    if hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                        current_date += timedelta(days=1)
                        hours_used_today = 0
                    while current_date.weekday() >= 5:
                        current_date += timedelta(days=1)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=current_date, deadline=group.end_date,
                        session_type='sdo', notes="Самостоятельное изучение в СДО", status='planned'
                    )
                    hours_used_today += item_hours_int
                else:
                    if sdo_hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                        sdo_current_date += timedelta(days=1)
                        sdo_hours_used_today = 0
                    while sdo_current_date.weekday() >= 5:
                        sdo_current_date += timedelta(days=1)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=sdo_current_date, deadline=group.end_date,
                        session_type='sdo', notes="Самостоятельное изучение в СДО", status='planned'
                    )
                    sdo_hours_used_today += item_hours_int
                created_count += 1
                continue

            # ==========================================
            # 2. Тренажеры (sim)
            # ==========================================
            if sub_detail == 'sim':
                if is_sequential:
                    if hours_used_today + 6 > MAX_HOURS_PER_DAY:
                        current_date += timedelta(days=1)
                        hours_used_today = 0
                    while current_date.weekday() >= 5:
                        current_date += timedelta(days=1)

                    start_time = time(default_start_min // 60, default_start_min % 60)
                    end_time, notes = calculate_sim_schedule(default_start_min)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=current_date, start_time=start_time, end_time=end_time,
                        session_type='sim', notes=notes, status='planned'
                    )
                    hours_used_today += 6
                else:
                    if face_to_face_hours_used_today + 6 > MAX_HOURS_PER_DAY:
                        face_to_face_current_date += timedelta(days=1)
                        face_to_face_hours_used_today = 0
                    while face_to_face_current_date.weekday() >= 5:
                        face_to_face_current_date += timedelta(days=1)

                    start_time = time(default_start_min // 60, default_start_min % 60)
                    end_time, notes = calculate_sim_schedule(default_start_min)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=face_to_face_current_date, start_time=start_time, end_time=end_time,
                        session_type='sim', notes=notes, status='planned'
                    )
                    face_to_face_hours_used_today += 6
                created_count += 1
                continue


            # 2.5. АСП Суша / АСП Вода — аналогично base-N, но часы из duration_hours
            if sub_detail in ['asp-l', 'asp-w']:
                if is_sequential:
                    if hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                        current_date += timedelta(days=1)
                        hours_used_today = 0
                    while current_date.weekday() >= 5:
                        current_date += timedelta(days=1)

                    if hours_used_today == 0:
                        start_min = default_start_min
                    elif hours_used_today == 4:
                        start_min = default_start_min + (4 * LESSON_MIN) + (3 * BREAK_MIN) + LUNCH_MIN
                    else:
                        start_min = default_start_min + (hours_used_today * LESSON_MIN) + (
                                    (hours_used_today - 1) * BREAK_MIN) + BREAK_MIN
                        if hours_used_today > 4:
                            start_min += LUNCH_MIN - BREAK_MIN

                    start_time = time(start_min // 60, start_min % 60)
                    end_time, notes = calculate_day_schedule(start_min, item_hours_int)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=current_date,
                        start_time=start_time, end_time=end_time,
                        session_type=sub_detail, notes=notes, status='planned'
                    )
                    hours_used_today += item_hours_int
                else:
                    if face_to_face_hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                        face_to_face_current_date += timedelta(days=1)
                        face_to_face_hours_used_today = 0
                    while face_to_face_current_date.weekday() >= 5:
                        face_to_face_current_date += timedelta(days=1)

                    if face_to_face_hours_used_today == 0:
                        start_min = default_start_min
                    elif face_to_face_hours_used_today == 4:
                        start_min = default_start_min + (4 * LESSON_MIN) + (3 * BREAK_MIN) + LUNCH_MIN
                    else:
                        start_min = default_start_min + (face_to_face_hours_used_today * LESSON_MIN) + (
                                    (face_to_face_hours_used_today - 1) * BREAK_MIN) + BREAK_MIN
                        if face_to_face_hours_used_today > 4:
                            start_min += LUNCH_MIN - BREAK_MIN

                    start_time = time(start_min // 60, start_min % 60)
                    end_time, notes = calculate_day_schedule(start_min, item_hours_int)

                    ScheduleItem.objects.create(
                        group=group, section=section, subsection=sub,
                        date=face_to_face_current_date,
                        start_time=start_time, end_time=end_time,
                        session_type=sub_detail, notes=notes, status='planned'
                    )
                    face_to_face_hours_used_today += item_hours_int
                created_count += 1
                continue

            # ==========================================
            # 3. Очные занятия (base-N)
            # ==========================================

            if is_sequential:
                if hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                    current_date += timedelta(days=1)
                    hours_used_today = 0
                while current_date.weekday() >= 5:
                    current_date += timedelta(days=1)

                if hours_used_today == 0:
                    start_min = default_start_min
                elif hours_used_today == 4:
                    start_min = default_start_min + (4 * LESSON_MIN) + (3 * BREAK_MIN) + LUNCH_MIN
                else:
                    start_min = default_start_min + (hours_used_today * LESSON_MIN) + (
                                (hours_used_today - 1) * BREAK_MIN) + BREAK_MIN
                    if hours_used_today > 4:
                        start_min += LUNCH_MIN - BREAK_MIN

                start_time = time(start_min // 60, start_min % 60)
                end_time, notes = calculate_day_schedule(start_min, item_hours_int)

                ScheduleItem.objects.create(
                    group=group, section=section, subsection=sub,
                    date=current_date, start_time=start_time, end_time=end_time,
                    session_type=sub_detail, notes=notes, status='planned'
                )
                hours_used_today += item_hours_int
            else:
                if face_to_face_hours_used_today + item_hours_int > MAX_HOURS_PER_DAY:
                    face_to_face_current_date += timedelta(days=1)
                    face_to_face_hours_used_today = 0
                while face_to_face_current_date.weekday() >= 5:
                    face_to_face_current_date += timedelta(days=1)

                if face_to_face_hours_used_today == 0:
                    start_min = default_start_min
                elif face_to_face_hours_used_today == 4:
                    start_min = default_start_min + (4 * LESSON_MIN) + (3 * BREAK_MIN) + LUNCH_MIN
                else:
                    start_min = default_start_min + (face_to_face_hours_used_today * LESSON_MIN) + (
                                (face_to_face_hours_used_today - 1) * BREAK_MIN) + BREAK_MIN
                    if face_to_face_hours_used_today > 4:
                        start_min += LUNCH_MIN - BREAK_MIN

                start_time = time(start_min // 60, start_min % 60)
                end_time, notes = calculate_day_schedule(start_min, item_hours_int)

                ScheduleItem.objects.create(
                    group=group, section=section, subsection=sub,
                    date=face_to_face_current_date, start_time=start_time, end_time=end_time,
                    session_type=sub_detail, notes=notes, status='planned'
                )
                face_to_face_hours_used_today += item_hours_int

            created_count += 1

    return created_count