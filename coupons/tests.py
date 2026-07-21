from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import CouponForm
from .models import Coupon
from .services import generate_coupon_code


class CouponTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(username='couponadmin', password='pass')
        self.user = User.objects.create_user(username='normal', password='pass')

    def test_generator_uses_required_unique_format(self):
        first = generate_coupon_code(750)
        Coupon.objects.create(coupon_code=first, discount_amount=750)
        second = generate_coupon_code(750)
        self.assertRegex(first, r'^SAVE750-[A-Z0-9]{5}-[A-Z0-9]{5}$')
        self.assertNotEqual(first, second)

    def test_form_requires_code_amount_to_match(self):
        form = CouponForm({'coupon_code': 'SAVE500-TFS1X-EFYTD', 'discount_amount': 750, 'status': 'on'})
        self.assertFalse(form.is_valid())
        self.assertIn('coupon_code', form.errors)

    def test_normal_user_is_forbidden(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('coupons:dashboard')).status_code, 403)

    def test_superuser_sees_only_recent_ten_without_search(self):
        self.client.force_login(self.superuser)
        for number in range(12):
            Coupon.objects.create(coupon_code=f'SAVE{number + 1}-AAAA{number % 10}-BBBB{number % 10}', discount_amount=number + 1)
        response = self.client.get(reverse('coupons:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['coupons']), 10)

    def test_search_fetches_matching_coupon(self):
        self.client.force_login(self.superuser)
        Coupon.objects.create(coupon_code='SAVE750-TFS1X-EFYTD', discount_amount=750, used_by='Customer One')
        response = self.client.get(reverse('coupons:dashboard'), {'q': 'TFS1X'})
        self.assertContains(response, 'SAVE750-TFS1X-EFYTD')
