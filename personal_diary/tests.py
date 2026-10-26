from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DiaryAccessSettings, DiaryEntry, DiaryMedia, ImportantEvent, DiaryPreference


class DiaryAccessTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='diary-user', password='pass')
        self.superuser = get_user_model().objects.create_superuser(username='diary-admin', password='pass')
        self.url = reverse('personal_diary:dashboard')

    def test_anonymous_user_is_redirected_to_existing_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f'{reverse("accounts:login")}?next={self.url}',
            fetch_redirect_response=False,
        )

    def test_authenticated_user_without_explicit_access_is_forbidden(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_superuser_without_explicit_access_is_forbidden(self):
        self.client.force_login(self.superuser)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_explicitly_enabled_user_can_open_diary(self):
        DiaryAccessSettings.objects.create(user=self.user, can_access_diary=True)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'आज लिखें')

    def test_access_revocation_blocks_the_diary_without_deleting_settings(self):
        settings = DiaryAccessSettings.objects.create(user=self.user, can_access_diary=True)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        settings.can_access_diary = False
        settings.save(update_fields=['can_access_diary'])
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_user_cannot_read_another_users_entry(self):
        other = get_user_model().objects.create_user(username='other-diary-user', password='pass')
        DiaryAccessSettings.objects.create(user=self.user, can_access_diary=True)
        DiaryAccessSettings.objects.create(user=other, can_access_diary=True)
        entry = DiaryEntry.objects.create(user=self.user, title='Private note', content='Only mine', entry_date=timezone.localdate())
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse('personal_diary:entry_detail', args=[entry.pk])).status_code, 404)


class DiaryPhaseTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.a = User.objects.create_user(username='diary-a', password='pass')
        self.b = User.objects.create_user(username='diary-b', password='pass')
        DiaryAccessSettings.objects.create(user=self.a, can_access_diary=True, storage_quota_bytes=10)
        DiaryAccessSettings.objects.create(user=self.b, can_access_diary=True)
        self.entry = DiaryEntry.objects.create(user=self.a, title='A secret', content='private body')

    def test_cross_user_event_media_and_export_are_private(self):
        event = ImportantEvent.objects.create(user=self.a, title='A event', event_date=timezone.localdate())
        media = DiaryMedia.objects.create(user=self.a, entry=self.entry, drive_file_id='unique-drive-id', drive_parent_folder_id='folder', original_filename='x.jpg', media_type='PHOTO', mime_type='image/jpeg', file_size=1)
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(reverse('personal_diary:event_delete', args=[event.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('personal_diary:media_download', args=[media.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('personal_diary:export_json)).status_code, 200)
        self.assertNotContains(self.client.get(reverse('personal_diary:export_json)), 'A secret')

    def test_locked_entry_never_returns_body_until_pin_verified(self):
        self.entry.is_locked = True; self.entry.save()
        DiaryPreference.objects.create(user=self.a, pin_hash=__import__('django.contrib.auth.hashers', fromlist=['make_password']).make_password('1234'))
        self.client.force_login(self.a)
        self.assertNotContains(self.client.get(reverse('personal_diary:entry_detail', args=[self.entry.pk])), 'private body')
        self.assertEqual(self.client.post(reverse('personal_diary:unlock_entry', args=[self.entry.pk]), {'pin': '1234'}).status_code, 302)
        self.assertContains(self.client.get(reverse('personal_diary:entry_detail', args=[self.entry.pk])), 'private body')

    def test_autosave_conflict_and_other_owner_denied(self):
        self.client.force_login(self.a)
        old = self.entry.updated_at.isoformat()
        response = self.client.post(reverse('personal_diary:autosave', args=[self.entry.pk]), data='{"title":"new","content":"new","updated_at":"wrong"}', content_type='application/json')
        self.assertEqual(response.status_code, 409)
        self.client.force_login(self.b)
        self.assertEqual(self.client.post(reverse('personal_diary:autosave', args=[self.entry.pk]), data='{}', content_type='application/json').status_code, 404)

    def test_invalid_signature_and_quota_are_rejected_before_drive(self):
        self.client.force_login(self.a)
        bad = SimpleUploadedFile('not-really.jpg', b'not an image', content_type='image/jpeg')
        response = self.client.post(reverse('personal_diary:media_upload', args=[self.entry.pk]), {'files': bad})
        self.assertEqual(response.status_code, 400)
        jpg = SimpleUploadedFile('real.jpg', b'\xff\xd8\xff' + b'x' * 20, content_type='image/jpeg')
        response = self.client.post(reverse('personal_diary:media_upload', args=[self.entry.pk]), {'files': jpg})
        self.assertEqual(response.status_code, 400)
