from datetime import date, datetime, timezone
from importlib import import_module
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection
from django.urls import reverse
from rest_framework.test import APITestCase

from execution.models import Assessment, Enrollment, Group
from people.models import Student
from references.models import Location
from training.models import Course, Module, Section, Stage


class BulkDismissalTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.methodist = get_user_model().objects.create_user(username='dismissal-methodist', is_staff=True)
        course = Course.objects.create(title='Synthetic course')
        module = Module.objects.create(course=course, title='Synthetic module', code='TEST', duration=4)
        stage = Stage.objects.create(module=module, title='Synthetic stage')
        cls.section = Section.objects.create(stage=stage, title='Exam', grade_type='binary', duration_hours=4)
        location = Location.objects.create(name='Krasnoyarsk test', timezone='Asia/Krasnoyarsk')
        cls.group = Group.objects.create(module=module, assigned_number='SYN-1', location=location,
                                         status='in_progress', start_date=date(2026, 11, 20))
        cls.absentee = Enrollment.objects.create(group=cls.group, number_in_group=2,
            student=Student.objects.create(surname='Absent', name='Student'))
        cls.passed = Enrollment.objects.create(group=cls.group, number_in_group=1,
            student=Student.objects.create(surname='Passed', name='Student'))
        Assessment.objects.create(enrollment=cls.passed, section=cls.section, score=1,
                                  assessment_date=cls.group.start_date)

    def setUp(self):
        self.client.force_authenticate(self.methodist)

    def url(self, name):
        return reverse(f'docs_api:{name}', args=[self.group.pk])

    def test_no_show_stays_in_journal_and_documents_use_generated_order_number(self):
        with patch('django.utils.timezone.now', return_value=datetime(2026, 11, 23, 18, tzinfo=timezone.utc)):
            response = self.client.post(self.url('dismiss_failed'), {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.absentee.refresh_from_db()
        self.passed.refresh_from_db()
        self.assertEqual(self.passed.status, 'enrolled')
        self.assertEqual(self.absentee.dismissal_date, date(2026, 11, 24))
        self.assertEqual(self.absentee.order_out_date, self.absentee.dismissal_date)
        self.assertEqual(self.absentee.order_out_number, 'SYN-1-ОТ')

        journal = self.client.get(self.url('group_grades_api')).data['students']
        self.assertEqual([(row['number_in_group'], row['status']) for row in journal],
                         [(1, 'enrolled'), (2, 'dismissed')])
        self.assertEqual(journal[1]['status_display'], 'Отчислен')
        self.assertIsNone(journal[1]['assessments'][0]['score'])

        response = self.client.post(self.url('group_grades_api'), {'updates': [{
            'enrollment_id': self.absentee.pk, 'section_id': self.section.pk, 'score': 1,
        }]}, format='json')
        self.assertEqual(response.data['saved_count'], 0)
        self.assertFalse(self.absentee.assessments.exists())

        # Inspect the rendered templates handed to the PDF writer.
        with TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root), \
                patch('docs.services.document_storage.HTML') as pdf:
            for kind, expected in [('dismissal_ot', 'SYN-1-ОТ'), ('dismissal_reference', 'SYN-1-ОТ-С-2')]:
                response = self.client.post(self.url('api_save_document'), {'document_type': kind}, format='json')
                self.assertEqual(response.status_code, 200, response.data)
                html = pdf.call_args.kwargs['string']
                self.assertIn(expected, html)
                self.assertIn('24.11.2026', html)

        self.client.post(self.url('dismiss_failed'), {}, format='json')
        self.absentee.refresh_from_db()
        self.assertEqual(self.absentee.order_out_date, date(2026, 11, 24))

    def test_unrelated_user_cannot_dismiss_group(self):
        user = get_user_model().objects.create_user(username='dismissal-unrelated')
        self.client.force_authenticate(user)
        self.assertEqual(self.client.post(self.url('dismiss_failed'), {}, format='json').status_code, 403)
        self.absentee.refresh_from_db()
        self.assertEqual(self.absentee.status, 'enrolled')

    def test_existing_rows_recover_number_without_overwriting_issued_order(self):
        reason = 'Неуспеваемость (не сданы все оцениваемые разделы)'
        Enrollment.objects.filter(pk__in=[self.absentee.pk, self.passed.pk]).update(
            status='dismissed', dismissal_reason=reason, dismissal_date=date(2026, 11, 24),
        )
        Enrollment.objects.filter(pk=self.passed.pk).update(order_out_number='EXISTING-ОТ')
        migration = import_module('execution.migrations.0011_restore_bulk_dismissal_numbers')
        migration.restore_order_numbers(apps, SimpleNamespace(connection=connection))
        self.absentee.refresh_from_db()
        self.passed.refresh_from_db()
        self.assertEqual(self.absentee.order_out_number, 'SYN-1-ОТ')
        self.assertEqual(self.absentee.order_out_date, self.absentee.dismissal_date)
        self.assertEqual(self.passed.order_out_number, 'EXISTING-ОТ')
