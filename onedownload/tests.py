import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings

from .drive_catalog import _load_catalog, file_is_in_downloads_root
from .views import public_downloads, sync_drive_catalog


@override_settings(GOOGLE_DRIVE_DOWNLOADS_FOLDER_ID='root-folder')
class DriveCatalogTests(SimpleTestCase):
    @patch('onedownload.drive_catalog.catalog')
    def test_membership_uses_configured_root_catalog(self, drive_catalog):
        drive_catalog.return_value = {'categories': [], 'files': [{'id': 'inside'}]}
        self.assertTrue(file_is_in_downloads_root('inside'))
        self.assertFalse(file_is_in_downloads_root('outside'))

    @patch('onedownload.drive_catalog._children')
    def test_catalog_maps_folders_to_categories_and_files(self, children):
        children.side_effect = lambda folder_id: iter({
            'root-folder': [
                {'id': 'folder-1', 'name': 'PMFBY', 'mimeType': 'application/vnd.google-apps.folder'},
                {'id': 'root-file', 'name': 'Setup.exe', 'mimeType': 'application/octet-stream', 'size': '100', 'createdTime': '2026-08-10T12:00:00Z', 'modifiedTime': '2026-08-12T15:51:57Z'},
            ],
            'folder-1': [
                {'id': 'file-1', 'name': 'PMFBY.zip', 'mimeType': 'application/zip', 'size': '2048'},
                {'id': 'doc-1', 'name': 'Notes', 'mimeType': 'application/vnd.google-apps.document'},
            ],
        }[folder_id])
        result = _load_catalog()
        self.assertEqual([item['name'] for item in result['categories']], ['PMFBY'])
        self.assertEqual(
            [(item['name'], item['category_name']) for item in result['files']],
            [('Setup.exe', 'General'), ('PMFBY.zip', 'PMFBY')],
        )
        setup_file = result['files'][0]
        self.assertEqual(setup_file['created_time'], '2026-08-10T12:00:00Z')
        self.assertEqual(setup_file['modified_time'], '2026-08-12T15:51:57Z')

    @patch('onedownload.views.drive_catalog')
    def test_permanent_file_link_rejects_file_outside_download_root(self, drive_catalog):
        drive_catalog.return_value = {'categories': [], 'files': []}
        response = self.client.get('/downloads/file/outside/')
        self.assertEqual(response.status_code, 404)

    def test_invalid_drive_download_token_is_rejected(self):
        response = self.client.get('/downloads/drive/not-a-valid-token/')
        self.assertEqual(response.status_code, 404)

    @patch('onedownload.views.file_is_in_downloads_root', return_value=False)
    def test_signed_file_outside_download_root_is_rejected(self, _membership):
        token = signing.dumps(
            {'file_id': 'outside', 'name': 'outside.exe', 'mime_type': 'application/octet-stream'},
            salt='onedownload.drive-file.v1',
            compress=True,
        )
        response = self.client.get(f'/downloads/drive/{token}/')
        self.assertEqual(response.status_code, 404)


class DownloadSnapshotTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.catalog = {
            'categories': [{'id': 'folder-1', 'name': 'ERP'}],
            'files': [{
                'id': 'drive-file-123',
                'name': 'Software.zip',
                'mime_type': 'application/zip',
                'size': 1024,
                'category_name': 'ERP',
                'parent_id': 'folder-1',
                'created_time': '2026-08-10T12:00:00Z',
                'modified_time': '2026-08-12T15:51:57Z',
            }],
        }
        self.superuser = SimpleNamespace(is_authenticated=True, is_superuser=True)

    @patch('onedownload.views.drive_catalog')
    @patch('onedownload.views.DownloadCatalogSnapshot.objects')
    def test_download_page_uses_saved_snapshot_without_drive_api(self, objects, drive_catalog):
        objects.filter.return_value.first.return_value = SimpleNamespace(
            catalog=self.catalog,
            synced_at=None,
            file_count=1,
            category_count=1,
        )
        response = public_downloads(self.factory.get('/downloads/'))
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            b'https://drive.google.com/open?id=drive-file-123&amp;usp=drive_fs',
            response.content,
        )
        self.assertContains(response, 'Updated:')
        self.assertContains(response, '12 Aug 2026, 09:21 PM IST')
        self.assertContains(response, 'Added:')
        self.assertContains(response, '10 Aug 2026, 05:30 PM IST')
        drive_catalog.assert_not_called()

    @patch('onedownload.views.DownloadCatalogSnapshot.objects')
    def test_non_superuser_cannot_sync(self, objects):
        request = self.factory.post('/downloads/sync/')
        request.user = SimpleNamespace(is_authenticated=False, is_superuser=False)
        response = sync_drive_catalog(request)
        self.assertEqual(response.status_code, 403)
        objects.update_or_create.assert_not_called()

    @patch('onedownload.views.transaction.atomic')
    @patch('onedownload.views.DownloadCatalogSnapshot.objects')
    @patch('onedownload.views.refresh_catalog')
    def test_superuser_sync_saves_snapshot(self, refresh_catalog, objects, _atomic):
        refresh_catalog.return_value = self.catalog
        objects.filter.return_value.first.return_value = None
        snapshot = SimpleNamespace(file_count=1, category_count=1, synced_at=None)
        objects.update_or_create.return_value = (snapshot, True)
        request = self.factory.post('/downloads/sync/')
        request.user = self.superuser
        response = sync_drive_catalog(request)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['added_count'], 1)
        self.assertEqual(data['removed_count'], 0)
        self.assertEqual(data['file_count'], 1)
        objects.update_or_create.assert_called_once()
        defaults = objects.update_or_create.call_args.kwargs['defaults']
        self.assertEqual(defaults['catalog'], self.catalog)
        self.assertIs(defaults['synced_by'], self.superuser)

    @patch('onedownload.views.transaction.atomic')
    @patch('onedownload.views.DownloadCatalogSnapshot.objects')
    @patch('onedownload.views.refresh_catalog')
    def test_sync_reports_added_removed_and_current_counts(self, refresh_catalog, objects, _atomic):
        previous_catalog = {
            'categories': [],
            'files': [{'id': 'keep'}, {'id': 'remove-1'}, {'id': 'remove-2'}],
        }
        current_catalog = {
            'categories': [],
            'files': [{'id': 'keep'}, {'id': 'add-1'}],
        }
        objects.filter.return_value.first.return_value = SimpleNamespace(catalog=previous_catalog)
        refresh_catalog.return_value = current_catalog
        objects.update_or_create.return_value = (
            SimpleNamespace(file_count=2, category_count=0, synced_at=None),
            False,
        )
        request = self.factory.post('/downloads/sync/')
        request.user = self.superuser

        response = sync_drive_catalog(request)
        data = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['added_count'], 1)
        self.assertEqual(data['removed_count'], 2)
        self.assertEqual(data['file_count'], 2)
        self.assertIn('New files added: 1', data['message'])
        self.assertIn('Files removed: 2', data['message'])
        self.assertIn('Current total files: 2', data['message'])
    @patch('onedownload.views.DownloadCatalogSnapshot.objects')
    @patch('onedownload.views.refresh_catalog', side_effect=RuntimeError('Drive unavailable'))
    def test_failed_sync_does_not_replace_snapshot(self, _refresh_catalog, objects):
        request = self.factory.post('/downloads/sync/')
        request.user = self.superuser
        response = sync_drive_catalog(request)
        self.assertEqual(response.status_code, 503)
        objects.update_or_create.assert_not_called()
