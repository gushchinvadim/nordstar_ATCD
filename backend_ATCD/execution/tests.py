from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.urls import reverse
from rest_framework.test import APITestCase

from docs.services.document_storage import DocumentStorageService
from people.models import Staff, Student
from training.models import Course, Module, Section, Stage

from .models import Assessment, Certificate, ComplianceLog, Enrollment, Group, ScheduleItem


class MethodistCompleteGroupTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(username='methodist')
        cls.curator = Staff.objects.create(user=cls.user, full_name='Test Methodist', fptitle=True)
        course = Course.objects.create(title='Test course')
        module = Module.objects.create(course=course, title='Test module', duration=2)
        stage = Stage.objects.create(module=module, title='Test stage')
        section = Section.objects.create(stage=stage, title='Итоговый экзамен', grade_type='numeric')
        cls.group = Group.objects.create(
            module=module, assigned_number='TEST-CLOSE', start_date=date(2026, 1, 12), status='in_progress',
        )
        student = Student.objects.create(surname='Test', name='Student')
        cls.enrollment = Enrollment.objects.create(group=cls.group, student=student, number_in_group=1, status='completed')
        Assessment.objects.create(
            enrollment=cls.enrollment, section=section, score=5, assessment_date=cls.group.start_date,
        )
        ComplianceLog.objects.create(enrollment=cls.enrollment, action_type='student_safety_ack')

    def setUp(self):
        self.client.force_authenticate(self.user)
        self.url = reverse('execution:methodist_complete_group', args=[self.group.pk])
        self.issuance = ComplianceLog.objects.filter(
            enrollment=self.enrollment, action_type='methodist_documents_issued',
        )

    def test_missing_curator_preserves_group_status_and_date(self):
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertIn('У группы не назначен куратор', response.data['missing_items'][0])
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'in_progress')
        self.assertIsNone(self.group.actual_completion_date)
        self.assertFalse(self.issuance.exists())

    def test_issuance_failure_rolls_back_group_completion(self):
        self.group.curator = self.curator
        self.group.save(update_fields=['curator'])
        with patch.object(ComplianceLog.objects, 'bulk_create', side_effect=IntegrityError('test')):
            with self.assertRaises(IntegrityError):
                self.client.post(self.url)
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'in_progress')
        self.assertIsNone(self.group.actual_completion_date)
        self.assertFalse(self.issuance.exists())

    def test_completion_creates_one_issuance_record_even_on_retry(self):
        self.group.curator = self.curator
        self.group.save(update_fields=['curator'])
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'completed')
        self.assertIsNotNone(self.group.actual_completion_date)
        self.assertEqual(self.issuance.get().staff_id, self.curator.pk)

    def test_group_with_only_dismissed_students_closes_without_curator(self):
        self.enrollment.status = 'dismissed'
        self.enrollment.save(update_fields=['status'])
        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'completed')
        self.assertFalse(self.issuance.exists())

    def test_grades_then_finalization_provides_the_issuance_signature_to_journal(self):
        self.group.curator = self.curator
        self.group.save(update_fields=['curator'])
        self.enrollment.status = 'in_progress'
        self.enrollment.save(update_fields=['status'])
        self.assertEqual(self.client.post(self.url).status_code, 400)
        self.assertFalse(self.issuance.exists())

        complete_grades = reverse('docs_api:complete_all_passed', args=[self.group.pk])
        self.assertEqual(self.client.post(complete_grades).status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'in_progress')
        self.assertFalse(self.issuance.exists())

        # Старые группы могли быть закрыты без записи о выдаче.
        self.group.status = 'completed'
        self.group.actual_completion_date = self.group.start_date
        self.group.save(update_fields=['status', 'actual_completion_date'])
        groups_url = reverse('docs_api:api_groups_list')
        self.assertTrue(self.client.get(groups_url).data['results'][0]['has_unsigned_documents'])

        self.assertEqual(self.client.post(self.url).status_code, 200)
        self.group.refresh_from_db()
        self.assertEqual(self.group.actual_completion_date, self.group.start_date)
        self.assertFalse(self.client.get(groups_url).data['results'][0]['has_unsigned_documents'])

        certificate = Certificate.objects.create(
            enrollment=self.enrollment,
            number='TEST-JOURNAL-CERTIFICATE',
            student_full_name='Test Student',
            module_title=self.group.module.title,
            total_hours=2,
        )
        signature = self.issuance.get().signature_string
        journal = DocumentStorageService(self.group)

        for template in ('journal.html', 'journal_landscape.html'):
            with self.subTest(template=template):
                if template == 'journal_landscape.html':
                    section = self.enrollment.assessments.get().section
                    ScheduleItem.objects.bulk_create([
                        ScheduleItem(
                            group=self.group, section=section, date=date(2026, 1, day),
                            session_type='base-2',
                        )
                        for day in range(12, 29)
                    ])
                with patch.object(journal, 'save_both') as save_both:
                    journal.save_journal()

                template_name, context, _, _ = save_both.call_args.args
                self.assertEqual(template_name, f'docs/journal/{template}')
                html = render_to_string(template_name, context)
                _, marker, certificate_row = html.partition(certificate.number)
                self.assertTrue(marker)
                self.assertIn(signature, certificate_row.split('</tr>', 1)[0])
