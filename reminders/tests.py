from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Task


class ReminderAjaxTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='reminder-user', password='secret123'
        )
        self.client.force_login(self.user)

    def test_task_create_returns_json_for_ajax(self):
        response = self.client.post(
            reverse('reminders:task_create'),
            {
                'title': 'Call customer',
                'priority': 'HIGH',
                'status': 'PENDING',
                'assigned_to': self.user.pk,
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertTrue(Task.objects.filter(title='Call customer').exists())

    def test_status_toggle_is_ajax_post(self):
        task = Task.objects.create(
            title='Prepare report',
            status='PENDING',
            assigned_to=self.user,
            created_by=self.user,
        )

        response = self.client.post(
            reverse('reminders:task_toggle_status', args=[task.pk]),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        task.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(task.status, 'IN_PROGRESS')
