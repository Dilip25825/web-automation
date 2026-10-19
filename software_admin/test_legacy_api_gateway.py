from unittest.mock import MagicMock, patch

import requests

from django.test import RequestFactory, SimpleTestCase, override_settings

from .legacy_api_gateway import proxy_licensing_api


@override_settings(
    LEGACY_API_GATEWAY_BASE_URL='https://new-api.example',
    LEGACY_API_GATEWAY_TIMEOUT_SECONDS=12,
)
class LegacyLicensingGatewayTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('software_admin.legacy_api_gateway.requests.request')
    def test_post_preserves_api_contract_and_authentication_headers(self, request_mock):
        upstream = MagicMock()
        upstream.content = b'{"success": true}'
        upstream.status_code = 429
        upstream.headers = {'Content-Type': 'application/json', 'Retry-After': '60'}
        request_mock.return_value = upstream

        request = self.factory.post(
            '/api/licensing/erp/subscription/?source=excel',
            data=b'{"operator_mobile":"9876543210"}',
            content_type='application/json',
            HTTP_AUTHORIZATION='Bearer client-token',
            HTTP_X_LICENSE_API_KEY='legacy-key',
            HTTP_USER_AGENT='Microsoft WinHTTP client',
            REMOTE_ADDR='203.0.113.25',
        )

        response = proxy_licensing_api(request, 'erp/subscription/')

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.content, b'{"success": true}')
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response['Retry-After'], '60')
        request_mock.assert_called_once_with(
            method='POST',
            url='https://new-api.example/api/licensing/erp/subscription/?source=excel',
            data=b'{"operator_mobile":"9876543210"}',
            headers={
                'Authorization': 'Bearer client-token',
                'Content-Type': 'application/json',
                'X-License-API-Key': 'legacy-key',
                'User-Agent': 'Microsoft WinHTTP client',
                'X-Forwarded-For': '203.0.113.25',
            },
            timeout=12,
            allow_redirects=False,
        )

    @patch(
        'software_admin.legacy_api_gateway.requests.request',
        side_effect=requests.ConnectionError,
    )
    def test_upstream_connection_error_returns_safe_json(self, request_mock):
        request = self.factory.post('/api/licensing/erp/subscription/', data=b'{}', content_type='application/json')

        response = proxy_licensing_api(request, 'erp/subscription/')

        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(response.content, {
            'success': False,
            'status': 'GATEWAY_UPSTREAM_UNAVAILABLE',
            'message': 'Licensing service abhi uplabdh nahi hai. Kripya dobara try karein.',
        })

    @override_settings(LEGACY_API_GATEWAY_BASE_URL='http://not-https.example')
    def test_non_https_upstream_is_rejected(self):
        request = self.factory.post('/api/licensing/erp/subscription/', data=b'{}', content_type='application/json')

        response = proxy_licensing_api(request, 'erp/subscription/')

        self.assertEqual(response.status_code, 503)
        self.assertJSONEqual(response.content, {'success': False, 'status': 'GATEWAY_NOT_CONFIGURED'})
