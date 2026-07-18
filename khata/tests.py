from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Customer, Transaction


class TransferVoucherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='shop', password='test-pass')
        self.from_customer = Customer.objects.create(user=self.user, name='Lilit', phone='1111111')
        self.to_customer = Customer.objects.create(user=self.user, name='Sodan', phone='2222222')
        self.client.force_login(self.user)

    def test_transfer_creates_matching_entries(self):
        response = self.client.post(reverse('khata:transfer_voucher'), {
            'from_customer': self.from_customer.id,
            'to_customer': self.to_customer.id,
            'amount': '2000',
            'date': '2026-07-18',
            'remarks': 'Cash transfer',
        })
        self.assertRedirects(response, reverse('khata:dashboard'))
        self.assertTrue(Transaction.objects.filter(
            customer=self.from_customer, amount=2000, trans_type='GOT').exists())
        self.assertTrue(Transaction.objects.filter(
            customer=self.to_customer, amount=2000, trans_type='GIVEN').exists())

    def test_same_head_is_rejected(self):
        self.client.post(reverse('khata:transfer_voucher'), {
            'from_customer': self.from_customer.id,
            'to_customer': self.from_customer.id,
            'amount': '2000', 'date': '2026-07-18',
        })
        self.assertEqual(Transaction.objects.count(), 0)
