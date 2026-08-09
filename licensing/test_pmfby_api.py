import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from . import license_views
from .forms import PublicPmfbyRegistrationForm


@override_settings(ALLOWED_HOSTS=['testserver'], ERP_API_IP_RATE_LIMIT=100, ERP_API_MOBILE_RATE_LIMIT=100)
class PmfbyApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, route_name, body):
        return self.factory.post(
            reverse(f'license_api:{route_name}'),
            data=json.dumps(body),
            content_type='application/json',
        )

    @patch('licensing.license_views.UserInfoData.objects')
    def test_registration_prefills_only_safe_profile_fields_from_latest_mobile_record(self, objects):
        previous = SimpleNamespace(
            pacs_name='Demo PACS', brach='Main Branch', dist='Sehore',
            state='MADHYA PRADESH', operator_mobile=9876543211,
            amount=9999, payment_status=9999, entry_count=500,
            limit_of_entrys=800, utr_number='SECRET-UTR',
        )
        objects.filter.return_value.order_by.return_value.first.return_value = previous
        initial = license_views._pmfby_registration_initial('9876543210')
        self.assertEqual(initial, {
            'mobile': '9876543210',
            'operator_mobile': '9876543211',
            'pacs_name': 'Demo PACS',
            'brach': 'Main Branch',
            'dist': 'Sehore',
            'state': 'MADHYA PRADESH',
        })
        for sensitive in ('amount', 'payment_status', 'entry_count', 'limit_of_entrys', 'utr_number'):
            self.assertNotIn(sensitive, initial)

    @patch('licensing.license_views.UserInfoData.objects')
    def test_registration_uses_mobile_defaults_when_no_history_exists(self, objects):
        objects.filter.return_value.order_by.return_value.first.return_value = None
        initial = license_views._pmfby_registration_initial('9876543210')
        self.assertEqual(initial, {'mobile': '9876543210', 'operator_mobile': '9876543210'})
    def test_registration_form_requires_every_visible_field(self):
        form = PublicPmfbyRegistrationForm(data={}, financial_years=['Kharif 2026'])
        self.assertFalse(form.is_valid())
        self.assertEqual(
            set(form.errors),
            {'mobile', 'pacs_name', 'brach', 'dist', 'state', 'operator_mobile', 'financial_year'},
        )

    def test_registration_form_does_not_expose_internal_payment_fields(self):
        form = PublicPmfbyRegistrationForm(financial_years=['Kharif 2026'])
        for field_name in ('payment_status', 'amount', 'utr_number', 'purpose', 'is_pri'):
            self.assertNotIn(field_name, form.fields)
    @patch('licensing.license_views._pmfby_years', return_value=['Kharif 2026'])
    def test_options_returns_pmfby_years(self, _years):
        response = license_views.pmfby_options(self.post('pmfby_options', {}))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['financial_years'], ['Kharif 2026'])
        self.assertNotIn('entry_limit', data)

    @patch('licensing.license_views._select_pmfby_record')
    def test_unpaid_record_gets_free_access_without_exposing_counts(self, select_record):
        select_record.return_value = (SimpleNamespace(
            pk=17, mobile=9876543210, pacs_name='Demo', f_year='Kharif 2026',
            amount=2000, payment_status=0, is_active=1, entry_count=4,
        ), False)
        response = license_views.pmfby_subscription(self.post('pmfby_subscription', {
            'mobile': '9876543210', 'financial_year': 'Kharif 2026',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['authorized'])

        self.assertTrue(data['record_token'])
        self.assertNotIn('entry_count', data)
        self.assertNotIn('remaining_entries', data)
        self.assertNotIn('entry_limit', data)

    @patch('licensing.license_views._select_pmfby_record')
    def test_paid_equal_record_is_unlimited_even_after_ten(self, select_record):
        select_record.return_value = (SimpleNamespace(
            pk=18, mobile=9876543210, pacs_name='Demo', f_year='Kharif 2026',
            amount=2000, payment_status=2000, is_active=1, entry_count=50,
        ), False)
        response = license_views.pmfby_subscription(self.post('pmfby_subscription', {
            'mobile': '9876543210', 'financial_year': 'Kharif 2026',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['authorized'])


    @patch('licensing.license_views._select_pmfby_record')
    def test_free_limit_does_not_block_login(self, select_record):
        select_record.return_value = (SimpleNamespace(
            pk=19, mobile=9876543210, pacs_name='Demo', f_year='Kharif 2026',
            amount=0, payment_status=0, is_active=1, entry_count=10,
        ), False)
        response = license_views.pmfby_subscription(self.post('pmfby_subscription', {
            'mobile': '9876543210', 'financial_year': 'Kharif 2026',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['authorized'])
        self.assertEqual(data['status'], 'ACTIVE')
        self.assertNotIn('remaining_entries', data)

    @patch('licensing.license_views._pmfby_record_from_token')
    def test_entry_button_blocks_free_record_after_ten(self, record_from_token):
        record_from_token.return_value = (SimpleNamespace(
            amount=0, payment_status=0, is_active=1, entry_count=10,
        ), None)
        response = license_views.check_pmfby_entry(self.post('pmfby_entry_check', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(data['allowed'])
        self.assertEqual(data['status'], 'ENTRY_LIMIT_REACHED')
        self.assertNotIn('entry_count', data)

    @patch('licensing.license_views._pmfby_record_from_token')
    def test_admin_extended_entry_limit_is_honored(self, record_from_token):
        record_from_token.return_value = (SimpleNamespace(
            amount=0, payment_status=0, is_active=1, entry_count=10, limit_of_entrys=15,
        ), None)
        response = license_views.check_pmfby_entry(self.post('pmfby_entry_check', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['allowed'])
        self.assertEqual(data['status'], 'ENTRY_ALLOWED')
        self.assertNotIn('entry_count', data)
        self.assertNotIn('entry_limit', data)
    @patch('licensing.license_views.tblUPI.objects')
    @patch('licensing.license_views._pmfby_record_from_token')
    def test_upi_endpoint_returns_active_server_upi(self, record_from_token, upi_objects):
        record_from_token.return_value = (SimpleNamespace(is_active=1), None)
        upi_objects.filter.return_value.exclude.return_value.exclude.return_value.order_by.return_value.first.return_value = SimpleNamespace(
            upiID='merchant@upi'
        )
        response = license_views.get_pmfby_upi(self.post('pmfby_upi', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['success'])
        self.assertEqual(data['upi_id'], 'merchant@upi')
    @patch('licensing.license_views._pmfby_record_from_token')
    def test_paid_entry_check_returns_paid_access_type(self, record_from_token):
        record_from_token.return_value = (SimpleNamespace(
            amount=2500, payment_status=2500, is_active=1, entry_count=3000, limit_of_entrys=3000,
        ), None)
        response = license_views.check_pmfby_entry(self.post('pmfby_entry_check', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['allowed'])
        self.assertEqual(data['access_type'], 'PAID')
    @patch('licensing.license_views._select_pmfby_record', return_value=(None, False))
    def test_missing_record_returns_registration_url(self, _select):
        response = license_views.pmfby_subscription(self.post('pmfby_subscription', {
            'mobile': '9876543210', 'financial_year': 'Kharif 2026',
        }))
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'LICENSE_NOT_FOUND')
        self.assertIn('/licensing/pmfby/register/?token=', data['registration_url'])

    @patch('licensing.license_views.transaction.atomic', return_value=nullcontext())
    @patch('licensing.license_views.UserInfoData.objects')
    @patch('licensing.license_views._pmfby_record_from_token')
    def test_free_successful_upload_increments_entry_count_immediately(self, record_from_token, objects, _atomic):
        record = SimpleNamespace(
            pk=21, amount=2500, payment_status=0, is_active=1,
            entry_count=4, limit_of_entrys=10, save=MagicMock(),
        )
        record_from_token.return_value = (record, None)
        objects.select_for_update.return_value.filter.return_value.first.return_value = record
        response = license_views.consume_pmfby_entries(self.post('pmfby_entries_consume', {
            'record_token': 'signed-session',
            'uploaded_count': 1,
        }))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'UPLOAD_RECORDED')
        self.assertEqual(record.entry_count, 5)
        record.save.assert_called_once_with(update_fields=['entry_count'])
    @patch('licensing.license_views.transaction.atomic', return_value=nullcontext())
    @patch('licensing.license_views.UserInfoData.objects')
    @patch('licensing.license_views._pmfby_record_from_token')
    def test_consume_rejects_free_upload_above_ten(self, record_from_token, objects, _atomic):
        record = SimpleNamespace(pk=20, amount=2000, payment_status=0, is_active=1, entry_count=9)
        record_from_token.return_value = (record, None)
        objects.select_for_update.return_value.filter.return_value.first.return_value = record
        token = 'signed-session'
        response = license_views.consume_pmfby_entries(self.post('pmfby_entries_consume', {
            'record_token': token, 'uploaded_count': 2,
        }))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(data['status'], 'ENTRY_LIMIT_EXCEEDED')
        self.assertNotIn('entry_count', data)

    def test_consume_rejects_tampered_token(self):
        response = license_views.consume_pmfby_entries(self.post('pmfby_entries_consume', {
            'record_token': 'tampered', 'uploaded_count': 1,
        }))
        self.assertEqual(response.status_code, 401)
        self.assertEqual(json.loads(response.content)['status'], 'INVALID_TOKEN')