import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from . import license_views


@override_settings(ALLOWED_HOSTS=['testserver'], ERP_API_IP_RATE_LIMIT=100, ERP_API_MOBILE_RATE_LIMIT=100)
class FasalRinApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, route_name, body):
        return self.factory.post(
            reverse(f'license_api:{route_name}'),
            data=json.dumps(body),
            content_type='application/json',
        )

    def test_work_type_mapping_accepts_only_one_to_three(self):
        self.assertEqual(license_views._fasal_work_type('1'), 1)
        self.assertEqual(license_views._fasal_work_type('2'), 2)
        self.assertEqual(license_views._fasal_work_type('3'), 3)
        self.assertEqual(license_views._fasal_work_type('4'), 0)

    @patch('licensing.license_views._fasal_years', return_value=['2025-2026ISSClaim'])
    def test_options_returns_work_type_and_fasal_years(self, years):
        response = license_views.fasal_rin_options(self.post('fasal_rin_options', {'work_type': 3}))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['service'], 'FASAL RIN')
        self.assertEqual(data['work_type_name'], 'IS/PRI Upload')
        self.assertEqual(data['financial_years'], ['2025-2026ISSClaim'])
        years.assert_called_once_with(3)

    @patch('licensing.license_views._select_fasal_record', return_value=(None, False))
    def test_missing_record_returns_work_type_bound_registration_url(self, _select):
        response = license_views.fasal_rin_subscription(self.post('fasal_rin_subscription', {
            'mobile': '9876543210', 'financial_year': '2025-2026', 'work_type': 1,
        }))
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'LICENSE_NOT_FOUND')
        self.assertIn('/licensing/fasal-rin/register/?token=', data['registration_url'])
        token = data['registration_url'].split('token=', 1)[1]
        payload = signing.loads(token, salt=license_views.FASAL_RIN_TOKEN_SALT)
        self.assertEqual(payload['work_type'], 1)

    @patch('licensing.license_views._select_fasal_record')
    def test_active_record_login_returns_signed_work_type_session(self, select_record):
        select_record.return_value = (SimpleNamespace(
            pk=31, mobile=9876543210, pacs_name='Demo', f_year='2025-2026',
            is_active=1,
        ), False)
        response = license_views.fasal_rin_subscription(self.post('fasal_rin_subscription', {
            'mobile': '9876543210', 'financial_year': '2025-2026', 'work_type': 2,
        }))
        data = json.loads(response.content)
        self.assertTrue(data['authorized'])
        self.assertEqual(data['work_type'], 2)
        self.assertTrue(data['record_token'])

    @patch('licensing.license_views._fasal_record_from_token')
    def test_free_entry_uses_server_record_limit(self, from_token):
        from_token.return_value = (SimpleNamespace(
            amount=2500, payment_status=0, is_active=1,
            entry_count=20, limit_of_entrys=25,
        ), 1, None)
        response = license_views.check_fasal_rin_entry(self.post('fasal_rin_entry_check', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertTrue(data['allowed'])
        self.assertEqual(data['access_type'], 'FREE_TRIAL')
        self.assertNotIn('entry_count', data)
        self.assertNotIn('entry_limit', data)

    @patch('licensing.license_views._fasal_record_from_token')
    def test_free_entry_blocks_at_server_record_limit(self, from_token):
        from_token.return_value = (SimpleNamespace(
            amount=2500, payment_status=0, is_active=1,
            entry_count=20, limit_of_entrys=20,
        ), 3, None)
        response = license_views.check_fasal_rin_entry(self.post('fasal_rin_entry_check', {
            'record_token': 'signed-session',
        }))
        data = json.loads(response.content)
        self.assertFalse(data['allowed'])
        self.assertEqual(data['status'], 'ENTRY_LIMIT_REACHED')

    @patch('licensing.license_views.transaction.atomic', return_value=nullcontext())
    @patch('licensing.license_views.UserInfoData.objects')
    @patch('licensing.license_views._fasal_record_from_token')
    def test_free_success_updates_entry_count_immediately(self, from_token, objects, _atomic):
        record = SimpleNamespace(
            pk=32, amount=2500, payment_status=0, is_active=1,
            entry_count=4, limit_of_entrys=20, save=MagicMock(),
        )
        from_token.return_value = (record, 2, None)
        objects.select_for_update.return_value.filter.return_value.first.return_value = record
        response = license_views.consume_fasal_rin_entries(self.post('fasal_rin_entries_consume', {
            'record_token': 'signed-session', 'uploaded_count': 1,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(record.entry_count, 5)
        record.save.assert_called_once_with(update_fields=['entry_count'])

    @patch('licensing.license_views.tblUPI.objects')
    @patch('licensing.license_views._fasal_record_from_token')
    def test_upi_endpoint_uses_active_server_upi(self, from_token, objects):
        from_token.return_value = (SimpleNamespace(is_active=1), 1, None)
        objects.filter.return_value.exclude.return_value.exclude.return_value.order_by.return_value.first.return_value = SimpleNamespace(upiID='merchant@upi')
        response = license_views.get_fasal_rin_upi(self.post('fasal_rin_upi', {'record_token': 'signed-session'}))
        self.assertEqual(json.loads(response.content)['upi_id'], 'merchant@upi')