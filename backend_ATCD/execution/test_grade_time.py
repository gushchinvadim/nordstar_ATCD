"""Regressions for grading against a group's local timetable, not server time."""
from datetime import date, datetime, time, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from people.models import Staff, Student
from references.models import Location
from training.models import Course, Module, Stage, Section
from .models import Group, Enrollment, ScheduleItem, Assessment, ComplianceLog


class LocalGradeTimeTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='local-grade-instructor', is_staff=True)
        self.staff = Staff.objects.create(user=self.user, full_name='Synthetic instructor', is_instructor=True)
        location = Location.objects.create(name='SYN-KJA', timezone='Asia/Krasnoyarsk')
        course = Course.objects.create(title='Synthetic course')
        module = Module.objects.create(course=course, title='Synthetic module', duration=1)
        stage = Stage.objects.create(module=module, title='Synthetic stage')
        self.section = Section.objects.create(stage=stage, title='Synthetic exam', grade_type='numeric')
        self.group = Group.objects.create(module=module, location=location, start_date=date(2026, 11, 20), status='in_progress')
        student = Student.objects.create(surname='Synthetic', name='Student')
        self.enrollment = Enrollment.objects.create(group=self.group, student=student, number_in_group=1, status='in_progress')
        self.lesson = ScheduleItem.objects.create(group=self.group, section=self.section, instructor=self.staff,
            date=date(2026, 11, 20), start_time=time(11, 30))
        self.client.force_login(self.user)
        self.client.force_authenticate(self.user)

    def submit(self, endpoint):
        row = {'enrollment_id': self.enrollment.pk, 'section_id': self.section.pk, 'score': 5}
        if endpoint == 'instructor':
            return self.client.post(reverse('execution:save_instructor_grades'),
                {'group_id': self.group.pk, 'grades': [row]}, format='json')
        if endpoint == 'journal_api':
            return self.client.post(reverse('docs_api:group_grades_api', args=[self.group.pk]),
                {'updates': [row]}, format='json')
        return self.client.post(reverse('docs:group_grades', args=[self.group.pk]),
            {f'score_{self.enrollment.pk}_{self.section.pk}': '5'}, format='multipart')

    def check_all_endpoints(self, now, allowed):
        for endpoint in ('instructor', 'journal_api', 'journal_html'):
            with self.subTest(endpoint=endpoint), patch('django.utils.timezone.now', return_value=now):
                response = self.submit(endpoint)
                self.assertIn(response.status_code, (200, 302) if allowed else (200, 302, 400))
                self.assertEqual(Assessment.objects.filter(enrollment=self.enrollment).exists(), allowed)
                self.assertEqual(ComplianceLog.objects.filter(enrollment=self.enrollment,
                    action_type='grades_submitted').exists(), allowed)
                if allowed:
                    signature = ComplianceLog.objects.get(enrollment=self.enrollment, action_type='grades_submitted')
                    self.assertIn('UTC+03:00' if self.group.location.timezone == 'Europe/Moscow' else 'UTC+07:00', signature.signature_string)
                ComplianceLog.objects.all().delete()
                Assessment.objects.all().delete()

    def test_krasnoyarsk_grading_allowed_at_start_while_moscow_is_four_hours_behind(self):
        self.check_all_endpoints(datetime(2026, 11, 20, 4, 30, tzinfo=dt_timezone.utc), True)

    def test_krasnoyarsk_grading_allowed_after_start(self):
        self.check_all_endpoints(datetime(2026, 11, 20, 4, 31, tzinfo=dt_timezone.utc), True)

    def test_krasnoyarsk_grading_rejected_before_local_start(self):
        self.check_all_endpoints(datetime(2026, 11, 20, 4, 29, tzinfo=dt_timezone.utc), False)

    def test_local_date_is_used_when_moscow_is_still_on_previous_day(self):
        self.lesson.start_time = time(0, 30)
        self.lesson.save(update_fields=['start_time'])
        now = datetime(2026, 11, 19, 18, 0, tzinfo=dt_timezone.utc)
        with patch('django.utils.timezone.now', return_value=now):
            response = self.submit('instructor')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(Assessment.objects.get().assessment_date, date(2026, 11, 20))
            response = self.submit('instructor')
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(Assessment.objects.get().assessment_date, date(2026, 11, 20))

    def test_missing_start_time_retains_local_midnight_boundary(self):
        self.lesson.start_time = None
        self.lesson.save(update_fields=['start_time'])
        self.check_all_endpoints(datetime(2026, 11, 19, 16, 59, tzinfo=dt_timezone.utc), False)
        self.check_all_endpoints(datetime(2026, 11, 19, 17, 0, tzinfo=dt_timezone.utc), True)

    def test_group_timezone_wins_over_active_request_timezone(self):
        with timezone.override('Asia/Tokyo'):
            self.check_all_endpoints(datetime(2026, 11, 20, 3, 0, tzinfo=dt_timezone.utc), False)

    def test_moscow_group_is_still_blocked_at_krasnoyarsk_start(self):
        self.group.location.timezone = 'Europe/Moscow'
        self.group.location.save(update_fields=['timezone'])
        self.check_all_endpoints(datetime(2026, 11, 20, 4, 30, tzinfo=dt_timezone.utc), False)
        self.check_all_endpoints(datetime(2026, 11, 20, 8, 30, tzinfo=dt_timezone.utc), True)
