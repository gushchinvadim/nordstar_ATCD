from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from execution.models import Enrollment, Group, ScheduleItem
from people.models import Staff, Student
from training.models import Course, Module, Section, Stage


class GroupScheduleTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.user = users.objects.create_user(username='audit-user')
        cls.methodist = users.objects.create_user(username='methodist')
        Staff.objects.create(user=cls.methodist, full_name='Methodist', fptitle=True)
        cls.curator = users.objects.create_user(username='curator')
        curator = Staff.objects.create(user=cls.curator, full_name='Curator')
        cls.student = Student.objects.create(surname='Test', name='Student')

        course = Course.objects.create(title='Test course')
        module = Module.objects.create(course=course, title='Test module', duration=4)
        other_module = Module.objects.create(course=course, title='Other module', duration=4)
        stage = Stage.objects.create(module=module, title='Test stage')
        cls.section = Section.objects.create(stage=stage, title='Test section', detail='sdo', duration_hours=1)
        cls.other_section = Section.objects.create(
            stage=Stage.objects.create(module=other_module, title='Other stage'), title='Other section'
        )
        cls.group = Group.objects.create(
            assigned_number='TEST-1', module=module, curator=curator, start_date=date(2026, 11, 10)
        )
        cls.other_group = Group.objects.create(
            assigned_number='TEST-2', module=module, start_date=cls.group.start_date
        )
        cls.item = ScheduleItem.objects.create(
            group=cls.group, section=cls.section, date=cls.group.start_date, session_type='sdo'
        )

    def test_plain_user_cannot_manage_schedule(self):
        self.client.force_authenticate(self.user)
        schedule = f'/api/docs/groups/{self.group.pk}/schedule/'
        item = f'/api/docs/schedule/item/{self.item.pk}/'
        requests = [
            self.client.get(schedule),
            self.client.get(schedule + 'dropdowns/'),
            self.client.post(schedule + 'create/', {}, format='json'),
            self.client.patch(item + 'update/', {}, format='json'),
            self.client.delete(item + 'delete/'),
            self.client.post(f'/api/docs/group/{self.group.pk}/generate-schedule/'),
            self.client.patch(f'/api/docs/group/{self.group.pk}/update/', {}, format='json'),
        ]
        self.assertEqual([response.status_code for response in requests], [403] * len(requests))
        self.assertTrue(ScheduleItem.objects.filter(pk=self.item.pk).exists())

    def test_curator_can_manage_only_assigned_schedule(self):
        self.client.force_authenticate(self.curator)
        self.assertEqual(self.client.get(f'/api/docs/groups/{self.group.pk}/schedule/').status_code, 200)
        self.assertEqual(self.client.get(f'/api/docs/groups/{self.other_group.pk}/schedule/').status_code, 403)

    def test_section_must_belong_to_group_module(self):
        self.client.force_authenticate(self.methodist)
        url = f'/api/docs/groups/{self.group.pk}/schedule/create/'
        data = {'date': '2026-11-11', 'section': self.other_section.pk}
        self.assertEqual(self.client.post(url, data, format='json').status_code, 400)
        update = f'/api/docs/schedule/item/{self.item.pk}/update/'
        self.assertEqual(self.client.patch(update, data, format='json').status_code, 400)
        self.item.refresh_from_db()
        self.assertEqual(self.item.section_id, self.section.pk)

        data['section'] = self.section.pk
        self.assertEqual(self.client.post(url, data, format='json').status_code, 201)
        self.assertEqual(self.group.schedule.get(date='2026-11-11').session_type, 'sdo')

    def test_failed_schedule_generation_preserves_existing_items(self):
        self.client.force_authenticate(self.methodist)
        with patch('core.services.schedule_generator.ScheduleItem.objects.create', side_effect=ValueError('test')):
            response = self.client.post(f'/api/docs/group/{self.group.pk}/generate-schedule/')
        self.assertEqual(response.status_code, 500)
        self.assertTrue(ScheduleItem.objects.filter(pk=self.item.pk).exists())

    def test_failed_enrollment_rolls_back_group_and_prior_enrollment(self):
        self.client.force_authenticate(self.methodist)
        url = '/api/docs/groups/create/'
        valid_enrollment = {'student_id': self.student.pk, 'number_in_group': 1}
        data = {
            'serial_number': 'TEST', 'application': 'NEW', 'module_id': self.group.module_id,
            'start_date': '2026-11-10', 'enrollments': [valid_enrollment, {'number_in_group': 2}],
        }
        self.assertEqual(self.client.post(url, data, format='json').status_code, 400)
        self.assertFalse(Group.objects.filter(assigned_number='TEST-NEW').exists())
        self.assertFalse(Enrollment.objects.filter(student=self.student).exists())

        data['enrollments'] = [valid_enrollment]
        self.assertEqual(self.client.post(url, data, format='json').status_code, 201)
        self.assertTrue(Enrollment.objects.filter(group__assigned_number='TEST-NEW', student=self.student).exists())
