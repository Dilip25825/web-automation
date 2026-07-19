from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Category, DownloadLink


class DownloadLinkViewsTests(TestCase):
    def setUp(self):
        self.link = DownloadLink.objects.create(
            name='7-Zip',
            description='Compression software',
            drive_link='https://drive.google.com/file/d/example/view',
            is_active=True,
        )

    def test_public_page_shows_active_links_without_login(self):
        response = self.client.get(reverse('downloads:public_downloads'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.link.name)
        self.assertContains(response, self.link.drive_link)

    def test_link_create_requires_superuser(self):
        user = get_user_model().objects.create_user(username='regularuser', password='secret123')
        self.client.force_login(user)

        response = self.client.post(reverse('downloads:link_create'))

        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_superuser_can_create_link_with_ajax_json_response(self):
        admin = get_user_model().objects.create_superuser(
            username='user',
            email='admin@example.com',
            password='secret123',
        )
        category = Category.objects.create(name='Utilities')
        self.client.force_login(admin)

        response = self.client.post(
            reverse('downloads:link_create'),
            {
                'name': 'Utility App',
                'description': 'Useful utility',
                'categories': [category.pk],
                'drive_link': 'https://drive.google.com/file/d/utility/view',
                'is_active': 'on',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(DownloadLink.objects.filter(name='Utility App').exists())
