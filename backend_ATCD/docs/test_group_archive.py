from datetime import date
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from docs.services.document_storage import DocumentStorageService
from execution.models import Group
from people.models import Staff
from training.models import Course, Module


class GroupArchiveTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.methodist = users.objects.create_user(username='archive-methodist')
        Staff.objects.create(user=cls.methodist, full_name='Synthetic Methodist', fptitle=True)
        cls.unrelated = users.objects.create_user(username='archive-unrelated')
        module = Module.objects.create(course=Course.objects.create(title='Synthetic course'),
                                      title='Synthetic module', code='TEST', duration=1)
        cls.group = Group.objects.create(module=module, assigned_number='001-СЗ/28',
                                         start_date=date(2026, 11, 28))

    def use_token(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {RefreshToken.for_user(user).access_token}')

    def url(self):
        return reverse('docs_api:api_download_group_archive', args=[self.group.pk])

    def test_methodist_can_download_saved_documents_using_token_only(self):
        self.use_token(self.methodist)
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            folder = Path(DocumentStorageService(self.group).base_path)
            (folder / 'orders').mkdir(parents=True)
            (folder / 'reports').mkdir()
            (folder / 'orders' / 'order.pdf').write_bytes(b'order')
            (folder / 'reports' / 'report.xlsx').write_bytes(b'report')
            outside = Path(media) / 'outside.pdf'
            outside.write_bytes(b'outside this group')
            (folder / 'orders' / 'external.pdf').symlink_to(outside)

            response = self.client.get(self.url())
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response['Content-Type'], 'application/zip')
            self.assertEqual(response['Content-Disposition'], 'attachment; filename="group_001_SZ_28.zip"')
            self.assertEqual(response['Cache-Control'], 'private, no-store')
            with ZipFile(BytesIO(b''.join(response.streaming_content))) as archive:
                self.assertEqual(set(archive.namelist()), {'orders/order.pdf', 'reports/report.xlsx'})
                self.assertEqual(archive.read('orders/order.pdf'), b'order')

    def test_download_requires_group_management_access(self):
        self.assertEqual(self.client.get(self.url()).status_code, 401)
        self.use_token(self.unrelated)
        self.assertEqual(self.client.get(self.url()).status_code, 403)

    def test_empty_archive_returns_not_found(self):
        self.use_token(self.methodist)
        with TemporaryDirectory() as media, self.settings(MEDIA_ROOT=media):
            self.assertEqual(self.client.get(self.url()).status_code, 404)
            Path(DocumentStorageService(self.group).base_path).mkdir(parents=True)
            response = self.client.get(self.url())
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.data['detail'], 'У группы пока нет сохранённых документов.')
