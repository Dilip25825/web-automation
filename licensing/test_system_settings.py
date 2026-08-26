import json
from types import SimpleNamespace
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase

from licensing import views


class SystemSettingsPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.normal_user = SimpleNamespace(is_authenticated=True, is_superuser=False)

    def _request(self, method, path, ajax=False):
        request = getattr(self.factory, method)(path)
        request.user = self.normal_user
        if ajax:
            request.META['HTTP_X_REQUESTED_WITH'] = 'XMLHttpRequest'
        return request

    def test_dashboard_rejects_non_superuser(self):
        response = views.system_settings(self._request('get', '/licensing/system-settings/'))
        self.assertEqual(response.status_code, 403)

    def test_all_crud_endpoints_reject_non_superuser(self):
        endpoints = [
            (views.create_purpose, ()),
            (views.update_purpose, (1,)),
            (views.delete_purpose, (1,)),
            (views.create_upi, ()),
            (views.update_upi, (1,)),
            (views.delete_upi, (1,)),
            (views.generate_upi_qr, ()),
        ]
        for view, args in endpoints:
            with self.subTest(view=view.__name__):
                response = view(self._request('post', '/blocked/', ajax=True), *args)
                self.assertEqual(response.status_code, 403)
                self.assertFalse(json.loads(response.content)['success'])

    def test_qr_form_validates_amount_and_remark(self):
        from licensing.forms import UpiQrForm
        self.assertTrue(UpiQrForm({'upi_id': '7', 'amount': '2000', 'remark': 'FASAL RIN 2025-2026'}).is_valid())
        self.assertFalse(UpiQrForm({'upi_id': '', 'amount': '0', 'remark': ''}).is_valid())

    @patch('licensing.views.tblUPI.objects')
    def test_superuser_can_generate_qr_from_active_upi(self, objects):
        objects.filter.return_value.exclude.return_value.exclude.return_value.first.return_value = SimpleNamespace(upiID='merchant@upi')
        request = self.factory.post('/licensing/system-settings/upi/qr/', {'upi_id': '7', 'amount': '2000', 'remark': 'FASAL RIN 2025-2026'})
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=True)
        response = views.generate_upi_qr(request)
        payload = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload['qr_data_url'].startswith('data:image/svg+xml;base64,'))
        self.assertIn('pa=merchant%40upi', payload['upi_url'])
        self.assertIn('am=2000.00', payload['upi_url'])
