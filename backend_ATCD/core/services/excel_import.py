# core/services/excel_import.py
import pandas as pd
from datetime import datetime
from references.models import AircraftType, Citizenship, Location, Organization, Position, StudentProfession
from people.models import Staff, Student
from training.models import Course, Module, Stage, Section, Subsection
from core.services.aircraft_utils import get_or_create_aircraft_type

# ==========================================
# СПИСКИ ОБЯЗАТЕЛЬНЫХ КОЛОНОК ДЛЯ ВАЛИДАЦИИ
# ==========================================
REQUIRED_PROGRAM_COLUMNS = [
    'COMPANY_CODE', 'COURSE', 'AIRCRAFT_TYPE', 'APPROVED', 'APPROVED_DATE',
    'PROG_ID', 'MODULE', 'DURATION', 'MOD_ID', 'CODE', 'STAGE', 'SECTION',
    'DETAILS', 'SUB_SECTION', 'DURATION_HOURS', 'ORDER', 'GRADE_TYPE',
    'MIN_SCORE', 'ATTACHMENT_NUMBER'
]

REQUIRED_STAFF_COLUMNS = [
    'full_name', 'rauts_id', 'position', 'is_active', 'fptitle', 'tptitle',
    'email', 'phone', 'organization', 'location'
]

REQUIRED_STUDENTS_COLUMNS = [
    'surname', 'name', 'patronymic', 'sex', 'dob', 'snils', 'surname_latin',
    'name_latin', 'profession', 'dcat_id', 'citizenship_code', 'email',
    'is_active', 'aircraft_type', 'employee_id'
]

# Допустимые значения для detail
VALID_DETAILS = ['sdo', 'sim', 'base-1', 'base-2', 'base-3', 'base-4',
                 'base-5', 'base-6', 'base-7', 'base-8', 'base-9',
                 'asp-l', 'asp-w', 'none']


def parse_date(date_value):
    if pd.isna(date_value):
        return None
    if isinstance(date_value, datetime):
        return date_value.date()

    date_str = str(date_value).strip()
    for fmt in ['%d/%m/%y', '%d/%m/%Y', '%d.%m.%Y', '%Y-%m-%d']:
        try:
            return datetime.strptime(date_str, fmt).date()
        except ValueError:
            continue
    return None


def clean_snils(snils_value):
    if pd.isna(snils_value):
        return ''
    return str(snils_value).replace(' ', '').replace('-', '').replace('.', '')


def parse_bool(value):
    if pd.isna(value):
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ['1', 'true', 'да', 'yes']
    return False


def safe_int(value, default=0):
    """Безопасное преобразование в int"""
    if pd.isna(value):
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value, default=0.0):
    """Безопасное преобразование в float"""
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ==========================================
# 1. ИМПОРТ ПРОГРАММЫ ПОДГОТОВКИ
# ==========================================
def import_training_program(file_path):
    df = pd.read_excel(file_path)

    # ВАЛИДАЦИЯ ЗАГОЛОВКОВ
    missing_cols = [col for col in REQUIRED_PROGRAM_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Неверный формат файла программы! Отсутствуют обязательные колонки: {', '.join(missing_cols)}")

    created_courses = 0
    updated_courses = 0
    created_modules = 0
    updated_modules = 0
    created_stages = 0
    updated_stages = 0
    created_sections = 0
    updated_sections = 0
    created_subsections = 0
    updated_subsections = 0

    for index, row in df.iterrows():
        if pd.isna(row.get('COURSE')) and pd.isna(row.get('MODULE')):
            continue

        aircraft_type = None
        if pd.notna(row.get('AIRCRAFT_TYPE')):
            aircraft_type = get_or_create_aircraft_type(row['AIRCRAFT_TYPE'])

        # === COURSE ===
        course = None
        if pd.notna(row.get('COURSE')):
            course_title = str(row['COURSE']).strip()
            approved_text = str(row.get('APPROVED', '')).strip() if pd.notna(row.get('APPROVED')) else None

            course, created = Course.objects.get_or_create(
                title=course_title,
                defaults={
                    'company_code': str(row.get('COMPANY_CODE', '')).strip() if pd.notna(
                        row.get('COMPANY_CODE')) else '',
                    'prog_id': str(row.get('PROG_ID', '')).strip() if pd.notna(row.get('PROG_ID')) else '',
                    'approved': approved_text,
                    'approved_date': parse_date(row.get('APPROVED_DATE')) if pd.notna(
                        row.get('APPROVED_DATE')) else None,
                }
            )
            if created:
                created_courses += 1
            else:
                # Обновляем поля курса
                course.company_code = str(row.get('COMPANY_CODE', '')).strip() if pd.notna(
                    row.get('COMPANY_CODE')) else ''
                course.prog_id = str(row.get('PROG_ID', '')).strip() if pd.notna(row.get('PROG_ID')) else ''
                course.approved = approved_text
                course.approved_date = parse_date(row.get('APPROVED_DATE')) if pd.notna(
                    row.get('APPROVED_DATE')) else None
                course.save()
                updated_courses += 1

        # === MODULE ===
        # === MODULE ===
        module = None
        if pd.notna(row.get('MODULE')) and course:
            module_title = str(row['MODULE']).strip()
            module, created = Module.objects.get_or_create(
                course=course,
                title=module_title,
                aircraft_type=aircraft_type,  # ← ДОБАВИТЬ ЭТУ СТРОКУ
                defaults={
                    'duration': safe_float(row.get('DURATION')),
                    'mod_id': str(row.get('MOD_ID', '')).strip() if pd.notna(row.get('MOD_ID')) else '',
                    'code': str(row.get('CODE', '')).strip() if pd.notna(row.get('CODE')) else '',
                    'attachment_number': safe_float(row.get('ATTACHMENT_NUMBER')),
                }
            )
            if created:
                created_modules += 1
            else:
                # Обновляем поля модуля
                module.duration = safe_float(row.get('DURATION'))
                module.mod_id = str(row.get('MOD_ID', '')).strip() if pd.notna(row.get('MOD_ID')) else ''
                module.code = str(row.get('CODE', '')).strip() if pd.notna(row.get('CODE')) else ''
                module.attachment_number = safe_float(row.get('ATTACHMENT_NUMBER'))
                module.save()
                updated_modules += 1

        # === STAGE ===
        stage = None
        if pd.notna(row.get('STAGE')) and module:
            stage_title = str(row['STAGE']).strip()
            stage, created = Stage.objects.get_or_create(
                module=module, title=stage_title,
                defaults={'order': safe_int(row.get('ORDER'))}
            )
            if created:
                created_stages += 1
            else:
                # Обновляем order этапа
                stage.order = safe_int(row.get('ORDER'))
                stage.save()
                updated_stages += 1

        # === SECTION ===
        section = None
        if pd.notna(row.get('SECTION')) and stage:
            section_title = str(row['SECTION']).strip()
            detail_value = str(row.get('DETAILS', '')).strip().lower() if pd.notna(row.get('DETAILS')) else 'none'

            # Проверяем, что detail в списке допустимых
            if detail_value not in VALID_DETAILS:
                detail_value = 'none'

            section, created = Section.objects.get_or_create(
                stage=stage, title=section_title,
                defaults={
                    'duration_hours': safe_float(row.get('DURATION_HOURS')),
                    'order': safe_int(row.get('ORDER')),
                    'grade_type': str(row.get('GRADE_TYPE', 'none')).strip().lower() if pd.notna(
                        row.get('GRADE_TYPE')) else 'none',
                    'min_score': safe_int(row.get('MIN_SCORE')) if pd.notna(row.get('MIN_SCORE')) and str(
                        row['MIN_SCORE']).replace('.', '').isdigit() else None,
                    'detail': detail_value,
                }
            )
            if created:
                created_sections += 1
            else:
                # Обновляем поля секции
                section.duration_hours = safe_float(row.get('DURATION_HOURS'))
                section.order = safe_int(row.get('ORDER'))
                section.grade_type = str(row.get('GRADE_TYPE', 'none')).strip().lower() if pd.notna(
                    row.get('GRADE_TYPE')) else 'none'
                section.min_score = safe_int(row.get('MIN_SCORE')) if pd.notna(row.get('MIN_SCORE')) and str(
                    row['MIN_SCORE']).replace('.', '').isdigit() else None
                section.detail = detail_value
                section.save()
                updated_sections += 1

        # === SUBSECTION ===
        if pd.notna(row.get('SUB_SECTION')) and section:
            subsection_title = str(row['SUB_SECTION']).strip()
            sub_detail = str(row.get('DETAILS', '')).strip().lower() if pd.notna(row.get('DETAILS')) else ''

            # Проверяем, что detail в списке допустимых
            if sub_detail and sub_detail not in VALID_DETAILS:
                sub_detail = ''

            subsection, created = Subsection.objects.get_or_create(
                section=section, title=subsection_title,
                defaults={
                    'duration_hours': safe_float(row.get('DURATION_HOURS')),
                    'order': safe_int(row.get('ORDER')),
                    'detail': sub_detail,
                }
            )
            if created:
                created_subsections += 1
            else:
                # Обновляем поля подраздела
                subsection.duration_hours = safe_float(row.get('DURATION_HOURS'))
                subsection.order = safe_int(row.get('ORDER'))
                subsection.detail = sub_detail
                subsection.save()
                updated_subsections += 1

    return {
        'courses_created': created_courses, 'courses_updated': updated_courses,
        'modules_created': created_modules, 'modules_updated': updated_modules,
        'stages_created': created_stages, 'stages_updated': updated_stages,
        'sections_created': created_sections, 'sections_updated': updated_sections,
        'subsections_created': created_subsections, 'subsections_updated': updated_subsections,
    }


# ==========================================
# 2. ИМПОРТ ПЕРСОНАЛА
# ==========================================
def import_staff(file_path):
    df = pd.read_excel(file_path)

    # ВАЛИДАЦИЯ ЗАГОЛОВКОВ
    missing_cols = [col for col in REQUIRED_STAFF_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Неверный формат файла персонала! Отсутствуют обязательные колонки: {', '.join(missing_cols)}")

    created_staff = 0
    updated_staff = 0
    created_positions = 0
    created_organizations = 0
    created_locations = 0

    for index, row in df.iterrows():
        if pd.isna(row.get('full_name')):
            continue

        full_name = str(row['full_name']).strip()

        location = None
        if pd.notna(row.get('location')):
            loc_name = str(row['location']).strip()
            location, created = Location.objects.get_or_create(
                name=loc_name,
                defaults={'addr': None, 'dept': None}
            )
            if created: created_locations += 1

        organization = None
        if pd.notna(row.get('organization')):
            org_name = str(row['organization']).strip()
            organization, created = Organization.objects.get_or_create(
                company_name=org_name,
                defaults={'location': location,
                          'address': str(row.get('address', '')).strip() if pd.notna(row.get('address')) else ''}
            )
            if created: created_organizations += 1

        position = None
        if pd.notna(row.get('position')):
            pos_name = str(row['position']).strip()
            pos_code = str(row.get('position_code', '')).strip() if pd.notna(row.get('position_code')) else ''

            position, created = Position.objects.get_or_create(
                name=pos_name,
                defaults={'code': pos_code}
            )
            if created:
                created_positions += 1

        staff, created = Staff.objects.get_or_create(
            full_name=full_name,
            defaults={
                'organization': organization, 'position': position,
                'is_active': parse_bool(row.get('is_active', 1)),
                'rauts_id': str(row.get('rauts_id', '')).strip() if pd.notna(row.get('rauts_id')) else '',
                'fptitle': parse_bool(row.get('fptitle', 0)),
                'tptitle': parse_bool(row.get('tptitle', 0)),
                'email': str(row.get('email', '')).strip() if pd.notna(row.get('email')) else '',
                'phone': str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else '',
            }
        )

        if created:
            created_staff += 1
        else:
            staff.organization = organization
            staff.position = position
            staff.is_active = parse_bool(row.get('is_active', 1))
            staff.rauts_id = str(row.get('rauts_id', '')).strip() if pd.notna(row.get('rauts_id')) else ''
            staff.fptitle = parse_bool(row.get('fptitle', 0))
            staff.tptitle = parse_bool(row.get('tptitle', 0))
            staff.email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else ''
            staff.phone = str(row.get('phone', '')).strip() if pd.notna(row.get('phone')) else ''
            staff.save()
            updated_staff += 1

    return {
        'staff_created': created_staff, 'staff_updated': updated_staff,
        'positions': created_positions, 'organizations': created_organizations, 'locations': created_locations,
    }


# ==========================================
# 3. ИМПОРТ СЛУШАТЕЛЕЙ
# ==========================================
def import_students(file_path):
    df = pd.read_excel(file_path)

    # ВАЛИДАЦИЯ ЗАГОЛОВКОВ
    missing_cols = [col for col in REQUIRED_STUDENTS_COLUMNS if col not in df.columns]
    if missing_cols:
        raise ValueError(
            f"Неверный формат файла слушателей! Отсутствуют обязательные колонки: {', '.join(missing_cols)}")

    created_students = 0
    updated_students = 0
    created_professions = 0
    created_citizenships = 0
    created_aircraft_types = 0

    sex_map = {'муж': 'M', 'жен': 'F', 'м': 'M', 'ж': 'F', 'male': 'M', 'female': 'F'}

    for index, row in df.iterrows():
        if pd.isna(row.get('surname')) or pd.isna(row.get('name')):
            continue

        surname = str(row['surname']).strip()
        name = str(row['name']).strip()
        patronymic = str(row.get('patronymic', '')).strip() if pd.notna(row.get('patronymic')) else ''

        citizenship = None
        if pd.notna(row.get('citizenship_code')):
            try:
                cit_code = int(float(row['citizenship_code']))
                cit_name = str(row.get('citizenship', '')).strip() if pd.notna(
                    row.get('citizenship')) else f'Код {cit_code}'
                if not cit_name:
                    cit_name = f'Код {cit_code}'

                citizenship, created = Citizenship.objects.get_or_create(
                    code=cit_code,
                    defaults={'name': cit_name}
                )
                if not created and citizenship.name != cit_name:
                    citizenship.name = cit_name
                    citizenship.save()

                if created:
                    created_citizenships += 1
            except (ValueError, TypeError):
                pass

        profession = None
        if pd.notna(row.get('profession')):
            prof_name = str(row['profession']).strip()
            prof_code = str(row.get('dcat_id', '')).strip() if pd.notna(row.get('dcat_id')) else ''
            if prof_code.endswith('.0'):
                prof_code = prof_code[:-2]

            profession, created = StudentProfession.objects.get_or_create(
                name=prof_name,
                defaults={'code': prof_code}
            )
            if not created and profession.code != prof_code:
                profession.code = prof_code
                profession.save()

            if created:
                created_professions += 1

        aircraft_type = None
        if pd.notna(row.get('aircraft_type')):
            aircraft_type = get_or_create_aircraft_type(row['aircraft_type'])

            if not aircraft_type:
                print(
                    f"️ ВНИМАНИЕ: Тип ВС '{row['aircraft_type']}' не найден в справочнике и не описан в словаре маппинга. "
                    f"Слушатель {surname} {name} будет сохранен без привязки к типу ВС.")

        sex_raw = str(row.get('sex', 'Муж')).strip().lower()
        sex = sex_map.get(sex_raw, 'M')

        student, created = Student.objects.get_or_create(
            surname=surname, name=name, patronymic=patronymic,
            defaults={
                'sex': sex, 'dob': parse_date(row.get('dob')),
                'snils': clean_snils(row.get('snils')),
                'surname_latin': str(row.get('surname_latin', '')).strip() if pd.notna(
                    row.get('surname_latin')) else '',
                'name_latin': str(row.get('name_latin', '')).strip() if pd.notna(row.get('name_latin')) else '',
                'profession': profession,
                'dcat_id': str(row.get('dcat_id', '')).strip() if pd.notna(row.get('dcat_id')) else '',
                'citizenship': citizenship,
                'email': str(row.get('email', '')).strip() if pd.notna(row.get('email')) else '',
                'is_active': parse_bool(row.get('is_active', 1)),
                'aircraft_type': aircraft_type,
                'employee_id': str(row.get('employee_id', '')).strip() if pd.notna(row.get('employee_id')) else '',
            }
        )

        if created:
            created_students += 1
        else:
            student.sex = sex
            student.dob = parse_date(row.get('dob'))
            student.snils = clean_snils(row.get('snils'))
            student.surname_latin = str(row.get('surname_latin', '')).strip() if pd.notna(
                row.get('surname_latin')) else ''
            student.name_latin = str(row.get('name_latin', '')).strip() if pd.notna(row.get('name_latin')) else ''
            student.profession = profession
            student.dcat_id = str(row.get('dcat_id', '')).strip() if pd.notna(row.get('dcat_id')) else ''
            student.citizenship = citizenship
            student.email = str(row.get('email', '')).strip() if pd.notna(row.get('email')) else ''
            student.is_active = parse_bool(row.get('is_active', 1))
            student.aircraft_type = aircraft_type
            student.employee_id = str(row.get('employee_id', '')).strip() if pd.notna(row.get('employee_id')) else ''
            student.save()
            updated_students += 1

    return {
        'students_created': created_students, 'students_updated': updated_students,
        'professions': created_professions, 'citizenships': created_citizenships,
    }