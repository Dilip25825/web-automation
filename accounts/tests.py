from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import PasswordResetOTP


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetOTPTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='testuser', email='test@example.com', password='OldPassword123!'
        )

    @patch('accounts.views.secrets.randbelow', return_value=123456)
    def test_email_otp_can_reset_password(self, _mock_randbelow):
        self.client.force_login(self.user)
        response = self.client.post(reverse('accounts:password_reset_request'), {'email': self.user.email})
        self.assertRedirects(response, reverse('accounts:password_reset_verify'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertNotIn('test@example.com', response.content.decode())

        otp = PasswordResetOTP.objects.get(user=self.user)
        self.assertTrue(otp.check_code('123456'))
        response = self.client.post(reverse('accounts:password_reset_verify'), {'code': '123456'})
        self.assertRedirects(response, reverse('accounts:password_reset_confirm'))

        response = self.client.post(reverse('accounts:password_reset_confirm'), {
            'new_password1': 'NewPassword123!',
            'new_password2': 'NewPassword123!',
        })
        self.assertRedirects(response, reverse('accounts:login'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('NewPassword123!'))
        otp.refresh_from_db()
        self.assertIsNotNone(otp.used_at)

    def test_wrong_otp_increases_attempt_count(self):
        self.client.force_login(self.user)
        self.client.post(reverse('accounts:password_reset_request'), {'email': self.user.email})
        response = self.client.post(reverse('accounts:password_reset_verify'), {'code': '000000'})
        self.assertEqual(response.status_code, 200)
        otp = PasswordResetOTP.objects.get(user=self.user)
        self.assertEqual(otp.attempts, 1)


class ProfileEmailTests(TestCase):
    def test_logged_in_user_can_save_email(self):
        user = get_user_model().objects.create_user(username='profileuser', password='Password123!')
        self.client.force_login(user)
        response = self.client.post(reverse('accounts:profile'), {'email': 'profile@example.com'})
        self.assertRedirects(response, reverse('accounts:profile'))
        user.refresh_from_db()
        self.assertEqual(user.email, 'profile@example.com')

    def test_password_reset_requires_login(self):
        response = self.client.get(reverse('accounts:password_reset_request'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:password_reset_request')}")
