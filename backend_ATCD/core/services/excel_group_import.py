# core/services/excel_group_import.py
import pandas as pd
from datetime import datetime
from django.utils import timezone
from references.models import Location
from training.models import Module
from people.models import Staff, Student
from execution.models import Group, Enrollment

# Обязательные колонки
# order_in_date убран — он теперь на уровне группы, а не студента
REQUIRED_GROUP_COLUMNS = [
    'group', 'application', 'module_code', 'location',
    'start_date', 'start_face_to_face', 'end_date', 'curator',
    'student', 'number_in_group'
]


def parse_date(date_value):
    """Парсинг дат из Excel"""
    if pd.isna(date_value):
        return None
    if isinstance(date_value, (pd.Timestamp, datetime)):
        return date_value.date()

    date_str = str(date_value).strip()
    for fmt in ['%m/%d/%y', '%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d', '%m/%d/%Y']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def normalize_module_code(code):
    """Нормализует код модуля: убирает лишние пробелы вокруг дефисов"""
    if not code:
        return ''
    code = str(code).strip()
    code = code.replace(' - ', '-').replace(' -', '-').replace('- ', '-')
    return code


def find_module_by_code(module_code):
    """Найти модуль по коду с нормализацией"""
    module_code = str(module_code).strip()
    normalized_code = normalize_module_code(module_code)

    # Точное совпадение после нормализации
    module = Module.objects.filter(code=normalized_code).first()
    if module:
        return module

    # Поиск по началу кода
    module = Module.objects.filter(code__startswith=normalized_code).first()
    if module:
        return module

    # Перебор всех модулей с нормализацией
    for m in Module.objects.all():
        if normalize_module_code(m.code) == normalized_code:
            return m

    return None


def find_staff_by_surname(surname):
    """Найти сотрудника по фамилии"""
    surname = str(surname).strip()
    return Staff.objects.filter(full_name__icontains=surname).first()


def find_student_by_surname(surname):
    """Найти студента по фамилии"""
    surname = str(surname).strip()
    return Student.objects.filter(surname=surname).first()


def import_group_enroll(file_path):
    """Импорт групп и зачислений из Excel"""
    df = pd.read_excel(file_path, dtype={
        'group': str,
        'application': str,
        'module_code': str,
        'location': str,
        'curator': str,
        'student': str,
    })

    # ВАЛИДАЦИЯ
    missing_cols = [col for col in REQUIRED_GROUP_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Неверный формат файла! Отсутствуют колонки: {', '.join(missing_cols)}")

    created_groups = 0
    updated_groups = 0
    created_enrollments = 0
    updated_enrollments = 0
    skipped_rows = []

    for index, row in df.iterrows():
        try:
            # 1. Обработка Location
            location_name = str(row['location']).strip()
            location = Location.objects.filter(name=location_name).first()

            if not location:
                skipped_rows.append(f"Строка {index + 1}: Локация '{location_name}' не найдена в справочнике")
                continue

            # 2. Поиск модуля
            module = find_module_by_code(row['module_code'])
            if not module:
                normalized = normalize_module_code(row['module_code'])
                skipped_rows.append(
                    f"Строка {index + 1}: Модуль '{row['module_code']}' (нормализованный: '{normalized}') не найден")
                continue

            # 3. Создание/обновление группы
            group_number = str(row['group']).strip()
            application = str(row['application']).strip()

            # Формируем номер приказа о зачислении (на уровне группы)
            order_in_number = f"{group_number}-{application}-З" if application else f"{group_number}-З"

            group, group_created = Group.objects.get_or_create(
                assigned_number=group_number,
                application=application,
                defaults={
                    'module': module,
                    'location': location,
                    'start_date': parse_date(row.get('start_date')),
                    'start_face_to_face': parse_date(row.get('start_face_to_face')),
                    'end_date': parse_date(row.get('end_date')),
                    'order_in_number': order_in_number,
                    'order_in_date': parse_date(row.get('order_in_date')),  # Берём из Excel, если есть
                    'status': 'enrolling',
                }
            )

            if group_created:
                created_groups += 1
            else:
                # Обновляем только если поля пустые (не перезаписываем ручные правки)
                changed = False
                if not group.order_in_number:
                    group.order_in_number = order_in_number
                    changed = True
                if not group.order_in_date:
                    group.order_in_date = parse_date(row.get('order_in_date'))
                    changed = True

                group.module = module
                group.location = location
                group.start_date = parse_date(row.get('start_date'))
                group.start_face_to_face = parse_date(row.get('start_face_to_face'))
                group.end_date = parse_date(row.get('end_date'))

                if changed:
                    group.save()
                updated_groups += 1

            # 4. Назначение куратора
            curator_surname = str(row.get('curator', '')).strip()
            if curator_surname:
                curator = find_staff_by_surname(curator_surname)
                if curator and group.curator != curator:
                    group.curator = curator
                    group.save()

            # 5. Обработка студента и зачисления
            student = find_student_by_surname(row['student'])
            if not student:
                skipped_rows.append(f"Строка {index + 1}: Студент '{row['student']}' не найден в базе")
                continue

            number_in_group = int(row['number_in_group'])

            # order_in_number и order_in_date больше НЕ заполняем в Enrollment
            # Они теперь подтягиваются из группы через property
            enrollment, enr_created = Enrollment.objects.get_or_create(
                group=group,
                student=student,
                defaults={
                    'number_in_group': number_in_group,
                    'status': 'enrolled',
                }
            )

            if enr_created:
                created_enrollments += 1
            else:
                enrollment.number_in_group = number_in_group
                enrollment.save()
                updated_enrollments += 1

        except Exception as e:
            skipped_rows.append(f"Строка {index + 1}: Ошибка - {str(e)}")

    return {
        'groups_created': created_groups,
        'groups_updated': updated_groups,
        'enrollments_created': created_enrollments,
        'enrollments_updated': updated_enrollments,
        'skipped': skipped_rows,
    }