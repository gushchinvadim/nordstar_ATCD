"""One timezone source for schedules, signatures and local calendar dates."""
from datetime import timezone as datetime_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from django.conf import settings
from django.utils import timezone


def group_timezone(group):
    name = getattr(getattr(group, 'location', None), 'timezone', None) or settings.TIME_ZONE
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone.get_default_timezone()


def local_datetime(value, group):
    if timezone.is_naive(value):
        value = timezone.make_aware(value, datetime_timezone.utc)
    return timezone.localtime(value, group_timezone(group))


def group_today(group):
    return local_datetime(timezone.now(), group).date()


def utc_offset(value):
    offset = value.strftime('%z')
    return f'UTC{offset[:3]}:{offset[3:]}'
