from datetime import date
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework.test import APITestCase
from people.models import Staff, Student
from references.models import Organization
from training.models import Course, Module, Stage, Section
from .models import Group, Enrollment, Assessment, ComplianceLog


class EnrollmentFundingTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='synthetic-funding-methodist')
        Staff.objects.create(user=self.user, full_name='Synthetic Methodist', fptitle=True)
        self.director = get_user_model().objects.create_user(username='synthetic-funding-director')
        self.director_staff = Staff.objects.create(user=self.director, full_name='Synthetic Director', tptitle=True)
        self.internal = Organization.objects.create(company_name='Synthetic NordStar')
        self.external = Organization.objects.create(company_name='Synthetic Customer')
        self.module = Module.objects.create(course=Course.objects.create(title='Synthetic course', frdo_template_type='pilot'),
            title='Synthetic module', code='FUNDING', duration=2)
        self.section = Section.objects.create(stage=Stage.objects.create(module=self.module, title='Stage'), title='Section', grade_type='numeric')
        self.group = Group.objects.create(module=self.module, assigned_number='SYNTHETIC-FUNDING', director=self.director_staff,
            start_date=date(2026, 11, 1), status='in_progress')
        self.male = Student.objects.create(name='Synthetic', surname='Male', sex='M')
        self.female = Student.objects.create(name='Synthetic', surname='Female', sex='F')
        self.first = Enrollment.objects.create(group=self.group, student=self.male, number_in_group=1,
            status='completed', completed_at=date(2026, 11, 10))
        self.second = Enrollment.objects.create(group=self.group, student=self.female, number_in_group=2,
            status='completed', completed_at=date(2026, 11, 10))
        self.client.force_authenticate(self.user)
        self.url = reverse('execution:group_funding', args=[self.group.pk])
        self.edit = reverse('docs_api:api_update_group', args=[self.group.pk])
        self.stats_url = reverse('execution:director_auc_statistics')
        self.dates = {'date_from': '2026-11-01', 'date_to': '2026-11-30'}

    def update(self, row, source, payer=None, reason='Synthetic finance evidence received'):
        return self.client.post(self.url, {'reason': reason, 'enrollments': [{'id': row.pk,
            'funding_source': source, 'payer_organization': payer.pk if payer else None, 'funding_reference': 'SYNTHETIC-CONTRACT'}]}, format='json')

    def stats(self, **filters):
        self.client.force_authenticate(self.director)
        response = self.client.get(self.stats_url, self.dates | filters)
        self.assertEqual(response.status_code, 200, response.data)
        result = response.data
        self.assertEqual(sum(row['total'] for row in result['funding']['by_source']), result['summary']['total'])
        for direction in result['by_direction']:
            for module in direction['modules']:
                self.assertEqual(sum(module[key] for key, label in Enrollment.FUNDING_CHOICES), module['total'])
        self.client.force_authenticate(self.user)
        return result

    def test_old_assignments_remain_unspecified_without_inference_from_program(self):
        self.assertEqual(self.first.funding_source, 'unspecified')
        result = self.stats()
        self.assertEqual(next(row['total'] for row in result['funding']['by_source'] if row['code'] == 'unspecified'), 2)
        self.assertEqual(result['summary']['total'], 2)

    def test_historical_financing_change_requires_reason_and_preserves_grades_signatures_and_dates(self):
        assessment = Assessment.objects.create(enrollment=self.first, section=self.section, score=5)
        signature = ComplianceLog.objects.create(enrollment=self.first, student=self.male, action_type='student_grade_ack')
        before = signature.signature_string
        self.assertEqual(self.update(self.first, 'self_paid', reason='').status_code, 400)
        self.assertEqual(self.update(self.first, 'self_paid').status_code, 200)
        self.first.refresh_from_db(); assessment.refresh_from_db(); signature.refresh_from_db()
        self.assertEqual(self.first.status, 'completed'); self.assertEqual(self.first.completed_at, date(2026, 11, 10))
        self.assertEqual(assessment.score, 5); self.assertEqual(signature.signature_string, before)
        self.assertEqual(self.first.funding_source, 'self_paid')
        self.assertIn('enrollment_funding_changed', LogEntry.objects.latest('pk').change_message)

    def test_corporate_sources_require_payer_and_physical_or_unknown_sources_reject_company(self):
        self.assertEqual(self.update(self.first, 'company_internal').status_code, 400)
        self.assertEqual(self.update(self.first, 'company_external').status_code, 400)
        self.assertEqual(self.update(self.first, 'self_paid', self.internal).status_code, 400)
        self.assertEqual(self.update(self.first, 'unspecified', self.internal).status_code, 400)
        self.assertEqual(self.update(self.first, 'company_internal', self.internal).status_code, 200)
        self.first.refresh_from_db(); self.assertEqual(self.first.payer_name_snapshot, self.internal.company_name)
        self.first.payer_organization = None
        with self.assertRaises(ValidationError): self.first.full_clean()

    def test_batch_failure_rolls_back_all_financing_and_audit_changes(self):
        Enrollment.objects.filter(pk=self.first.pk).update(status='enrolled')
        response = self.client.post(self.url, {'enrollments': [
            {'id': self.first.pk, 'funding_source': 'self_paid'},
            {'id': self.second.pk, 'funding_source': 'self_paid'},
        ]}, format='json')
        self.assertEqual(response.status_code, 400)
        self.first.refresh_from_db(); self.second.refresh_from_db()
        self.assertEqual(self.first.funding_source, 'unspecified'); self.assertEqual(self.second.funding_source, 'unspecified')
        self.assertFalse(LogEntry.objects.exists())

    def test_create_group_common_defaults_and_individual_override(self):
        response = self.client.post(reverse('docs_api:api_create_group'), {
            'serial_number': 'SYNTHETIC-CREATE', 'application': 'FUNDING', 'module_id': self.module.pk,
            'start_date': '2026-11-01', 'funding_defaults': {'funding_source': 'company_internal',
                'payer_organization': self.internal.pk, 'funding_reference': 'GROUP-DEFAULT'},
            'enrollments': [
                {'student_id': self.male.pk, 'number_in_group': 1, 'funding_source': 'self_paid', 'payer_organization': None},
                {'student_id': self.female.pk, 'number_in_group': 2},
            ]}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        rows = list(Enrollment.objects.filter(group_id=response.data['group_id']).order_by('number_in_group'))
        self.assertEqual(rows[0].funding_source, 'self_paid'); self.assertIsNone(rows[0].payer_organization_id)
        self.assertEqual(rows[1].funding_source, 'company_internal'); self.assertEqual(rows[1].payer_organization_id, self.internal.pk)

    def test_general_group_edit_preserves_enrollment_ids_financing_and_related_evidence(self):
        self.assertEqual(self.update(self.first, 'company_external', self.external).status_code, 200)
        assessment = Assessment.objects.create(enrollment=self.first, section=self.section, score=4)
        signature = ComplianceLog.objects.create(enrollment=self.first, student=self.male, action_type='student_safety_ack')
        response = self.client.patch(self.edit, {'enrollments': [
            {'id': self.first.pk, 'student_id': self.male.pk, 'number_in_group': 2, 'status': 'completed'},
            {'id': self.second.pk, 'student_id': self.female.pk, 'number_in_group': 1, 'status': 'completed'},
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.first.refresh_from_db(); assessment.refresh_from_db(); signature.refresh_from_db()
        self.assertEqual(self.first.number_in_group, 2)
        self.assertEqual(self.first.funding_source, 'company_external')
        self.assertEqual(assessment.enrollment_id, self.first.pk); self.assertEqual(signature.enrollment_id, self.first.pk)
        self.assertEqual(self.first.completed_at, date(2026, 11, 10))

    def test_unsafe_roster_removal_rejected_and_group_changes_rolled_back(self):
        response = self.client.patch(self.edit, {'start_date': '2026-12-01', 'enrollments': []}, format='json')
        self.assertEqual(response.status_code, 400)
        self.group.refresh_from_db(); self.assertEqual(self.group.start_date, date(2026, 11, 1))
        self.assertEqual(Enrollment.objects.filter(group=self.group).count(), 2)

    def test_archive_preserves_financing_and_allows_audited_corrections_without_reopening_training(self):
        self.assertEqual(self.update(self.first, 'company_external', self.external).status_code, 200)
        before = self.stats()['summary']['total']
        self.group.status = 'archived'; self.group.archived_from_status = 'completed'; self.group.save()
        self.assertEqual(self.update(self.first, 'self_paid').status_code, 200)
        self.group.refresh_from_db(); self.assertEqual(self.group.status, 'archived')
        result = self.stats(); self.assertEqual(result['summary']['total'], before)
        self.assertEqual(result['summary']['archived'], 2)

    def test_permissions_prevent_director_or_student_editing_financing(self):
        self.client.force_authenticate(self.director)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.update(self.first, 'self_paid').status_code, 403)
        self.assertEqual(self.client.get(reverse('execution:funding_references')).status_code, 403)
        self.assertEqual(self.client.get(reverse('execution:director_statistics_filters')).status_code, 200)
        response = self.client.patch(self.edit, {'enrollments': [
            {'id': self.first.pk, 'student_id': self.male.pk, 'number_in_group': 1, 'status': 'completed', 'funding_source': 'self_paid'},
            {'id': self.second.pk, 'student_id': self.female.pk, 'number_in_group': 2, 'status': 'completed'},
        ], 'funding_reason': 'Unauthorized'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.first.refresh_from_db(); self.assertEqual(self.first.funding_source, 'unspecified')

    def test_foreign_assignment_duplicate_ids_and_teaching_fields_are_rejected(self):
        other = Group.objects.create(module=self.module, assigned_number='SYNTHETIC-OTHER-FUNDING', start_date=date(2026, 11, 1))
        foreign = Enrollment.objects.create(group=other, student=self.male, number_in_group=1)
        for records in ([{'id': foreign.pk, 'funding_source': 'self_paid'}],
            [{'id': self.first.pk}, {'id': self.first.pk}], [{'id': self.first.pk, 'status': 'enrolled'}]):
            self.assertEqual(self.client.post(self.url, {'enrollments': records, 'reason': 'Test'}, format='json').status_code, 400)

    def test_payer_filters_and_financing_totals_match_module_and_global_totals(self):
        self.assertEqual(self.update(self.first, 'company_internal', self.internal).status_code, 200)
        self.assertEqual(self.update(self.second, 'company_external', self.external).status_code, 200)
        another = Group.objects.create(module=self.module, assigned_number='SYNTHETIC-SELF', start_date=date(2026, 11, 1))
        Enrollment.objects.create(group=another, student=self.male, number_in_group=1, status='completed',
            completed_at=date(2026, 11, 10), funding_source='self_paid')
        result = self.stats(); self.assertEqual(result['summary']['total'], 3)
        self.assertEqual({row['code']: row['total'] for row in result['funding']['by_source']},
            {'unspecified': 0, 'self_paid': 1, 'company_internal': 1, 'company_external': 1})
        self.assertEqual(sum(row['total'] for row in result['funding']['companies']), 2)
        self.assertEqual(self.stats(funding_source='self_paid')['summary']['total'], 1)
        result = self.stats(payer_organization=self.external.pk)
        self.assertEqual(result['summary']['total'], 1)
        self.assertEqual(result['filters']['payer_organization'], self.external.pk)

    def test_inactive_payer_remains_in_history_but_cannot_be_selected_for_new_funding(self):
        self.assertEqual(self.update(self.first, 'company_external', self.external).status_code, 200)
        original = self.external.company_name
        self.external.company_name = 'Renamed synthetic company'; self.external.is_active = False; self.external.save()
        self.assertEqual(self.update(self.second, 'company_external', self.external).status_code, 400)
        self.assertEqual(self.update(self.first, 'company_external', self.external).status_code, 200)
        self.first.refresh_from_db(); self.assertEqual(self.first.payer_name_snapshot, original)
        self.assertEqual(self.stats(payer_organization=self.external.pk)['summary']['total'], 1)

    def test_pending_financed_assignment_can_be_removed_explicitly_with_audit(self):
        Enrollment.objects.filter(group=self.group).update(status='enrolled', completed_at=None)
        self.assertEqual(self.update(self.first, 'self_paid').status_code, 200)
        response = self.client.patch(self.edit, {'enrollments': [
            {'id': self.second.pk, 'student_id': self.female.pk, 'number_in_group': 1, 'status': 'enrolled'}
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Enrollment.objects.filter(pk=self.first.pk).exists())
        self.second.refresh_from_db(); self.assertEqual(self.second.number_in_group, 1)
        self.assertIn('unused_enrollment_removed', LogEntry.objects.latest('pk').change_message)

    def test_legacy_client_without_enrollment_id_preserves_existing_identity_and_financing(self):
        self.assertEqual(self.update(self.first, 'company_internal', self.internal).status_code, 200)
        response = self.client.patch(self.edit, {'enrollments': [
            {'student_id': self.male.pk, 'number_in_group': 1, 'status': 'completed'},
            {'student_id': self.female.pk, 'number_in_group': 2, 'status': 'completed'}
        ]}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.first.refresh_from_db(); self.assertEqual(self.first.funding_source, 'company_internal')
