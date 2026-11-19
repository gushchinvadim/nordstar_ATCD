from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from people.models import Staff, Student
from training.models import Course, Module, Stage, Section
from .admin import GroupAdmin, archive_groups, restore_groups
from .group_history import group_delete_reasons
from .models import Group, Enrollment, Assessment, Certificate, ComplianceLog, ScheduleItem


class DirectorCabinetTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.director = User.objects.create_user(username='synthetic-director')
        self.staff = Staff.objects.create(user=self.director, full_name='Synthetic Director', tptitle=True)
        self.other = User.objects.create_user(username='synthetic-other-director')
        self.other_staff = Staff.objects.create(user=self.other, full_name='Other Director', tptitle=True)
        self.methodist = User.objects.create_user(username='synthetic-methodist')
        Staff.objects.create(user=self.methodist, full_name='Synthetic Methodist', fptitle=True)
        self.root = User.objects.create_superuser(username='synthetic-admin', password='Only-synthetic-42')
        self.student_user = User.objects.create_user(username='synthetic-student')
        self.student = Student.objects.create(user=self.student_user, surname='Synthetic', name='Listener')
        self.module = Module.objects.create(course=Course.objects.create(title='Synthetic course'), code='CABINET', title='Synthetic module', duration=2)
        self.section = Section.objects.create(stage=Stage.objects.create(module=self.module, title='Stage'), title='Section', grade_type='numeric')
        self.group = self.new_group('SYNTHETIC-CANCELLED', director=self.staff, cancellation_date=date(2026, 11, 3), cancellation_reason='Customer changed plans', cancelled_by=self.methodist)
        self.enrollment = Enrollment.objects.create(group=self.group, student=self.student, number_in_group=1)
        self.list_url = reverse('execution:director_cancelled_groups')
        self.detail_url = reverse('execution:director_cancelled_detail', args=[self.group.pk])
        self.archive_url = reverse('execution:director_archive_cancelled', args=[self.group.pk])
        self.client.force_authenticate(self.director)
        self.temp = TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        override = override_settings(MEDIA_ROOT=self.temp.name); override.enable(); self.addCleanup(override.disable)
        self.group_admin = GroupAdmin(Group, admin.site)
        self.request = RequestFactory().post('/admin/execution/group/')
        self.request.user = self.root; self.request.session = {}
        self.request._messages = FallbackStorage(self.request)

    def new_group(self, number, **kwargs):
        return Group.objects.create(module=self.module, assigned_number=number, start_date=date(2026, 11, 1), **({'status': 'cancelled'} | kwargs))

    def folder(self, group=None):
        from docs.services.document_storage import DocumentStorageService
        return Path(DocumentStorageService(group or self.group).base_path)

    def archive(self):
        response = self.client.post(self.archive_url, {'confirm_delete_files': True}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.group.refresh_from_db()

    def test_permissions_and_assignment_for_all_operations(self):
        for user in (self.student_user, self.methodist):
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(self.list_url).status_code, 403)
            self.assertEqual(self.client.get(self.detail_url).status_code, 403)
            self.assertEqual(self.client.post(self.archive_url, {'confirm_delete_files': True}).status_code, 403)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.client.get(self.list_url).data['count'], 0)
        self.assertEqual(self.client.get(self.detail_url).status_code, 404)
        self.assertEqual(self.client.post(self.archive_url, {'confirm_delete_files': True}).status_code, 404)
        self.other_staff.is_active = False; self.other_staff.save()
        self.client.force_authenticate(get_user_model().objects.get(pk=self.other.pk))
        self.assertEqual(self.client.get(self.list_url).status_code, 403)

    def test_period_search_status_filters_and_superuser(self):
        self.new_group('SYNTHETIC-OTHER', director=self.other_staff, cancellation_date=date(2026, 11, 3))
        response = self.client.get(self.list_url, {'date_from': '2026-11-01', 'date_to': '2026-11-10', 'search': 'CANCELLED'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['students_count'], 1)
        self.assertEqual(response.data['results'][0]['cancelled_by'], 'Synthetic Methodist')
        self.assertEqual(self.client.get(self.list_url, {'date_from': '2026-11-04'}).data['count'], 0)
        self.assertEqual(self.client.get(self.list_url, {'date_from': '2026-11-10', 'date_to': '2026-11-01'}).status_code, 400)
        self.assertEqual(self.client.get(self.list_url, {'status': 'completed'}).status_code, 400)
        self.client.force_authenticate(self.root)
        self.assertEqual(self.client.get(self.list_url).data['count'], 2)

    def test_read_only_history_includes_indirect_signatures(self):
        assessment = Assessment.objects.create(enrollment=self.enrollment, section=self.section, score=4, notes='Synthetic remark')
        signature = ComplianceLog.objects.create(assessment=assessment, student=self.student, action_type='student_grade_ack')
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200, response.data)
        history = response.data['history']
        self.assertEqual(history['students'][0]['name'], 'Synthetic Listener')
        self.assertEqual(history['assessments'][0]['notes'], 'Synthetic remark')
        self.assertEqual(history['signatures'][0]['signature'], signature.signature_string)
        self.assertTrue(response.data['deletion_blockers'])
        self.assertEqual(self.client.patch(self.detail_url, {'status': 'completed'}).status_code, 405)
        self.assertEqual(self.client.delete(self.detail_url).status_code, 405)

    def test_archive_preserves_training_and_cancelled_origin_deleting_only_own_files(self):
        assessment = Assessment.objects.create(enrollment=self.enrollment, section=self.section, score=4)
        signature = ComplianceLog.objects.create(enrollment=self.enrollment, student=self.student, action_type='student_safety_ack')
        original = signature.signature_string
        folder = self.folder(); folder.mkdir(parents=True); (folder/'synthetic.pdf').write_bytes(b'synthetic')
        outside = Path(self.temp.name)/'unrelated.pdf'; outside.write_bytes(b'preserve')
        self.assertEqual(self.client.post(self.archive_url, {}).status_code, 400)
        self.archive()
        self.assertEqual(self.group.status, 'archived')
        self.assertEqual(self.group.archived_from_status, 'cancelled')
        self.assertTrue(self.group.was_cancelled)
        self.assertEqual(self.group.cancellation_reason, 'Customer changed plans')
        self.assertFalse(folder.exists()); self.assertTrue(outside.exists())
        signature.refresh_from_db(); assessment.refresh_from_db(); self.enrollment.refresh_from_db()
        self.assertEqual(signature.signature_string, original)
        self.assertEqual(assessment.score, 4); self.assertEqual(self.enrollment.status, 'enrolled')
        self.assertEqual(self.client.get(self.list_url).data['count'], 0)
        self.assertEqual(self.client.get(self.list_url, {'status': 'archived'}).data['count'], 1)
        self.assertEqual(self.client.get(self.detail_url).status_code, 200)
        self.archive(); self.assertEqual(LogEntry.objects.filter(user=self.director).count(), 1)
        self.client.force_authenticate(self.student_user)
        self.assertEqual(self.client.get(reverse('execution:student_modules')).data, [])
        response = self.client.post(reverse('execution:student_confirm_action'), {'action_type': 'student_safety_ack', 'enrollment_id': self.enrollment.pk}, format='json')
        self.assertEqual(response.status_code, 409)

    def test_failed_file_removal_and_folder_collision_do_not_archive(self):
        folder = self.folder(); folder.mkdir(parents=True); (folder/'synthetic.pdf').write_bytes(b'synthetic')
        with patch('execution.group_archive.shutil.rmtree', side_effect=OSError('synthetic')):
            self.assertEqual(self.client.post(self.archive_url, {'confirm_delete_files': True}).status_code, 400)
        self.group.refresh_from_db(); self.assertEqual(self.group.status, 'cancelled')
        Group.objects.filter(pk=self.group.pk).update(assigned_number='COLLISION/1')
        self.new_group('COLLISION_1')
        self.assertEqual(self.client.post(self.archive_url, {'confirm_delete_files': True}).status_code, 400)
        self.assertTrue(folder.exists())

    def test_director_cannot_archive_active_or_completed_groups(self):
        for state in ('in_progress', 'completed'):
            Group.objects.filter(pk=self.group.pk).update(status=state)
            self.assertEqual(self.client.post(self.archive_url, {'confirm_delete_files': True}).status_code, 404)

    def test_admin_restores_cancelled_and_completed_to_original_states(self):
        archive_groups(self.group_admin, self.request, Group.objects.filter(pk=self.group.pk))
        self.group.refresh_from_db(); self.assertEqual(self.group.archived_from_status, 'cancelled')
        restore_groups(self.group_admin, self.request, Group.objects.filter(pk=self.group.pk))
        self.group.refresh_from_db(); self.assertEqual(self.group.status, 'cancelled')
        self.assertEqual(self.group.cancellation_date, date(2026, 11, 3))
        completed = self.new_group('SYNTHETIC-COMPLETED', status='completed')
        archive_groups(self.group_admin, self.request, Group.objects.filter(pk=completed.pk))
        restore_groups(self.group_admin, self.request, Group.objects.filter(pk=completed.pk))
        completed.refresh_from_db(); self.assertEqual(completed.status, 'completed')

    def test_admin_blocks_deletion_for_grades_signatures_certificates_or_conducted_lessons(self):
        for kind in ('grade', 'group_signature', 'enrollment_signature', 'lesson', 'certificate'):
            with self.subTest(kind=kind):
                group = self.new_group('SYNTHETIC-'+kind)
                enrollment = Enrollment.objects.create(group=group, student=self.student, number_in_group=1)
                if kind == 'grade': Assessment.objects.create(enrollment=enrollment, section=self.section, score=5)
                if kind == 'group_signature': ComplianceLog.objects.create(group=group, action_type='director_schedule_approved')
                if kind == 'enrollment_signature': ComplianceLog.objects.create(enrollment=enrollment, action_type='student_safety_ack')
                if kind == 'lesson': ScheduleItem.objects.create(group=group, section=self.section, date=date(2026, 11, 1), is_completed=True)
                if kind == 'certificate': Certificate.objects.create(enrollment=enrollment, number='TEST-CERT', student_full_name='Synthetic', module_title='Synthetic', total_hours=2)
                self.assertTrue(group_delete_reasons(group))
                self.assertFalse(self.group_admin.has_delete_permission(self.request, group))
                with self.assertRaises(PermissionDenied): self.group_admin.delete_model(self.request, group)
                self.assertTrue(Group.objects.filter(pk=group.pk).exists())

    def test_bulk_delete_checks_whole_selection_before_touching_files(self):
        protected = self.new_group('SYNTHETIC-PROTECTED')
        ComplianceLog.objects.create(group=protected, action_type='director_schedule_approved')
        folder = self.folder(); folder.mkdir(parents=True); (folder/'synthetic.pdf').write_bytes(b'preserve')
        with self.assertRaises(PermissionDenied): self.group_admin.delete_queryset(self.request, Group.objects.filter(pk__in=[self.group.pk, protected.pk]))
        self.assertTrue(folder.exists()); self.assertTrue(Group.objects.filter(pk=self.group.pk).exists())
        self.assertTrue(self.group_admin.get_deleted_objects([protected], self.request)[3])

    def test_admin_can_delete_unused_cancelled_request_and_its_files(self):
        folder = self.folder(); folder.mkdir(parents=True); (folder/'synthetic.pdf').write_bytes(b'synthetic')
        self.assertTrue(self.group_admin.has_delete_permission(self.request, self.group))
        pk = self.group.pk
        self.group_admin.delete_model(self.request, self.group)
        self.assertFalse(Group.objects.filter(pk=pk).exists()); self.assertFalse(folder.exists())
        self.assertTrue(Student.objects.filter(pk=self.student.pk).exists())
