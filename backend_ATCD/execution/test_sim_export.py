from datetime import date, time
from django.test import override_settings
from rest_framework.test import APITestCase
from people.models import Staff, Student
from references.models import Location, Classroom
from training.models import Course, Module, Stage, Section, Subsection
from .models import Group, Enrollment, ScheduleItem
from .sim_export import wall_time


@override_settings(SIM_TRAINING_EXPORT_KEY='synthetic-test-export-key-at-least-32-characters')
class SIMExportTests(APITestCase):
    url='/api/integrations/sim-training/schedule/?from=2026-11-20&to=2026-11-21'
    def setUp(self):
        course=Course.objects.create(company_code='ППП.АУЦ.11',title='Synthetic')
        module=Module.objects.create(course=course,title='Module1',code='PPP11M1',duration=100)
        stage=Stage.objects.create(module=module,title='SIM')
        section=Section.objects.create(stage=stage,title='SIM section',detail='sim')
        sub=Subsection.objects.create(section=section,title='FFS Сессия 1',detail='sim')
        moscow=Location.objects.create(name='DME',timezone='Europe/Moscow')
        kja=Location.objects.create(name='KJA',timezone='Asia/Krasnoyarsk')
        classroom=Classroom.objects.create(location=kja,title='FFS')
        staff=Staff.objects.create(full_name='Synthetic instructor',is_instructor=True)
        self.group=Group.objects.create(module=module,assigned_number='SIM-TEST',start_date=date(2026,11,20),location=moscow,status='in_progress')
        for i in (1,2):
            student=Student.objects.create(surname='Synthetic',name='Pilot'+str(i))
            Enrollment.objects.create(group=self.group,student=student,number_in_group=i)
        self.lesson=ScheduleItem.objects.create(group=self.group,section=section,subsection=sub,date=date(2026,11,20),
            start_time=time(11,30),end_time=time(15,30),classroom=classroom,instructor=staff,session_type='sim')
        self.client.credentials(HTTP_X_SIM_INTEGRATION_KEY='synthetic-test-export-key-at-least-32-characters')

    def test_device_timezone_wins_over_group_and_only_sim_is_exported(self):
        ScheduleItem.objects.create(group=self.group,section=self.lesson.section,date=date(2026,11,20),session_type='base-1')
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,200,response.data)
        row=response.data['rows'][0]
        self.assertEqual(row['starts_at'],'2026-11-20T04:30:00+00:00')
        self.assertEqual(row['timezone'],'Asia/Krasnoyarsk'); self.assertEqual(len(row['pilots']),2)
        self.assertEqual(row['title'],'FFS Сессия 1'); self.assertEqual(row['errors'],[])
        self.assertNotIn('snils',str(response.data)); self.assertEqual(response['Cache-Control'],'no-store')

    def test_one_pilot_supported_and_three_reported(self):
        Enrollment.objects.filter(group=self.group,number_in_group=2).delete()
        self.assertEqual(self.client.get(self.url).data['rows'][0]['errors'],[])
        for i in (2,3):
            student=Student.objects.create(surname='Synthetic',name='Pilot'+str(i))
            Enrollment.objects.create(group=self.group,student=student,number_in_group=i)
        self.assertTrue(self.client.get(self.url).data['rows'][0]['errors'])

    def test_other_courses_and_cbt_do_not_leak(self):
        course=self.group.module.course; course.company_code='OTHER'; course.save()
        self.assertEqual(self.client.get(self.url).data['rows'],[])

    def test_authentication_disabled_key_and_period_are_checked(self):
        self.client.credentials(); self.assertIn(self.client.get(self.url).status_code,(401,403))
        self.client.credentials(HTTP_X_SIM_INTEGRATION_KEY='wrong'); self.assertIn(self.client.get(self.url).status_code,(401,403))
        self.client.credentials(HTTP_X_SIM_INTEGRATION_KEY='synthetic-test-export-key-at-least-32-characters')
        self.assertEqual(self.client.get(self.url.replace('2026-11-21','2027-11-21')).status_code,400)
        with override_settings(SIM_TRAINING_EXPORT_KEY=''):
            self.assertIn(self.client.get(self.url).status_code,(401,403))

    def test_cancelled_lesson_in_active_group_and_overnight(self):
        self.lesson.start_time=time(23); self.lesson.end_time=time(3); self.lesson.save()
        self.lesson.status='cancelled'; self.lesson.save(update_fields=['status'])
        row=self.client.get(self.url).data['rows'][0]
        self.assertEqual(row['status'],'cancelled')
        self.assertEqual(row['starts_at'],'2026-11-20T16:00:00+00:00')
        self.assertEqual(row['ends_at'],'2026-11-20T20:00:00+00:00')

    def test_dst_gap_or_ambiguity_requires_review(self):
        for day,clock in ((date(2026,3,29),time(2,30)),(date(2026,10,25),time(2,30))):
            with self.assertRaises(ValueError): wall_time(day,clock,'Europe/Berlin')

    def test_only_active_group_statuses_are_exported(self):
        for status in ('draft', 'completed', 'archived', 'cancelled'):
            with self.subTest(status=status):
                self.group.status=status; self.group.save(update_fields=['status'])
                response=self.client.get(self.url)
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.data['rows'],[])
        for status in ('enrolling', 'in_progress'):
            with self.subTest(status=status):
                self.group.status=status; self.group.save(update_fields=['status'])
                response=self.client.get(self.url)
                self.assertEqual([r['id'] for r in response.data['rows']],[self.lesson.pk])

    def test_archived_cancelled_group_is_not_exported_as_a_cancellation(self):
        self.group.status='archived'; self.group.archived_from_status='cancelled'
        self.group.save(update_fields=['status','archived_from_status'])
        self.assertEqual(self.client.get(self.url).data['rows'],[])
