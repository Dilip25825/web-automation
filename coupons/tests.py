from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .forms import CouponForm
from .models import Coupon
from .services import generate_coupon_code


class CouponTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.superuser = User.objects.create_superuser(username="couponadmin", password="pass")
        self.user = User.objects.create_user(username="normal", password="pass")

    def test_generator_uses_128_bit_unique_format(self):
        first = generate_coupon_code(750)
        Coupon.objects.create(coupon_code=first, discount_amount=750)
        second = generate_coupon_code(750)
        self.assertRegex(first, r"^C750-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{6}$")
        self.assertNotEqual(first, second)

    def test_form_requires_hint_to_match_discount(self):
        code = generate_coupon_code(750)
        form = CouponForm({"coupon_code": code, "discount_amount": 750, "status": "on"})
        self.assertTrue(form.is_valid(), form.errors.as_json())

    def test_normal_user_can_view_but_cannot_create(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("coupons:dashboard")).status_code, 200)
        self.assertEqual(self.client.post(reverse("coupons:create"), {}).status_code, 403)


    def test_copy_reserves_and_records_logged_in_user(self):
        coupon = Coupon.objects.create(coupon_code=generate_coupon_code(500), discount_amount=500)
        self.client.force_login(self.user)
        response = self.client.post(reverse('coupons:reserve', args=[coupon.pk]))
        self.assertEqual(response.status_code, 200)
        coupon.refresh_from_db()
        self.assertEqual(coupon.copied_by, self.user)
        self.assertIsNotNone(coupon.copied_at)
        self.assertTrue(coupon.used_by.startswith('RESERVED:'))

    def test_superuser_sees_only_ten_rows_per_page(self):
        self.client.force_login(self.superuser)
        for number in range(12):
            Coupon.objects.create(coupon_code=generate_coupon_code(number + 1), discount_amount=number + 1)
        response = self.client.get(reverse("coupons:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["coupons"]), 10)

    def test_search_fetches_matching_coupon(self):
        self.client.force_login(self.superuser)
        code = generate_coupon_code(750)
        Coupon.objects.create(coupon_code=code, discount_amount=750, used_by="Customer One")
        response = self.client.get(reverse("coupons:dashboard"), {"q": code[4:9]})
        self.assertContains(response, code)
    def test_superuser_can_bulk_copy_available_coupons_by_amount(self):
        coupons = [
            Coupon.objects.create(coupon_code=generate_coupon_code(750), discount_amount=750)
            for _ in range(3)
        ]
        Coupon.objects.create(coupon_code=generate_coupon_code(500), discount_amount=500)
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('coupons:bulk_copy'), {
            'discount_amount': '750', 'quantity': '2',
        })
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload['coupon_codes']), 2)
        self.assertEqual(payload['copy_text'], ',\n'.join(payload['coupon_codes']))
        for coupon in coupons[:2]:
            coupon.refresh_from_db()
            self.assertEqual(coupon.copied_by, self.superuser)
            self.assertTrue(coupon.used_by.startswith('RESERVED:'))
        coupons[2].refresh_from_db()
        self.assertIsNone(coupons[2].used_by)

    def test_bulk_copy_is_superuser_only(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('coupons:bulk_copy'), {
            'discount_amount': '750', 'quantity': '1',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 403)

    def test_bulk_copy_does_not_reserve_partial_quantity(self):
        coupon = Coupon.objects.create(coupon_code=generate_coupon_code(750), discount_amount=750)
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('coupons:bulk_copy'), {
            'discount_amount': '750', 'quantity': '2',
        })
        self.assertEqual(response.status_code, 409)
        coupon.refresh_from_db()
        self.assertIsNone(coupon.used_by)
