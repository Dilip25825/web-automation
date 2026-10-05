from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
import base64
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .models import Customer, Transaction, TransferVoucher
from .views import build_reminder_whatsapp_url, build_transaction_whatsapp_url




class WhatsAppMessageTests(SimpleTestCase):
    def whatsapp_message(self, url):
        return parse_qs(urlparse(url).query)['text'][0]

    def test_transaction_message_contains_saved_entry_in_hindi(self):
        customer = SimpleNamespace(name='मोहन', phone='9876543210')
        entry = SimpleNamespace(
            trans_type='GIVEN', amount=Decimal('1250'),
            date=date(2026, 8, 11), remarks='सॉफ्टवेयर सेवा',
        )

        message = self.whatsapp_message(
            build_transaction_whatsapp_url(customer, entry, Decimal('1250'))
        )

        self.assertIn('नया लेन-देन दर्ज किया गया है', message)
        self.assertIn('उधार जोड़ा गया', message)
        self.assertIn('₹1250.00', message)
        self.assertNotIn('याद दिलाने', message)

    def test_reminder_message_contains_current_balance_not_transaction(self):
        customer = SimpleNamespace(name='मोहन', phone='9876543210')

        message = self.whatsapp_message(
            build_reminder_whatsapp_url(customer, Decimal('900'))
        )

        self.assertIn('याद दिलाने हेतु संदेश', message)
        self.assertIn('₹900.00 का भुगतान बाकी है', message)
        self.assertNotIn('नया लेन-देन', message)

class TransferVoucherTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='shop', password='test-pass')
        self.from_customer = Customer.objects.create(user=self.user, name='Lilit', phone='9876543210')
        self.to_customer = Customer.objects.create(user=self.user, name='Sodan', phone='9876543211')
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

    def test_bad_debt_ledger_is_hidden_from_main_list_and_shown_separately(self):
        bad_debt = Customer.objects.create(
            user=self.user, name='Old recovery', phone='9876543212', is_bad_debt=True,
        )
        main_response = self.client.get(reverse('khata:dashboard'))
        bad_debt_response = self.client.get(reverse('khata:bad_debt_dashboard'))
        self.assertContains(main_response, self.from_customer.name)
        self.assertNotContains(main_response, bad_debt.name)
        self.assertContains(bad_debt_response, bad_debt.name)
        self.assertNotContains(bad_debt_response, self.from_customer.name)

    def test_main_dashboard_shows_bad_debt_summary_card(self):
        Transaction.objects.create(
            customer=self.from_customer, amount=Decimal('800'), trans_type='GIVEN', date=date(2026, 7, 18),
        )
        bad_debt = Customer.objects.create(
            user=self.user, name='Old recovery', phone='9876543212', is_bad_debt=True,
        )
        Transaction.objects.create(
            customer=bad_debt, amount=Decimal('1250'), trans_type='GIVEN', date=date(2026, 7, 18),
        )
        response = self.client.get(reverse('khata:dashboard'))
        self.assertContains(response, 'Bad Debts')
        self.assertContains(response, reverse('khata:bad_debt_dashboard'))
        self.assertContains(response, 'Outstanding recovery')
        self.assertEqual(response.context['bad_debt_amount'], Decimal('1250'))
        self.assertContains(response, 'Total Receivable')
        self.assertEqual(response.context['total_recovery_amount'], Decimal('2050'))
        self.assertEqual(response.context['total_recovery_ledger_count'], 2)

    def test_bad_debt_customer_is_created_in_separate_section(self):
        response = self.client.post(reverse('khata:add_customer'), {
            'name': 'Written off account', 'phone': '9876543213', 'is_bad_debt': '1',
        })
        self.assertRedirects(response, reverse('khata:bad_debt_dashboard'))
        self.assertTrue(Customer.objects.filter(
            user=self.user, phone='9876543213', is_bad_debt=True
        ).exists())

    def test_existing_customer_can_move_to_bad_debt_and_be_restored(self):
        encoded_id = base64.b64encode(str(self.from_customer.id).encode()).decode()
        update_url = reverse('khata:update_customer', args=[encoded_id])
        response = self.client.post(update_url, {
            'name': self.from_customer.name, 'phone': self.from_customer.phone, 'is_bad_debt': '1',
        })
        self.assertRedirects(response, reverse('khata:bad_debt_dashboard'))
        self.from_customer.refresh_from_db()
        self.assertTrue(self.from_customer.is_bad_debt)
        response = self.client.post(update_url, {
            'name': self.from_customer.name, 'phone': self.from_customer.phone,
        })
        self.assertRedirects(response, reverse('khata:dashboard'))
        self.from_customer.refresh_from_db()
        self.assertFalse(self.from_customer.is_bad_debt)

    def test_transfer_cannot_mix_main_and_bad_debt_ledgers(self):
        bad_debt = Customer.objects.create(
            user=self.user, name='Old recovery', phone='9876543212', is_bad_debt=True,
        )
        self.client.post(reverse('khata:transfer_voucher'), {
            'from_customer': self.from_customer.id,
            'to_customer': bad_debt.id,
            'amount': '2000', 'date': '2026-07-18', 'is_bad_debt': '0',
        })
        self.assertEqual(Transaction.objects.count(), 0)

    def test_transfer_returns_json_for_ajax(self):
        response = self.client.post(
            reverse('khata:transfer_voucher'),
            {
                'from_customer': self.from_customer.id,
                'to_customer': self.to_customer.id,
                'amount': '1500',
                'date': '2026-07-18',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        self.assertEqual(Transaction.objects.count(), 2)
        voucher = TransferVoucher.objects.get()
        self.assertEqual(set(Transaction.objects.values_list('transfer_voucher_id', flat=True)), {voucher.pk})
        self.assertEqual(len(response.json()['whatsapp_actions']), 2)

    @patch('khata.views.upload_attachment')
    def test_transfer_uploads_one_shared_attachment(self, upload_attachment_mock):
        upload_attachment_mock.return_value = {
            'attachment_drive_id': 'drive-file-1',
            'attachment_name': 'voucher.pdf',
            'attachment_mime_type': 'application/pdf',
            'attachment_size': 25,
        }
        attachment = SimpleUploadedFile('voucher.pdf', b'%PDF-1.4 shared voucher', content_type='application/pdf')
        response = self.client.post(
            reverse('khata:transfer_voucher'),
            {'from_customer': self.from_customer.id, 'to_customer': self.to_customer.id,
             'amount': '1500', 'date': '2026-07-18', 'attachment': attachment},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 200)
        voucher = TransferVoucher.objects.get()
        self.assertEqual(voucher.attachment_drive_id, 'drive-file-1')
        self.assertEqual(Transaction.objects.filter(transfer_voucher=voucher).count(), 2)
        self.assertEqual(Transaction.objects.exclude(attachment_drive_id__isnull=True).count(), 0)
        upload_attachment_mock.assert_called_once()
