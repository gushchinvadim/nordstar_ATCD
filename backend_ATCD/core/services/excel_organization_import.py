# core/services/excel_organization_import.py
import pandas as pd
from references.models import Location, Organization, Classroom
from people.models import Staff

REQUIRED_ORG_COLUMNS = [
    'full_name', 'location_name', 'addr', 'dept', 'company_name', 'address',
    'title', 'audience', 'contact_name'
]


def parse_str(value):
    """Безопасное преобразование в строку"""
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return str(int(value))
    result = str(value).strip()
    return result if result else None


def find_staff_by_surname(surname):
    """Найти сотрудника по фамилии"""
    surname = str(surname).strip()
    return Staff.objects.filter(full_name__icontains=surname).first()


def import_organizations(file_path):
    """Импорт локаций, организаций и аудиторий из Excel"""
    df = pd.read_excel(file_path, dtype={
        'full_name': str,
        'location_name': str,
        'company_name': str,
        'address': str,
        'title': str,
        'audience': str,
        'contact_name': str,
    })

    missing_cols = [col for col in REQUIRED_ORG_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(f"Неверный формат файла! Отсутствуют колонки: {', '.join(missing_cols)}")

    created_locations = 0
    updated_locations = 0
    created_organizations = 0
    updated_organizations = 0
    created_classrooms = 0
    updated_classrooms = 0
    skipped_rows = []

    for index, row in df.iterrows():
        try:
            # 1. Обработка Location
            location_name = str(row['location_name']).strip() if pd.notna(row['location_name']) else ''
            full_name = str(row['full_name']).strip() if pd.notna(row['full_name']) else ''
            addr_code = parse_str(row.get('addr'))
            dept_code = parse_str(row.get('dept'))

            location, loc_created = Location.objects.get_or_create(
                name=location_name,
                defaults={
                    'full_name': full_name,
                    'addr': addr_code,
                    'dept': dept_code,
                }
            )

            # Обновляем только непустые значения (не перезаписываем существующие на None)
            update_fields = {'full_name': full_name}
            if addr_code is not None:
                update_fields['addr'] = addr_code
            if dept_code is not None:
                update_fields['dept'] = dept_code

            Location.objects.filter(name=location_name).update(**update_fields)
            location.refresh_from_db()

            if loc_created:
                created_locations += 1
            else:
                updated_locations += 1
            # 2. Обработка Organization
            company_name = str(row['company_name']).strip() if pd.notna(row['company_name']) else ''
            address = str(row.get('address', '')).strip() if pd.notna(row.get('address')) else ''

            organization, org_created = Organization.objects.get_or_create(
                company_name=company_name,
                location=location,
                defaults={
                    'address': address,
                    'is_active': True,
                }
            )

            if not org_created:
                Organization.objects.filter(id=organization.id).update(address=address)
                organization.refresh_from_db()
                updated_organizations += 1
            else:
                created_organizations += 1

            # 3. Обработка Classroom
            title = str(row['title']).strip() if pd.notna(row['title']) else ''
            audience = str(row.get('audience', '')).strip() if pd.notna(row.get('audience')) else ''
            contact_surname = str(row.get('contact_name', '')).strip() if pd.notna(row.get('contact_name')) else ''

            contact_staff = None
            if contact_surname:
                contact_staff = find_staff_by_surname(contact_surname)
                if not contact_staff:
                    skipped_rows.append(f"Строка {index + 2}: Сотрудник '{contact_surname}' не найден")

            classroom, class_created = Classroom.objects.get_or_create(
                title=title,
                organization=organization,
                defaults={
                    'location': location,
                    'audience': audience,
                    'contact_name': contact_staff,
                }
            )

            if not class_created:
                Classroom.objects.filter(id=classroom.id).update(
                    audience=audience,
                    contact_name=contact_staff,
                )
                classroom.refresh_from_db()
                updated_classrooms += 1
            else:
                created_classrooms += 1

        except Exception as e:
            skipped_rows.append(f"Строка {index + 2}: Ошибка - {str(e)}")

    return {
        'locations_created': created_locations,
        'locations_updated': updated_locations,
        'organizations_created': created_organizations,
        'organizations_updated': updated_organizations,
        'classrooms_created': created_classrooms,
        'classrooms_updated': updated_classrooms,
        'skipped': skipped_rows,
    }