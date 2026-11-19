from datetime import timedelta, datetime, timezone as dt_timezone
from unittest.mock import patch
import pandas as pd
from django.contrib.auth import get_user_model
from django.contrib.admin.models import LogEntry
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from people.models import Staff
from training.models import Course, Module, Stage, Section, Subject, InstructorQualification
from training.qualification_services import register_qualification, valid_qualifications, assignment_error
from execution.models import Group, ScheduleItem, ComplianceLog
from core.services.excel_import import import_instructor_qualifications


class InstructorQualificationTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.methodist = User.objects.create_user(username='synthetic-qualification-methodist')
        Staff.objects.create(user=self.methodist, full_name='Synthetic Methodist', fptitle=True)
        self.user = User.objects.create_user(username='synthetic-teacher', password='Synthetic-pass-42')
        self.staff = Staff.objects.create(user=self.user, full_name='Synthetic Teacher', is_instructor=True)
        self.subject = Subject.objects.create(code='SYNTHETIC-SUBJECT', name='Synthetic subject')
        course = Course.objects.create(title='Synthetic course')
        module = Module.objects.create(course=course, title='Synthetic module', code='QUAL', duration=2)
        self.section = Section.objects.create(stage=Stage.objects.create(module=module, title='Stage'),
            title='Synthetic section', subject=self.subject, teaching_device_type='CLASS')
        self.today = timezone.localdate()
        self.group = Group.objects.create(module=module, assigned_number='SYNTHETIC-QUAL', start_date=self.today, status='in_progress')
        self.client.force_authenticate(self.methodist)
        self.list_url = reverse('execution:manage_instructors')
        self.detail_url = reverse('execution:manage_instructor', args=[self.staff.pk])
        self.add_url = reverse('execution:add_instructor_qualification', args=[self.staff.pk])
        self.account_url = reverse('execution:instructor_account', args=[self.staff.pk])

    def payload(self, days=30):
        return {'subject': self.subject.pk, 'device_type': 'CLASS', 'certificate_number': 'SYNTHETIC-DOC',
            'effective_from': self.today.isoformat(), 'valid_until': (self.today + timedelta(days=days)).isoformat()}

    def register(self, days=30):
        response = self.client.post(self.add_url, self.payload(days), format='json')
        self.assertEqual(response.status_code, 201, response.data)
        return InstructorQualification.objects.get(pk=response.data['id'])

    def test_manual_expiry_and_day_count_are_authoritative(self):
        row = self.register(30)
        self.assertEqual(row.valid_until, self.today + timedelta(days=30))
        self.assertEqual(row.days_left, 30)
        self.assertEqual(row.status, 'critical')
        self.assertTrue(row.is_verified)
        self.assertEqual(row.confirmed_by_id, self.methodist.pk)
        self.assertTrue(valid_qualifications(self.staff, self.section, row.valid_until).exists())
        self.assertFalse(valid_qualifications(self.staff, self.section, row.valid_until + timedelta(days=1)).exists())
        self.assertEqual(row.status_on(row.valid_until), 'expires_today')
        self.assertEqual(row.status_on(row.valid_until + timedelta(days=1)), 'expired')
        self.assertEqual(LogEntry.objects.filter(user=self.methodist).count(), 1)

    def test_legacy_calculated_dates_do_not_grant_permission(self):
        row = InstructorQualification.objects.create(staff=self.staff, subject=self.subject, certificate_number='OLD-DOC',
            issue_date=self.today - timedelta(days=1), validity_months=24)
        self.assertIsNotNone(row.legacy_expiration_date)
        self.assertIsNone(row.expiration_date)
        self.assertEqual(row.status, 'unconfirmed')
        self.assertFalse(valid_qualifications(self.staff, self.section, self.today).exists())
        data = self.client.get(self.detail_url).data['qualifications'][0]
        self.assertIsNone(data['valid_until']); self.assertIsNone(data['days_left'])
        self.assertIsNotNone(data['legacy_expiration_date'])

    def test_confirmation_requires_explicit_evidence_and_freezes_author(self):
        row = InstructorQualification.objects.create(staff=self.staff, subject=self.subject, issue_date=self.today)
        url = reverse('execution:confirm_instructor_qualification', args=[row.pk])
        self.assertEqual(self.client.post(url, {'certificate_number': 'DOC'}, format='json').status_code, 400)
        response = self.client.post(url, self.payload(45), format='json')
        self.assertEqual(response.status_code, 200, response.data)
        row.refresh_from_db(); self.assertEqual(row.valid_until, self.today + timedelta(days=45))
        self.assertEqual(row.confirmed_by, self.methodist)
        self.assertEqual(self.client.post(url, self.payload(99), format='json').status_code, 400)
        row.refresh_from_db(); self.assertEqual(row.valid_until, self.today + timedelta(days=45))

    def test_validation_rejects_partial_dates_privilege_and_backwards_period(self):
        for payload in [dict(self.payload(), certificate_number=''), dict(self.payload(), valid_until=None),
            dict(self.payload(), valid_until=(self.today - timedelta(days=1)).isoformat()),
            dict(self.payload(), is_verified=True)]:
            self.assertEqual(self.client.post(self.add_url, payload, format='json').status_code, 400)
        self.assertFalse(InstructorQualification.objects.exists())
        self.assertEqual(self.client.patch(self.detail_url, {'tptitle': True}, format='json').status_code, 400)

    def test_future_renewal_keeps_old_document_and_continuous_permission(self):
        old = self.register(30)
        data = self.payload(100); data.update(certificate_number='SYNTHETIC-NEW', reason='New document',
            effective_from=(self.today + timedelta(days=10)).isoformat())
        response = self.client.post(self.add_url, data, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        old.refresh_from_db()
        self.assertEqual(old.certificate_number, 'SYNTHETIC-DOC')
        self.assertEqual(old.valid_until, self.today + timedelta(days=30))
        self.assertFalse(old.is_active); self.assertEqual(old.superseded_by_id, response.data['id'])
        self.assertEqual(self.staff.qualifications.filter(is_active=True).count(), 1)
        self.assertEqual(valid_qualifications(self.staff, self.section, self.today).get().pk, old.pk)
        self.assertEqual(valid_qualifications(self.staff, self.section, self.today + timedelta(days=10)).get().pk, response.data['id'])
        self.assertIsNone(assignment_error(self.staff, self.section, self.today, self.today + timedelta(days=90)))
        self.assertIsNotNone(assignment_error(self.staff, self.section, self.today, self.today + timedelta(days=101)))

    def test_revocation_retains_assignments_signatures_and_reports_upcoming_problem(self):
        row = self.register(20)
        item = ScheduleItem.objects.create(group=self.group, section=self.section, instructor=self.staff, date=self.today + timedelta(days=1))
        log = ComplianceLog.objects.create(staff=self.staff, schedule_item=item, action_type='instructor_familiarized')
        signature = log.signature_string
        url = reverse('execution:revoke_instructor_qualification', args=[row.pk])
        self.assertEqual(self.client.post(url, {'reason': ' '}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {'reason': 'Counterparty withdrew permission'}, format='json').status_code, 200)
        row.refresh_from_db(); item.refresh_from_db(); log.refresh_from_db()
        self.assertEqual(item.instructor_id, self.staff.pk); self.assertEqual(log.signature_string, signature)
        self.assertEqual(row.revoked_on, self.today)
        self.assertFalse(valid_qualifications(self.staff, self.section, self.today).exists())
        detail = self.client.get(self.detail_url).data
        self.assertEqual(detail['upcoming_issues'][0]['id'], item.pk)

    def test_roster_filters_and_personal_edit_preserve_assignments_and_old_signature_name(self):
        self.register(20)
        item = ScheduleItem.objects.create(group=self.group, section=self.section, instructor=self.staff, date=self.today)
        log = ComplianceLog.objects.create(staff=self.staff, schedule_item=item, action_type='instructor_familiarized')
        ComplianceLog.objects.filter(pk=log.pk).update(actor_name_snapshot='')
        self.assertEqual(self.client.get(self.list_url, {'state': '30', 'subject': self.subject.pk}).data['count'], 1)
        self.assertEqual(self.client.get(self.list_url, {'state': 'expired'}).data['count'], 0)
        response = self.client.patch(self.detail_url, {'full_name': 'Renamed Synthetic Teacher'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        item.refresh_from_db(); log.refresh_from_db()
        self.assertEqual(item.instructor_id, self.staff.pk)
        self.assertIn('Synthetic Teacher', log.signature_string)
        self.assertNotIn('Renamed', log.signature_string)

    def test_new_instructor_and_existing_staff_account_do_not_gain_administrative_rights(self):
        response = self.client.post(self.list_url, {'full_name': 'New Synthetic Teacher'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        staff = Staff.objects.get(pk=response.data['id'])
        self.assertTrue(staff.is_instructor); self.assertFalse(staff.fptitle); self.assertFalse(staff.tptitle)
        account = self.client.post(reverse('execution:instructor_account', args=[staff.pk]),
            {'confirm': True, 'username': 'new-synthetic-teacher'}, format='json')
        self.assertEqual(account.status_code, 200, account.data)
        staff.refresh_from_db(); self.assertFalse(staff.user.is_staff); self.assertFalse(staff.user.is_superuser)
        self.assertTrue(staff.user.check_password(account.data['temporary_password']))
        self.assertEqual(account['Cache-Control'], 'no-store')
        self.client.force_authenticate(staff.user)
        self.assertIn('instructor', self.client.get(reverse('docs_api:user_roles')).data['available_roles'])
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_password_reset_revokes_old_tokens_without_logging_secret(self):
        old = RefreshToken.for_user(self.user)
        response = self.client.post(self.account_url, {'confirm': True}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(response.data['temporary_password'], LogEntry.objects.latest('pk').change_message)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.post(reverse('token_refresh'), {'refresh': str(old)}, format='json').status_code, 401)

    def test_schedule_checks_target_date_subject_and_format_and_keeps_existing_notes_editable(self):
        row = self.register(2)
        item = ScheduleItem.objects.create(group=self.group, section=self.section, date=self.today)
        url = reverse('docs_api:api_update_schedule_item', args=[item.pk])
        response = self.client.patch(url, {'instructor': self.staff.pk}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        response = self.client.patch(url, {'date': (self.today + timedelta(days=3)).isoformat()}, format='json')
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db(); self.assertEqual(item.date, self.today)
        row.valid_until = self.today - timedelta(days=1); row.save(update_fields=['valid_until'])
        self.assertEqual(self.client.patch(url, {'notes': 'Existing assignment retained'}, format='json').status_code, 200)
        self.section.teaching_device_type = 'FFS'; self.section.save()
        with self.assertRaises(ValidationError):
            ScheduleItem(group=self.group, section=self.section, instructor=self.staff, date=self.today).full_clean()

    def test_schedule_candidates_filter_qualified_instructors(self):
        self.register(2)
        url = reverse('docs_api:api_schedule_dropdowns', args=[self.group.pk])
        response = self.client.get(url, {'section_id': self.section.pk, 'date': self.today.isoformat()})
        self.assertEqual([row['id'] for row in response.data['instructors']], [self.staff.pk])
        response = self.client.get(url, {'section_id': self.section.pk, 'date': (self.today + timedelta(days=3)).isoformat()})
        self.assertEqual(response.data['instructors'], [])

    def test_excel_without_manual_expiry_cannot_overwrite_confirmed_document(self):
        row = self.register(30)
        frame = pd.DataFrame([{'full_name': self.staff.full_name, 'subject_code': self.subject.code,
            'subject_name': self.subject.name, 'issue_date': self.today, 'validity_months': 120,
            'certificate_number': 'OLD-IMPORT'}])
        with patch('core.services.excel_import.pd.read_excel', return_value=frame):
            result = import_instructor_qualifications('synthetic.xlsx', user=self.methodist)
        row.refresh_from_db()
        self.assertEqual(row.certificate_number, 'SYNTHETIC-DOC')
        self.assertEqual(row.valid_until, self.today + timedelta(days=30))
        self.assertTrue(result['warnings'])

    def test_admin_renewal_form_and_post_preserve_history_without_custom_html(self):
        row = self.register(30)
        root = get_user_model().objects.create_superuser(username='qualification-admin', password='Synthetic-root-42')
        client = Client(); client.force_login(root)
        url = reverse('admin:qualification_renew', args=[row.pk])
        self.assertEqual(client.get(url).status_code, 200)
        response = client.post(url, {'certificate_number': 'ADMIN-RENEWAL',
            'effective_from': self.today.isoformat(), 'valid_until': (self.today + timedelta(days=99)).isoformat(),
            'reason': 'Synthetic renewal', '_save': 'Save'})
        self.assertEqual(response.status_code, 302)
        row.refresh_from_db(); self.assertIsNotNone(row.superseded_by_id)
        self.assertEqual(row.certificate_number, 'SYNTHETIC-DOC')

    def test_local_day_count_uses_training_center_time(self):
        row = self.register(30)
        with timezone.override('Europe/Moscow'), patch('django.utils.timezone.now', return_value=datetime(2026, 11, 18, 22, tzinfo=dt_timezone.utc)):
            row.valid_until = timezone.localdate()
            self.assertEqual(row.days_left, 0)
            self.assertEqual(row.status, 'expires_today')

    def test_manual_excel_is_idempotent_and_does_not_rewrite_prior_document(self):
        row = self.register(30)
        frame = pd.DataFrame([{'full_name': self.staff.full_name, 'subject_code': self.subject.code,
            'subject_name': self.subject.name, 'effective_from': self.today,
            'valid_until': self.today + timedelta(days=99), 'certificate_number': 'EXCEL-RENEWAL'}])
        with patch('core.services.excel_import.pd.read_excel', return_value=frame):
            first = import_instructor_qualifications('synthetic.xlsx', user=self.methodist)
            second = import_instructor_qualifications('synthetic.xlsx', user=self.methodist)
        self.assertEqual(first['qualifications_created'], 1, first)
        self.assertEqual(second['qualifications_created'], 0, second)
        row.refresh_from_db(); self.assertEqual(row.certificate_number, 'SYNTHETIC-DOC')
        self.assertEqual(self.staff.qualifications.count(), 2)

    def test_privileged_teacher_account_and_activity_require_administrator(self):
        self.staff.tptitle = True; self.staff.save()
        self.assertEqual(self.client.post(self.account_url, {'confirm': True}, format='json').status_code, 400)
        self.assertEqual(self.client.patch(self.detail_url, {'is_active': False}, format='json').status_code, 400)
        self.staff.refresh_from_db(); self.assertTrue(self.staff.is_active)
        self.assertTrue(self.user.check_password('Synthetic-pass-42'))

    def test_missing_mapping_is_not_guessed_and_existing_teacher_is_not_unassigned(self):
        self.register(20)
        self.section.teaching_device_type = ''; self.section.save()
        item = ScheduleItem.objects.create(group=self.group, section=self.section, instructor=self.staff, date=self.today)
        response = self.client.patch(reverse('docs_api:api_update_schedule_item', args=[item.pk]),
            {'date': (self.today + timedelta(days=1)).isoformat()}, format='json')
        self.assertEqual(response.status_code, 400)
        item.refresh_from_db(); self.assertEqual(item.instructor_id, self.staff.pk)
        candidates = self.client.get(reverse('docs_api:api_schedule_dropdowns', args=[self.group.pk]),
            {'section_id': self.section.pk, 'date': self.today.isoformat()})
        self.assertEqual(candidates.data['instructors'], [])
        self.assertTrue(candidates.data['eligibility_error'])

    def test_renewal_failure_rolls_back_old_active_document(self):
        row = self.register(30)
        with patch('training.qualification_services.audit_qualification', side_effect=ValidationError('Synthetic audit failure')):
            response = self.client.post(self.add_url, dict(self.payload(99), certificate_number='FAILED', reason='Renewal'), format='json')
        self.assertEqual(response.status_code, 400)
        row.refresh_from_db(); self.assertTrue(row.is_active); self.assertIsNone(row.superseded_by_id)
        self.assertEqual(self.staff.qualifications.count(), 1)

    def test_methodist_can_create_subject_and_duplicate_or_unauthorized_creation_is_rejected(self):
        url = reverse('execution:add_instructor_subject')
        response = self.client.post(url, {'name': 'New synthetic subject', 'code': 'NEW-SUBJECT'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.client.post(url, {'name': 'Other name', 'code': 'new-subject'}, format='json').status_code, 409)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.post(url, {'name': 'Unauthorized'}, format='json').status_code, 403)

    def test_section_mapping_changes_only_qualification_metadata_not_training_plan_or_assignments(self):
        item = ScheduleItem.objects.create(group=self.group, section=self.section, instructor=self.staff, date=self.today)
        previous_title = self.section.title
        previous_hours = self.section.duration_hours
        new_subject = Subject.objects.create(name='Other synthetic subject')
        url = reverse('execution:update_instructor_section_mapping', args=[self.section.pk])
        response = self.client.patch(url, {'subject': new_subject.pk, 'teaching_device_type': 'FFS'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['upcoming_assignments_to_review'], 1)
        self.section.refresh_from_db(); item.refresh_from_db()
        self.assertEqual(self.section.title, previous_title)
        self.assertEqual(self.section.duration_hours, previous_hours)
        self.assertEqual(item.instructor_id, self.staff.pk)
        self.assertEqual(self.section.subject_id, new_subject.pk)
        self.assertEqual(self.client.patch(url, {'subject': new_subject.pk, 'teaching_device_type': 'FFS', 'title': 'Forbidden'}, format='json').status_code, 400)
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get(reverse('execution:instructor_section_mappings')).status_code, 403)

    def test_admin_import_cannot_bypass_qualification_permissions(self):
        self.user.is_staff = True; self.user.save(update_fields=['is_staff'])
        client = Client(); client.force_login(self.user)
        with patch('training.views.import_instructor_qualifications') as importer:
            response = client.post('/training/import-qualifications/', {})
        self.assertEqual(response.status_code, 403)
        importer.assert_not_called()
