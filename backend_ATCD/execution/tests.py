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

    def configure_local_dates(self):
        from references.models import Location
        from datetime import datetime, timezone
        self.group.location = Location.objects.create(name='KJA', timezone='Asia/Krasnoyarsk')
        self.group.curator = self.curator
        self.group.end_date = date(2026, 11, 19)
        self.group.save(update_fields=['location', 'curator', 'end_date'])
        self.lesson = ScheduleItem.objects.create(group=self.group, section=self.enrollment.assessments.get().section, date=self.group.end_date, is_completed=True)
        self.fixed_now = datetime(2026, 11, 19, 22, 30, tzinfo=timezone.utc)

    def test_preview_and_next_day_closure_keep_effective_date(self):
        self.configure_local_dates()
        with patch('django.utils.timezone.now', return_value=self.fixed_now):
            preview = self.client.get(self.url)
            self.assertEqual(str(preview.data['completion_date']), '2026-11-19')
            self.assertEqual(str(preview.data['maximum_date']), '2026-11-20')
            self.assertEqual(preview.data['timezone'], 'Asia/Krasnoyarsk')
            response = self.client.post(self.url, {'completion_date': '2026-11-19'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.group.refresh_from_db(); self.enrollment.refresh_from_db()
        self.assertEqual(self.group.actual_completion_date, date(2026,11,19))
        self.assertEqual(self.enrollment.completed_at, date(2026,11,19))
        audit = ComplianceLog.objects.get(group=self.group, action_type='methodist_corrected')
        self.assertEqual(audit.timestamp, self.fixed_now)
        self.assertEqual(audit.staff, self.curator)
        self.assertIn('20.11.2026 05:30 (UTC+07:00)', audit.signature_string)

    def test_invalid_dates_and_missing_reason_do_not_close_group(self):
        self.configure_local_dates()
        with patch('django.utils.timezone.now', return_value=self.fixed_now):
            for payload in [{'completion_date':'2026-11-18','completion_reason':'test'}, {'completion_date':'2026-11-21','completion_reason':'test'}, {'completion_date':'2026-11-20'}, {'completion_date':'wrong'}]:
                with self.subTest(payload=payload):
                    self.assertEqual(self.client.post(self.url,payload,format='json').status_code,400)
        self.group.refresh_from_db()
        self.assertEqual(self.group.status,'in_progress')
        self.assertFalse(self.issuance.exists())

    def test_reason_is_logged_and_closed_date_cannot_be_changed(self):
        self.configure_local_dates()
        with patch('django.utils.timezone.now', return_value=self.fixed_now):
            response = self.client.post(self.url,{'completion_date':'2026-11-20','completion_reason':'Дополнительная проверка знаний'},format='json')
            self.assertEqual(response.status_code,200,response.data)
            self.assertEqual(self.client.post(self.url,{'completion_date':'2026-11-19'},format='json').status_code,400)
        audit = ComplianceLog.objects.get(group=self.group, action_type='methodist_corrected')
        self.assertIn('Дополнительная проверка знаний',audit.notes)

    def test_students_completion_date_is_separate_from_order_date(self):
        self.configure_local_dates()
        self.enrollment.status='in_progress';self.enrollment.save(update_fields=['status'])
        with patch('django.utils.timezone.now', return_value=self.fixed_now):
            response=self.client.post(reverse('docs_api:complete_all_passed',args=[self.group.pk]),{'completion_date':'2026-11-19'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.enrollment.refresh_from_db();self.group.refresh_from_db()
        self.assertEqual(self.enrollment.completed_at,date(2026,11,19))
        self.assertEqual(self.enrollment.order_out_date,date(2026,11,20))
        self.assertEqual(self.group.status,'in_progress')

    def test_existing_certificate_is_not_silently_redated(self):
        self.configure_local_dates()
        self.enrollment.completed_at=date(2026,11,18);self.enrollment.save(update_fields=['completed_at'])
        cert=Certificate.objects.create(enrollment=self.enrollment,number='ISSUED-OLD',total_hours=2,issue_date=date(2026,11,18))
        with patch('django.utils.timezone.now', return_value=self.fixed_now):
            response=self.client.post(self.url,{'completion_date':'2026-11-19'},format='json')
        self.assertEqual(response.status_code,400)
        cert.refresh_from_db();self.assertEqual(cert.issue_date,date(2026,11,18))

    def test_signatures_follow_all_group_relations(self):
        self.configure_local_dates()
        cert=Certificate.objects.create(enrollment=self.enrollment,number='TZ-CERT',total_hours=2)
        links=[{'group':self.group},{'enrollment':self.enrollment},{'schedule_item':self.lesson},{'assessment':self.enrollment.assessments.get()},{'certificate':cert}]
        for link in links:
            with self.subTest(link=list(link)):
                log=ComplianceLog.objects.create(staff=self.curator,action_type='methodist_corrected',**link)
                ComplianceLog.objects.filter(pk=log.pk).update(timestamp=self.fixed_now);log.refresh_from_db()
                self.assertIn('20.11.2026 05:30 (UTC+07:00)',log.signature_string)
                self.assertEqual(log.timestamp,self.fixed_now)

    def test_naive_timestamp_has_safe_default_timezone(self):
        from datetime import datetime
        from django.test import override_settings
        log=ComplianceLog(group=self.group,staff=self.curator,timestamp=datetime(2026,11,19,22,30))
        with override_settings(TIME_ZONE='Europe/Moscow'):
            self.assertIn('20.11.2026 01:30 (UTC+03:00)',log.signature_string)

    def test_non_methodist_cannot_preview_or_complete(self):
        self.client.force_authenticate(get_user_model().objects.create_user('ordinary-student'))
        self.assertEqual(self.client.get(self.url).status_code,403)
        self.assertEqual(self.client.post(reverse('docs_api:complete_all_passed',args=[self.group.pk])).status_code,403)

    def test_document_context_uses_actual_date_without_altering_schedule(self):
        from docs.rendering import document_context
        self.configure_local_dates()
        self.group.actual_completion_date=date(2026,11,20)
        self.group.save(update_fields=['actual_completion_date'])
        context=document_context('docs/training_tasks/course_1/land_training_task.html',{'group':self.group})
        self.assertEqual(context['group'].end_date,date(2026,11,20))
        self.group.refresh_from_db();self.assertEqual(self.group.end_date,date(2026,11,19))
        schedule_context=document_context('docs/schedules/schedule.html',{'group':self.group})
        self.assertEqual(schedule_context['group'].end_date,date(2026,11,19))

    def test_group_render_uses_local_time_for_template_date_filters(self):
        from docs.rendering import render_group_html
        from django.template import engines
        self.configure_local_dates()
        template=engines['django'].from_string('{{ stamp|date:"d.m.Y H:i" }}')
        with patch('docs.rendering.render_to_string',side_effect=lambda name,ctx,request=None:template.render(ctx)):
            html=render_group_html('docs/schedules/schedule.html',{'group':self.group,'stamp':self.fixed_now})
        self.assertEqual(html,'20.11.2026 05:30')

    def test_legacy_enrollment_date_does_not_override_schedule_default(self):
        self.configure_local_dates()
        self.enrollment.completed_at=date(2026,11,20);self.enrollment.save(update_fields=['completed_at'])
        with patch('django.utils.timezone.now',return_value=self.fixed_now):
            response=self.client.get(self.url)
        self.assertEqual(str(response.data['completion_date']),'2026-11-19')

    def test_existing_closed_date_is_preserved_when_confirming_issuance(self):
        self.configure_local_dates()
        self.group.status='completed';self.group.actual_completion_date=date(2026,11,18)
        self.group.save(update_fields=['status','actual_completion_date'])
        with patch('django.utils.timezone.now',return_value=self.fixed_now):
            response=self.client.post(self.url)
        self.assertEqual(response.status_code,200,response.data)
        self.group.refresh_from_db()
        self.assertEqual(self.group.actual_completion_date,date(2026,11,18))
