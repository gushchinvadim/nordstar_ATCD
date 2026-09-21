# execution/utils.py
from zoneinfo import ZoneInfo  # Стандартная библиотека Python 3.9+ (у вас Python 3.14, она точно есть)
from django.conf import settings
from datetime import datetime


def check_schedule_time_allowed(schedule_item):
    """
    Проверяет, наступило ли время начала занятия с учетом часового пояса локации группы.
    Возвращает (is_allowed: bool, error_message: str)
    """
    # Если время не указано (например, СДО), пропускаем проверку времени
    if not schedule_item.start_time:
        return True, ""

    # 1. Определяем часовой пояс локации группы
    tz_name = 'Europe/Moscow'  # Значение по умолчанию
    if schedule_item.group and schedule_item.group.location and schedule_item.group.location.timezone:
        tz_name = schedule_item.group.location.timezone

    try:
        local_tz = ZoneInfo(tz_name)
    except Exception:
        # Если такой пояс не найден, fallback на настройки Django
        local_tz = ZoneInfo(settings.TIME_ZONE)

    # 2. Создаем "точное" время начала занятия (локальное для этой локации)
    naive_start = datetime.combine(schedule_item.date, schedule_item.start_time)
    aware_start = naive_start.replace(tzinfo=local_tz)

    # 3. Получаем текущее время в ЭТОМ ЖЕ часовом поясе
    now_local = datetime.now(local_tz)

    # 4. Сравниваем
    if now_local < aware_start:
        return False, f"Нельзя подтвердить действие раньше времени начала. По местному времени ({tz_name}) занятие начинается {schedule_item.date} в {schedule_item.start_time}"

    return True, ""