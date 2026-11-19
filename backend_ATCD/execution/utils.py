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

    from .local_time import group_timezone
    local_tz = group_timezone(schedule_item.group)
    tz_name = str(local_tz)

    # 2. Создаем "точное" время начала занятия (локальное для этой локации)
    naive_start = datetime.combine(schedule_item.date, schedule_item.start_time)
    aware_start = naive_start.replace(tzinfo=local_tz)

    # 3. Получаем текущее время в ЭТОМ ЖЕ часовом поясе
    now_local = datetime.now(local_tz)

    # 4. Сравниваем
    if now_local < aware_start:
        return False, f"Нельзя подтвердить действие раньше времени начала. По местному времени ({tz_name}) занятие начинается {schedule_item.date} в {schedule_item.start_time}"

    return True, ""