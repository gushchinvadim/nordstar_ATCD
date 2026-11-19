import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import patch
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from people.models import Student, Staff
from training.models import Course, Module
from .models import Group, Enrollment, ComplianceLog


class MethodistMaintenanceTests(APITestCase):
    def setUp(self):
        users=get_user_model()
        self.methodist=users.objects.create_user('methodist-maintenance',password='Initial-methodist-pass-45')
        Staff.objects.create(user=self.methodist,full_name='Test Methodist',fptitle=True)
        self.listener=users.objects.create_user('listener-maintenance',password='Initial-listener-pass-45',last_login='2026-11-18T12:00:00Z')
        self.student=Student.objects.create(user=self.listener,surname='OldSurname',name='TestName',email='listener@example.test')
        module=Module.objects.create(course=Course.objects.create(title='Synthetic course'),title='Synthetic module',code='TEST-MODULE',duration=2)
        self.group=Group.objects.create(module=module,assigned_number='TEST-ARCHIVE/1',start_date=date(2026,11,18),status='completed')
        self.enrollment=Enrollment.objects.create(group=self.group,student=self.student,number_in_group=1,status='completed')
        self.client.force_authenticate(self.methodist)
        self.detail=reverse('execution:methodist_student',args=[self.student.pk])
        self.reset=reverse('execution:methodist_student_reset',args=[self.student.pk])
        self.archive=reverse('execution:methodist_archive_group',args=[self.group.pk])
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        settings=override_settings(MEDIA_ROOT=self.temp.name);settings.enable();self.addCleanup(settings.disable)

    def folder(self,group=None):
        from docs.services.document_storage import DocumentStorageService
        return Path(DocumentStorageService(group or self.group).base_path)

    def test_search_and_edit_preserve_identity_enrollment_and_old_signatures(self):
        log=ComplianceLog.objects.create(student=self.student,enrollment=self.enrollment,action_type='student_grade_ack')
        # Simulate a pre-migration signature with no captured name.
        ComplianceLog.objects.filter(pk=log.pk).update(actor_name_snapshot='')
        original_time=log.timestamp
        response=self.client.get(reverse('execution:methodist_students'),{'search':'OldSurname TestName'})
        self.assertEqual(response.data['count'],1)
        response=self.client.patch(self.detail,{'surname':'NewSurname','patronymic':'Middle'},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.student.refresh_from_db();self.enrollment.refresh_from_db();self.listener.refresh_from_db();log.refresh_from_db()
        self.assertEqual(self.enrollment.student_id,self.student.pk)
        self.assertEqual(self.student.user_id,self.listener.pk)
        self.assertEqual(self.listener.username,'listener-maintenance')
        self.assertEqual(self.listener.last_name,'NewSurname')
        self.assertEqual(log.timestamp,original_time)
        self.assertIn('OldSurname TestName',log.signature_string)
        self.assertNotIn('NewSurname',log.signature_string)
        new_log=ComplianceLog.objects.create(student=self.student,action_type='student_grade_ack')
        self.assertIn('NewSurname',new_log.signature_string)
        self.assertEqual(LogEntry.objects.filter(object_id=str(self.student.pk)).count(),1)

    def test_personal_edit_rejects_assignments_and_privilege_fields(self):
        for payload in [{'user':self.methodist.pk},{'is_staff':True},{'enrollments':[]},{'username':'changed'}]:
            self.assertEqual(self.client.patch(self.detail,payload,format='json').status_code,400)
        self.listener.refresh_from_db();self.assertFalse(self.listener.is_staff)

    def test_reset_returns_temporary_password_once_and_revokes_old_access(self):
        old_refresh=RefreshToken.for_user(self.listener)
        old_access=str(old_refresh.access_token)
        response=self.client.post(self.reset,{'confirm':True},format='json')
        self.assertEqual(response.status_code,200,response.data)
        temporary=response.data['temporary_password']
        self.assertEqual(response['Cache-Control'],'no-store')
        self.listener.refresh_from_db()
        self.assertTrue(self.listener.check_password(temporary))
        self.assertFalse(self.listener.check_password('Initial-listener-pass-45'))
        self.assertIsNone(self.listener.last_login)
        self.assertNotIn(temporary,LogEntry.objects.latest('pk').change_message)
        detail=self.client.get(self.detail)
        self.assertNotIn('temporary_password',detail.data)
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+old_access)
        self.assertEqual(client.get(reverse('docs_api:api_me')).status_code,401)
        self.assertEqual(client.post(reverse('token_refresh'),{'refresh':str(old_refresh)},format='json').status_code,401)
        login=client.post(reverse('token_obtain_pair'),{'username':self.listener.username,'password':temporary},format='json')
        self.assertEqual(login.status_code,200)

    def test_personal_password_change_returns_working_replacement_tokens(self):
        client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+str(RefreshToken.for_user(self.listener).access_token))
        response=client.post(reverse('execution:change_password'),{'old_password':'Initial-listener-pass-45','new_password':'Personal-password-908'},format='json')
        self.assertEqual(response.status_code,200)
        self.assertEqual(client.get(reverse('docs_api:api_me')).status_code,401)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'])
        self.assertEqual(client.get(reverse('docs_api:api_me')).status_code,200)

    def test_reset_requires_confirmation_and_rejects_staff_account(self):
        self.assertEqual(self.client.post(self.reset,{},format='json').status_code,400)
        Staff.objects.create(user=self.listener,full_name='Staff and student')
        self.assertEqual(self.client.post(self.reset,{'confirm':True},format='json').status_code,400)
        self.listener.refresh_from_db();self.assertTrue(self.listener.check_password('Initial-listener-pass-45'))

    def test_ordinary_user_cannot_use_methodist_actions(self):
        self.client.force_authenticate(self.listener)
        self.assertEqual(self.client.get(reverse('execution:methodist_students')).status_code,403)
        self.assertEqual(self.client.patch(self.detail,{'surname':'Bad'}).status_code,403)
        self.assertEqual(self.client.post(self.reset,{'confirm':True}).status_code,403)
        self.assertEqual(self.client.post(self.archive,{'confirm_delete_files':True}).status_code,403)

    def test_archive_deletes_only_own_generated_files_and_preserves_database(self):
        folder=self.folder();folder.mkdir(parents=True);(folder/'test.pdf').write_bytes(b'synthetic')
        outside=Path(self.temp.name)/'unrelated.pdf';outside.write_bytes(b'preserve')
        self.assertEqual(self.client.post(self.archive,{},format='json').status_code,400)
        response=self.client.post(self.archive,{'confirm_delete_files':True},format='json')
        self.assertEqual(response.status_code,200,response.data)
        self.group.refresh_from_db();self.assertEqual(self.group.status,'archived')
        self.assertFalse(folder.exists());self.assertTrue(outside.exists())
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())
        self.assertEqual(self.client.post(self.archive,{'confirm_delete_files':True},format='json').status_code,200)

    def test_archive_rejects_active_group_and_failed_file_removal(self):
        self.group.status='in_progress';self.group.save(update_fields=['status'])
        self.assertEqual(self.client.post(self.archive,{'confirm_delete_files':True},format='json').status_code,400)
        self.group.status='completed';self.group.save(update_fields=['status'])
        self.folder().mkdir(parents=True)
        with patch('execution.methodist_views.shutil.rmtree',side_effect=OSError('synthetic failure')):
            response=self.client.post(self.archive,{'confirm_delete_files':True},format='json')
        self.assertEqual(response.status_code,400)
        self.group.refresh_from_db();self.assertEqual(self.group.status,'completed')

    def test_archive_rejects_shared_folder_and_symlink(self):
        Group.objects.create(module=self.group.module,assigned_number='TEST-ARCHIVE_1',start_date=self.group.start_date,status='completed')
        self.folder().mkdir(parents=True)
        self.assertEqual(self.client.post(self.archive,{'confirm_delete_files':True},format='json').status_code,400)
        self.assertTrue(self.folder().exists())
        Group.objects.exclude(pk=self.group.pk).delete()
        self.folder().rmdir()
        outside=Path(self.temp.name)/'protected';outside.mkdir();(outside/'data.txt').write_text('preserve')
        self.folder().symlink_to(outside,target_is_directory=True)
        self.assertEqual(self.client.post(self.archive,{'confirm_delete_files':True},format='json').status_code,400)
        self.assertTrue((outside/'data.txt').exists())

    def test_refresh_works_until_password_changes(self):
        client=APIClient()
        refresh=RefreshToken.for_user(self.listener)
        response=client.post(reverse('token_refresh'),{'refresh':str(refresh)},format='json')
        self.assertEqual(response.status_code,200,response.data)
        client.credentials(HTTP_AUTHORIZATION='Bearer '+response.data['access'])
        self.assertEqual(client.get(reverse('docs_api:api_me')).status_code,200)
