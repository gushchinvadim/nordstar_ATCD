from references.models import AircraftType

# Словарь маппинга кодов в названия
AIRCRAFT_TYPE_MAP = {
    'CL': 'Boeing -737-300 (Classic - CL)',
    'NG': 'Boeing -737-800 (Next Generation - NG)',
    'NG/CL': 'Boeing -737-800 (Next Generation - NG) Boeing -737-300 (Classic - CL)',
    'MAX': 'Boeing -737 MAX',
    'A320': 'Airbus A320',
    'A321': 'Airbus A321',
    # Добавляйте новые типы по мере необходимости
}


def normalize_aircraft_code(raw_code):
    """
    Нормализует сырой код из Excel в базовый код для поиска.
    Примеры:
        'B737NG' -> 'NG'
        'B737CL' -> 'CL'
        'NG/CL' -> 'NG/CL'
        'B737 NG' -> 'NG'
    """
    if not raw_code:
        return None

    raw_code = str(raw_code).strip().upper().replace(' ', '')

    # Убираем префикс B737 если есть
    if raw_code.startswith('B737'):
        raw_code = raw_code[4:]

    return raw_code if raw_code else None


def get_or_create_aircraft_type(raw_code):
    """
    Находит или создает AircraftType по коду из Excel.
    Возвращает объект AircraftType или None.
    """
    code = normalize_aircraft_code(raw_code)
    if not code:
        return None

    # 1. Ищем в БД по коду
    aircraft_type = AircraftType.objects.filter(code=code).first()

    if aircraft_type:
        return aircraft_type

    # 2. Если не нашли — получаем название из словаря
    name = AIRCRAFT_TYPE_MAP.get(code)

    if not name:
        print(f"️ ВНИМАНИЕ: Код ВС '{code}' не найден в словаре маппинга. "
              f"Добавьте его в AIRCRAFT_TYPE_MAP или создайте вручную в админке.")
        return None

    # 3. Создаем запись в справочнике
    aircraft_type, created = AircraftType.objects.get_or_create(
        code=code,
        defaults={'name': name}
    )

    if created:
        print(f"✅ Создан новый тип ВС: {name} (код: {code})")

    return aircraft_type