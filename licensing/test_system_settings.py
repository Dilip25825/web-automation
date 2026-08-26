import json
from types import SimpleNamespace

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
        ]
        for view, args in endpoints:
            with self.subTest(view=view.__name__):
                response = view(self._request('post', '/blocked/', ajax=True), *args)
                self.assertEqual(response.status_code, 403)
                self.assertFalse(json.loads(response.content)['success'])
