from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from people.models import Staff, Student
from references.models import Location
from training.models import Course, Module, Section, Stage
from .models import Group, Enrollment, Assessment, ComplianceLog, ScheduleItem


class GroupCancellationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cancel-methodist')
        self.staff = Staff.objects.create(user=self.user, full_name='Synthetic Methodist', fptitle=True)
        self.listener = get_user_model().objects.create_user(username='cancel-listener')
        self.student = Student.objects.create(user=self.listener, surname='Synthetic', name='Listener')
        course = Course.objects.create(title='Cancellation tests')
        module = Module.objects.create(course=course, title='Synthetic module', code='CANCEL-TEST', duration=2)
        section = Section.objects.create(stage=Stage.objects.create(module=module, title='Stage'), title='Section', grade_type='numeric')
        self.group = Group.objects.create(module=module, assigned_number='SYNTHETIC-CANCEL',
            start_date=date(2026, 1, 1), status='in_progress')
        self.enrollment = Enrollment.objects.create(group=self.group, student=self.student, number_in_group=1, status='in_progress')
        self.assessment = Assessment.objects.create(enrollment=self.enrollment, section=section, score=4)
        self.item = ScheduleItem.objects.create(group=self.group, section=section, instructor=self.staff,
            date=date.today() + timedelta(days=10))
        self.log = ComplianceLog.objects.create(enrollment=self.enrollment, student=self.student, action_type='student_safety_ack')
        self.url = reverse('execution:methodist_cancel_group', args=[self.group.pk])
        self.client.force_authenticate(self.user)
        self.payload = {'cancellation_date': '2026-01-02', 'cancellation_reason': ' Customer cancelled training. '}

    def cancel(self):
        response = self.client.post(self.url, self.payload, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.group.refresh_from_db()

    def test_cancellation_preserves_training_signatures_files_and_planned_dates(self):
        signature, timestamp = self.log.signature_string, self.log.timestamp
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder):
            from docs.services.document_storage import DocumentStorageService
            storage = Path(DocumentStorageService(self.group).base_path)
            storage.mkdir(parents=True, exist_ok=True)
            file = storage / 'synthetic.pdf'; file.write_bytes(b'synthetic-history')
            self.cancel()
            self.assertEqual(file.read_bytes(), b'synthetic-history')
        self.assertEqual(self.group.status, 'cancelled')
        self.assertEqual(self.group.cancellation_date, date(2026, 1, 2))
        self.assertEqual(self.group.cancellation_reason, 'Customer cancelled training.')
        self.assertEqual(self.group.cancelled_by_id, self.user.pk)
        self.assertIsNotNone(self.group.cancelled_at)
        self.assertEqual(self.group.start_date, date(2026, 1, 1))
        self.assertIsNone(self.group.actual_completion_date)
        self.enrollment.refresh_from_db(); self.assessment.refresh_from_db(); self.item.refresh_from_db(); self.log.refresh_from_db()
        self.assertEqual(self.enrollment.status, 'in_progress')
        self.assertEqual(self.assessment.score, 4)
        self.assertEqual(self.item.status, 'planned')
        self.assertEqual(self.log.timestamp, timestamp)
        self.assertEqual(self.log.signature_string, signature)
        self.assertEqual(LogEntry.objects.filter(user=self.user).count(), 1)

    def test_reason_and_date_required_and_future_rejected(self):
        for payload in [{}, {'cancellation_date': 'bad', 'cancellation_reason': 'reason'},
            {'cancellation_date': '2026-01-02', 'cancellation_reason': '  '},
            {'cancellation_date': '2999-01-01', 'cancellation_reason': 'reason'}]:
            self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 400)
        self.group.refresh_from_db(); self.assertEqual(self.group.status, 'in_progress')
        self.assertFalse(LogEntry.objects.exists())

    def test_local_date_and_pre_start_cancellation(self):
        self.group.location = Location.objects.create(name='TST', timezone='Asia/Tokyo')
        self.group.start_date = date(2026, 12, 1)
        self.group.save()
        with patch('execution.local_time.timezone.now', return_value=datetime(2026, 11, 18, 18, tzinfo=timezone.utc)):
            preview = self.client.get(self.url)
            self.assertEqual(str(preview.data['maximum_date']), '2026-11-19')
            self.payload['cancellation_date'] = '2026-11-19'
            self.cancel()
        self.assertEqual(self.group.cancellation_date, date(2026, 11, 19))

    def test_terminal_states_and_retries_cannot_overwrite_history(self):
        for state in ('completed', 'archived'):
            Group.objects.filter(pk=self.group.pk).update(status=state)
            self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 409)
        Group.objects.filter(pk=self.group.pk).update(status='enrolling')
        self.cancel()
        original = self.group.cancelled_at
        self.payload['cancellation_reason'] = 'overwrite'
        self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 409)
        self.group.refresh_from_db()
        self.assertEqual(self.group.cancelled_at, original)
        self.assertEqual(self.group.cancellation_reason, 'Customer cancelled training.')
        self.assertEqual(LogEntry.objects.count(), 1)

    def test_only_methodist_can_cancel(self):
        self.client.force_authenticate(self.listener)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload, format='json').status_code, 403)

    def test_cancelled_groups_leave_queues_but_remain_in_methodist_history(self):
        self.cancel()
        rows = self.client.get(reverse('docs_api:api_groups_list'), {'status': 'cancelled'}).data['results']
        self.assertEqual(rows[0]['cancellation_reason'], 'Customer cancelled training.')
        self.assertFalse(self.client.get(reverse('execution:instructor_schedule')).data['results'])
        self.client.force_authenticate(self.listener)
        self.assertEqual(self.client.get(reverse('execution:student_modules')).data, [])

    def test_stale_pages_cannot_write_grades_signatures_schedule_or_reactivate(self):
        self.cancel()
        urls = [
            (f'/api/docs/group/{self.group.pk}/update/', 'patch', {'status': 'in_progress'}),
            (f'/api/docs/groups/{self.group.pk}/grades/', 'post', {}),
            (f'/api/execution/instructor/schedule/{self.item.pk}/log/', 'post', {'action_type': 'lesson_completed'}),
            (f'/api/execution/instructor/groups/{self.group.pk}/complete/', 'post', {}),
            (f'/api/execution/instructor/grades/', 'post', {'group_id': self.group.pk, 'grades': [{'enrollment_id': self.enrollment.pk}]}),
            (f'/api/execution/instructor/log/', 'post', {'action_type': 'instructor_schedule_ack', 'group_id': self.group.pk}),
        ]
        urls.extend([
            (f'/api/docs/schedule/item/{self.item.pk}/update/', 'patch', {'date': '2026-01-01'}),
            (f'/api/docs/schedule/item/{self.item.pk}/delete/', 'delete', {}),
            (f'/api/docs/groups/{self.group.pk}/schedule/create/', 'post', {}),
            (f'/api/docs/group/{self.group.pk}/generate-schedule/', 'post', {}),
        ])
        for url, method, data in urls:
            response = getattr(self.client, method)(url, data, format='json')
            self.assertEqual(response.status_code, 409, (url, response.status_code))
        self.client.force_authenticate(self.listener)
        active = Group.objects.create(module=self.group.module, assigned_number='SYNTHETIC-ACTIVE', start_date=date.today())
        response = self.client.post(reverse('execution:student_confirm_action'),
            {'action_type': 'student_safety_ack', 'enrollment_id': self.enrollment.pk, 'group_id': active.pk}, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(ComplianceLog.objects.count(), 1)
        self.assessment.refresh_from_db(); self.assertEqual(self.assessment.score, 4)

    def test_audit_failure_rolls_back_cancellation(self):
        with patch('execution.methodist_views.audit', side_effect=IntegrityError('synthetic failure')):
            with self.assertRaises(IntegrityError):
                self.client.post(self.url, self.payload, format='json')
        self.group.refresh_from_db()
        self.assertEqual(self.group.status, 'in_progress')
        self.assertIsNone(self.group.cancelled_at)
