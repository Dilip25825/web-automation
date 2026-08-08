import json
from contextlib import nullcontext
from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from . import license_views


@override_settings(LICENSE_VALIDATION_API_KEY='test-api-key', ALLOWED_HOSTS=['testserver'])
class ErpSubscriptionApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse('license_api:erp_subscription')

    def post(self, body, api_key='test-api-key', client_token=None):
        request = self.factory.post(self.url, data=body, content_type='application/json')
        if api_key is not None:
            request.META['HTTP_X_LICENSE_API_KEY'] = api_key
        if client_token:
            request.META['HTTP_AUTHORIZATION'] = f'Bearer {client_token}'
        return license_views.check_erp_subscription(request)

    def test_api_key_is_required(self):
        response = self.post('{"operator_mobile":"9876543210"}', api_key=None)
        self.assertEqual(response.status_code, 401)
        self.assertJSONEqual(response.content, {'success': False, 'authorized': False, 'status': 'UNAUTHORIZED'})

    def test_invalid_mobile_is_rejected(self):
        response = self.post('{"operator_mobile":"123"}')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['status'], 'INVALID_MOBILE')

    @patch('licensing.license_views.tblPacsErp.objects')
    def test_missing_record_returns_signed_registration_url(self, objects):
        objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = []
        response = self.post('{"operator_mobile":"9876543210"}')
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data['status'], 'LICENSE_NOT_FOUND')
        self.assertIn('/licensing/erp/register/?token=', data['registration_url'])

    @patch('licensing.license_views.tblPacsErp.objects')
    def test_active_record_returns_erp_login_data(self, objects):
        record = MagicMock()
        record.pk = 42
        record.erp_id = 'CEO123456'
        record.pacs_name = 'Demo PACS'
        record.expiry_date = date(2099, 12, 31)
        record.date_time = datetime(2026, 8, 8, 1, 30, tzinfo=dt_timezone.utc)
        record.is_active = 1
        record.current_amount = 4500
        record.payment_status = 4500
        objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = [record]

        response = self.post('{"operator_mobile":"+91 98765 43210"}')
        data = json.loads(response.content)
        self.assertTrue(data['authorized'])
        self.assertEqual(data['status'], 'ACTIVE')
        self.assertEqual(data['record_id'], 42)
        self.assertEqual(data['erp_id'], 'CEO123456')
        self.assertEqual(data['registration_date'], '2026-08-08')
        self.assertEqual(data['expiry_date'], '2099-12-31')
        record.save.assert_called_once_with(update_fields=['last_login'])

    @patch('licensing.license_views.ErpApiClientToken.objects')
    @patch('licensing.license_views.tblPacsErp.objects')
    def test_client_bearer_token_authenticates_without_master_key(self, erp_objects, token_objects):
        raw_token = 'client-token-' + ('x' * 48)
        credential = MagicMock(expires_at=None)
        token_objects.filter.return_value.first.return_value = credential
        record = MagicMock(
            pk=51,
            erp_id='CEOCLIENT51',
            pacs_name='Client PACS',
            expiry_date=date(2099, 12, 31),
            is_active=1,
            current_amount=4500,
            payment_status=4500,
            date_time=datetime(2026, 8, 8, 1, 30, tzinfo=dt_timezone.utc),
        )
        erp_objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = [record]

        response = self.post(
            '{"operator_mobile":"9876543210"}',
            api_key=None,
            client_token=raw_token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)['authorized'])
        credential.save.assert_called_once_with(update_fields=['last_used_at'])
    @override_settings(ERP_API_IP_RATE_LIMIT=100, ERP_API_MOBILE_RATE_LIMIT=1)
    @patch('licensing.license_views.tblPacsErp.objects')
    def test_mobile_rate_limit_returns_429(self, objects):
        cache.clear()
        objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = []
        first = self.post('{"operator_mobile":"9876543210"}')
        second = self.post('{"operator_mobile":"9876543210"}')
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(json.loads(second.content)['status'], 'RATE_LIMITED')
        self.assertEqual(second['Retry-After'], '60')
        cache.clear()

@override_settings(LICENSE_VALIDATION_API_KEY='test-api-key', ALLOWED_HOSTS=['testserver'])
class ErpVersionApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse('license_api:erp_version')

    @patch('licensing.license_views.VersionInfo.objects')
    def test_newer_server_version_is_reported(self, objects):
        objects.filter.return_value.first.return_value = SimpleNamespace(
            Version='5.1.0.9',
            Description='ERP update',
            Year='2026',
            Remark='Recommended',
        )
        request = self.factory.post(
            self.url,
            data='{"operator_mobile":"9876543210","current_version":"5.1.0.8"}',
            content_type='application/json',
            HTTP_X_LICENSE_API_KEY='test-api-key',
        )
        response = license_views.check_erp_version(request)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['update_available'])
        self.assertEqual(data['latest_version'], '5.1.0.9')

    def test_numeric_version_comparison_does_not_treat_older_server_as_update(self):
        self.assertGreater(license_views._version_parts('5.10.0'), license_views._version_parts('5.9.9'))

@override_settings(ALLOWED_HOSTS=['testserver'])
class ErpSelfRegistrationTests(SimpleTestCase):
    def registration_token(self):
        return signing.dumps(
            {'operator_mobile': '9876543210'},
            salt=license_views.ERP_REGISTRATION_SALT,
            compress=True,
        )

    @patch('licensing.license_views.tblPacsErp.objects')
    def test_signed_registration_page_opens(self, objects):
        objects.filter.return_value.exclude.return_value.exists.return_value = False
        response = self.client.get(reverse('licensing:erp_self_register'), {'token': self.registration_token()})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '9876543210')
        self.assertContains(response, 'Create ERP Registration')

    @patch('licensing.license_views.transaction.atomic', return_value=nullcontext())
    @patch('licensing.license_views.tblPacsErp.objects')
    def test_registration_creates_inactive_pending_record(self, objects, _atomic):
        objects.filter.return_value.exclude.return_value.exists.return_value = False
        objects.filter.return_value.exists.return_value = False
        objects.create.return_value = SimpleNamespace(id=77)
        response = self.client.post(
            reverse('licensing:erp_self_register'),
            {
                'token': self.registration_token(),
                'erp_id': 'CEO123456',
                'pacs_name': 'Demo PACS',
                'brach': 'Main Branch',
                'dist': 'Demo District',
                'state': 'Madhya Pradesh',
                'operator_mobile': '9876543210',
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Registration successful')
        objects.create.assert_called_once()
        kwargs = objects.create.call_args.kwargs
        self.assertEqual(kwargs['operator_mobile'], 9876543210)
        self.assertEqual(kwargs['is_active'], 1)
        self.assertEqual(kwargs['payment_status'], 0)
        self.assertEqual(kwargs['current_amount'], 4500)
        self.assertEqual(kwargs['expiry_date'], date.today())
@override_settings(ALLOWED_HOSTS=['testserver'], ERP_API_IP_RATE_LIMIT=100)
class ErpDeviceRegistrationApiTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.factory = RequestFactory()
        self.url = reverse('license_api:erp_device_register')

    @patch('licensing.license_views.ErpApiClientToken.objects')
    @patch('licensing.license_views.tblPacsErp.objects')
    def test_first_device_receives_token(self, erp_objects, token_objects):
        record = SimpleNamespace(id=7)
        erp_objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = [record]
        token_objects.filter.return_value.first.return_value = None
        request = self.factory.post(
            self.url,
            data='{"operator_mobile":"9876543210","device_id":"PC01|DOMAIN|USER"}',
            content_type='application/json',
        )
        response = license_views.register_erp_device(request)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data['registered'])
        self.assertGreaterEqual(len(data['client_token']), 32)
        token_objects.create.assert_called_once()

    @patch('licensing.license_views.ErpApiClientToken.objects')
    @patch('licensing.license_views.tblPacsErp.objects')
    def test_second_device_is_rejected(self, erp_objects, token_objects):
        import hashlib
        record = SimpleNamespace(id=7)
        erp_objects.filter.return_value.exclude.return_value.order_by.return_value.__getitem__.return_value = [record]
        token_objects.filter.return_value.first.return_value = SimpleNamespace(
            device_hash=hashlib.sha256(b'PC01|DOMAIN|USER').hexdigest()
        )
        request = self.factory.post(
            self.url,
            data='{"operator_mobile":"9876543210","device_id":"PC02|DOMAIN|USER"}',
            content_type='application/json',
        )
        response = license_views.register_erp_device(request)
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(data['status'], 'DEVICE_ALREADY_REGISTERED')