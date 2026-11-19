from datetime import date
from importlib import import_module
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import override_settings
from django.urls import reverse
from openpyxl import load_workbook
from rest_framework.test import APITestCase

from execution.models import Group, Enrollment, Certificate
from people.models import Student
from training.models import Course, Module
from .services.frdo_export import FRDOExportService


class CourseDirectionTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='synthetic-frdo-methodist')
        self.client.force_authenticate(self.user)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_ROOT=self.temp.name); override.enable(); self.addCleanup(override.disable)

    def fixture(self, direction):
        course = Course.objects.create(title='Synthetic '+direction, frdo_template_type=direction, form_of_education='Очная')
        module = Module.objects.create(course=course, title='Synthetic module', code='SYNTHETIC-'+direction, duration=20)
        group = Group.objects.create(module=module, assigned_number='SYNTHETIC-'+direction,
            serial_number='SYNTHETIC', application='TEST', start_date=date(2026, 11, 1), status='completed')
        student = Student.objects.create(surname='Synthetic-'+direction, name='Test', patronymic='Student',
            snils='12345678901', dob=date(2000, 1, 1), sex='M')
        enrollment = Enrollment.objects.create(group=group, student=student, number_in_group=1,
            status='completed', completed_at=date(2026, 11, 10), order_out_date=date(2026, 11, 10))
        Certificate.objects.create(enrollment=enrollment, number='SYNTHETIC-'+direction,
            student_full_name=str(student), module_title=module.title, total_hours=20,
            issue_date=date(2026, 11, 10))
        return group

    def test_new_choices_validate_and_legacy_code_is_not_selectable(self):
        expected = {'flight_attendant', 'pilot', 'engineer', 'representative'}
        self.assertEqual({code for code, label in Course.FRDO_TEMPLATE_CHOICES}, expected)
        for code in expected:
            Course(title='Synthetic course', frdo_template_type=code).full_clean()
        with self.assertRaises(ValidationError):
            Course(title='Synthetic old code', frdo_template_type='pilot_engineer').full_clean()

    def test_all_dpo_directions_export_consistent_headers_rows_and_workbooks(self):
        for direction in ('pilot', 'engineer', 'representative'):
            with self.subTest(direction=direction):
                group = self.fixture(direction)
                service = FRDOExportService(group, self.user)
                rows, errors = service.get_data()
                self.assertEqual(errors, [])
                self.assertEqual(service.get_headers(), service.HEADERS_DPO)
                self.assertEqual(set(rows[0]), set(service.get_headers()))
                self.assertEqual(rows[0]['Наименование дополнительной профессиональной программы'], f'Synthetic {direction} — Synthetic module')
                self.assertNotIn('Наименование профессий рабочих, должностей служащих', rows[0])
                path, relative, errors = service.generate_excel()
                workbook = load_workbook(path, read_only=True)
                try:
                    self.assertEqual(list(next(workbook.active.values)), service.HEADERS_DPO)
                    self.assertEqual(workbook.active.max_row, 2)
                finally:
                    workbook.close()

    def test_flight_attendant_export_keeps_professional_training_layout(self):
        service = FRDOExportService(self.fixture('flight_attendant'), self.user)
        rows, errors = service.get_data()
        self.assertEqual(errors, [])
        self.assertEqual(service.get_headers(), service.HEADERS_ATTENDANT)
        self.assertEqual(set(rows[0]), set(service.get_headers()))
        self.assertEqual(rows[0]['Наименование профессий рабочих, должностей служащих'], 'Бортпроводник')
        self.assertNotIn('Наименование дополнительной профессиональной программы', rows[0])

    def test_dpo_saved_report_does_not_mislabel_year_column_as_missing(self):
        for direction in ('pilot', 'engineer', 'representative'):
            with self.subTest(direction=direction):
                service = FRDOExportService(self.fixture(direction), self.user)
                report = service.save_to_database()
                self.assertEqual(report.status, 'generated')
                self.assertTrue(report.items.get().is_valid)
                self.assertEqual(report.items.get().validation_error, '')

    def test_unknown_direction_cannot_silently_use_flight_attendant_layout(self):
        group = self.fixture('pilot')
        group.module.course.frdo_template_type = 'unknown'
        with self.assertRaisesMessage(ValueError, 'Неизвестное направление'):
            FRDOExportService(group, self.user)

    def test_direction_api_always_lists_all_choices_even_before_programs_exist(self):
        response = self.client.get(reverse('docs_api:api_directions_list'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual({row['code'] for row in response.data}, {'flight_attendant', 'pilot', 'engineer', 'representative'})

    def test_group_filter_uses_separate_directions(self):
        for code in ('flight_attendant', 'pilot', 'engineer', 'representative'):
            self.fixture(code)
        for code in ('flight_attendant', 'pilot', 'engineer', 'representative'):
            response = self.client.get(reverse('docs_api:api_groups_list'), {'direction': code})
            self.assertEqual(response.data['count'], 1)
            self.assertEqual(response.data['results'][0]['direction'], code)
            self.assertEqual(response.data['results'][0]['direction_display'], dict(Course.FRDO_TEMPLATE_CHOICES)[code])

    def test_data_migration_moves_only_confirmed_existing_combined_entries(self):
        migration = import_module('training.migrations.0003_split_course_directions')
        old = Course.objects.create(title='Synthetic old programme', frdo_template_type='pilot_engineer')
        attendant = Course.objects.create(title='Synthetic attendants', frdo_template_type='flight_attendant')
        migration.split_existing_courses(apps, SimpleNamespace(connection=connection))
        old.refresh_from_db(); attendant.refresh_from_db()
        self.assertEqual(old.frdo_template_type, 'pilot')
        self.assertEqual(attendant.frdo_template_type, 'flight_attendant')
        self.assertEqual(old.title, 'Synthetic old programme')

    def test_reverse_migration_refuses_to_lose_new_directions(self):
        migration = import_module('training.migrations.0003_split_course_directions')
        pilot = Course.objects.create(title='Synthetic pilot', frdo_template_type='pilot')
        Course.objects.create(title='Synthetic engineer', frdo_template_type='engineer')
        with self.assertRaises(RuntimeError):
            migration.restore_combined_courses(apps, SimpleNamespace(connection=connection))
        pilot.refresh_from_db(); self.assertEqual(pilot.frdo_template_type, 'pilot')
