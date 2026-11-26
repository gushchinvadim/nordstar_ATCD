from datetime import timedelta
from io import BytesIO

import pandas as pd
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from core.services.excel_import import REQUIRED_PROGRAM_COLUMNS, import_training_program
from people.models import Staff
from training.models import Course, Module, Stage, Section, Subsection, Subject, InstructorQualification
from training.qualification_services import valid_qualifications


class TrainingProgramImportTests(TestCase):
    def setUp(self):
        self.subject = Subject.objects.create(code='PNP-FA', name='Наземная подготовка')

    def row(self, **overrides):
        row = dict.fromkeys(REQUIRED_PROGRAM_COLUMNS)
        row.update(COMPANY_CODE='TEST', COURSE='Тестовая программа', MODULE='Модуль 1',
            DURATION=2, MOD_ID='1', CODE='TEST-M1', STAGE='Этап 1', SECTION='Раздел 1',
            DETAILS='base-1', DURATION_HOURS=2, ORDER=1, GRADE_TYPE='numeric', MIN_SCORE=3,
            subject_code='PNP-FA', device_type='TEST')
        row.update(overrides)
        return row

    def import_rows(self, *rows):
        workbook = BytesIO()
        pd.DataFrame(rows).to_excel(workbook, index=False)
        workbook.seek(0)
        return import_training_program(workbook)

    def test_import_links_section_and_preserves_subsections_and_schedule_type(self):
        result = self.import_rows(self.row(SUB_SECTION='Задание 1'),
            self.row(SUB_SECTION='Задание 2', subject_code=None, device_type=None))
        section = Section.objects.get()
        self.assertEqual(section.subject, self.subject)
        self.assertEqual(section.teaching_device_type, 'TEST')
        self.assertEqual(section.detail, 'base-1')
        self.assertEqual(section.subsections.count(), 2)
        self.assertEqual(result['sections_created'], 1)
        self.assertEqual(Subject.objects.count(), 1)
        self.assertFalse(InstructorQualification.objects.exists())

    def test_reimport_updates_same_section_without_duplicate_curriculum(self):
        self.import_rows(self.row(device_type='CLASS'))
        section = Section.objects.get()
        result = self.import_rows(self.row())
        section.refresh_from_db()
        self.assertEqual(section.teaching_device_type, 'TEST')
        self.assertEqual(Section.objects.get().pk, section.pk)
        self.assertEqual(result['sections_created'], 0)
        self.assertEqual(Module.objects.count(), 1)
        self.assertEqual(Stage.objects.count(), 1)

    def test_legacy_and_empty_columns_preserve_existing_mapping(self):
        self.import_rows(self.row())
        legacy = self.row()
        del legacy['subject_code'], legacy['device_type']
        for row in (legacy, self.row(subject_code=None, device_type=None),
                    self.row(subject_code='  ', device_type='  ')):
            with self.subTest(row=row):
                self.import_rows(row)
                section = Section.objects.get()
                self.assertEqual(section.subject, self.subject)
                self.assertEqual(section.teaching_device_type, 'TEST')

    def test_legacy_file_can_create_unmapped_section(self):
        row = self.row()
        del row['subject_code'], row['device_type']
        self.import_rows(row)
        section = Section.objects.get()
        self.assertIsNone(section.subject_id)
        self.assertEqual(section.teaching_device_type, '')

    def test_optional_headers_codes_and_formats_accept_case_and_spaces(self):
        row = self.row()
        del row['subject_code'], row['device_type']
        row.update({' SUBJECT_CODE ': ' pnp-fa ', ' DEVICE_TYPE ': ' test '})
        self.import_rows(row)
        section = Section.objects.get()
        self.assertEqual(section.subject, self.subject)
        self.assertEqual(section.teaching_device_type, 'TEST')

    def test_invalid_mapping_rolls_back_entire_file_with_row_number(self):
        for overrides, message in (
            ({'subject_code': 'UNKNOWN'}, 'не найден'),
            ({'device_type': 'NOT-A-DEVICE'}, 'неизвестный device_type'),
            ({'subject_code': None}, 'заполните subject_code и device_type вместе'),
            ({'device_type': None}, 'заполните subject_code и device_type вместе'),
        ):
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(ValueError, f'Строка 3:.*{message}'):
                    self.import_rows(self.row(), self.row(SECTION='Раздел 2', **overrides))
                self.assertFalse(Course.objects.exists())
                self.assertFalse(Section.objects.exists())

    def test_inactive_or_ambiguous_subject_cannot_be_imported(self):
        self.subject.is_active = False
        self.subject.save(update_fields=['is_active'])
        with self.assertRaisesRegex(ValueError, 'неактивен'):
            self.import_rows(self.row())
        self.subject.is_active = True
        self.subject.save(update_fields=['is_active'])
        Subject.objects.create(code='pnp-fa', name='Дубль')
        with self.assertRaisesRegex(ValueError, 'повторяется'):
            self.import_rows(self.row())
        self.assertFalse(Course.objects.exists())

    def test_conflicting_subsection_mapping_rolls_back_existing_changes(self):
        self.import_rows(self.row(device_type='CLASS'))
        section = Section.objects.get()
        with self.assertRaisesRegex(ValueError, 'Строка 3:.*разные.*строку 2'):
            self.import_rows(self.row(SUB_SECTION='Один'),
                self.row(SUB_SECTION='Два', device_type='FFS'))
        section.refresh_from_db()
        self.assertEqual(section.teaching_device_type, 'CLASS')
        self.assertFalse(Subsection.objects.exists())

    def test_conflicting_subjects_in_same_section_are_rejected(self):
        Subject.objects.create(code='CRM', name='CRM')
        with self.assertRaisesRegex(ValueError, 'разные subject_code/device_type'):
            self.import_rows(self.row(), self.row(subject_code='CRM'))
        self.assertFalse(Course.objects.exists())

    def test_different_sections_can_have_different_formats(self):
        self.import_rows(self.row(), self.row(SECTION='Раздел 2', device_type='CLASS'))
        self.assertEqual(set(Section.objects.values_list('teaching_device_type', flat=True)),
            {'CLASS', 'TEST'})

    def test_duplicate_optional_headers_are_rejected(self):
        row = self.row()
        row['SUBJECT_CODE'] = 'PNP-FA'
        with self.assertRaisesRegex(ValueError, 'subject_code.*несколько раз'):
            self.import_rows(row)
        self.assertFalse(Course.objects.exists())

    def test_mapping_without_section_hierarchy_is_not_silently_skipped(self):
        with self.assertRaisesRegex(ValueError, 'Строка 3:.*заполните COURSE'):
            self.import_rows(self.row(), self.row(SECTION=None))
        self.assertFalse(Course.objects.exists())

    def test_imported_mapping_matches_only_valid_instructor_qualification(self):
        self.import_rows(self.row())
        user = get_user_model().objects.create_user(username='program-import-teacher')
        staff = Staff.objects.create(user=user, full_name='Тестовый преподаватель', is_instructor=True)
        today = timezone.localdate()
        qualification = InstructorQualification.objects.create(staff=staff, subject=self.subject,
            device_type='CLASS', certificate_number='TEST-DOC', is_verified=True,
            effective_from=today, valid_until=today + timedelta(days=30))
        section = Section.objects.get()
        self.assertFalse(valid_qualifications(staff, section, today).exists())
        qualification.device_type = 'TEST'
        qualification.save(update_fields=['device_type'])
        self.assertEqual(valid_qualifications(staff, section, today).get(), qualification)
        self.assertFalse(valid_qualifications(staff, section, today + timedelta(days=31)).exists())
