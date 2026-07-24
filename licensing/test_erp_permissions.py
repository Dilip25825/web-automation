from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase

from licensing import views


class ErpRoleSecurityTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.regular_user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=False,
            username='operator-one',
        )
        self.superuser = SimpleNamespace(
            is_authenticated=True,
            is_superuser=True,
            username='admin',
        )

    @patch('licensing.views.messages.error')
    def test_regular_user_cannot_add_erp(self, mocked_error):
        request = self.factory.get('/licensing/pacserp/add/')
        request.user = self.regular_user
        response = views.create_pacserp(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/licensing/pacserp/')
        mocked_error.assert_called_once()

    @patch('licensing.views.messages.error')
    def test_regular_user_cannot_update_erp(self, mocked_error):
        request = self.factory.post('/licensing/pacserp/update/7/')
        request.user = self.regular_user
        response = views.update_pacserp_view(request, 7)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/licensing/pacserp/')
        mocked_error.assert_called_once()

    def test_activation_rejects_get_requests(self):
        request = self.factory.get('/licensing/toggle-erp/7/')
        request.user = self.regular_user
        response = views.toggle_erp_activation(request, 7)
        self.assertEqual(response.status_code, 405)

    @patch('licensing.views.messages.error')
    def test_regular_user_cannot_deactivate_erp(self, mocked_error):
        request = self.factory.post('/licensing/toggle-erp/7/', {'action': 'deactivate'})
        request.user = self.regular_user
        response = views.toggle_erp_activation(request, 7)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/licensing/pacserp/')
        mocked_error.assert_called_once()
    def test_delete_rejects_get_requests(self):
        request = self.factory.get('/licensing/delete-record/7/')
        request.user = self.superuser
        response = views.delete_record_view(request, 7)
        self.assertEqual(response.status_code, 405)

    @patch('licensing.views.tblPacsErp')
    def test_regular_user_queryset_is_scoped(self, mocked_model):
        base_queryset = Mock()
        scoped_queryset = Mock()
        base_queryset.filter.return_value = scoped_queryset
        scoped_queryset.exclude.return_value = scoped_queryset
        mocked_model.objects.all.return_value = base_queryset
        result = views._erp_queryset_for_user(self.regular_user)
        self.assertIs(result, scoped_queryset)
        base_queryset.filter.assert_called_once()
        visibility_rule = base_queryset.filter.call_args.args[0]
        self.assertEqual(visibility_rule.connector, 'OR')
        self.assertIn(('expiry_date__lt', views.timezone.localdate()), visibility_rule.children)
        self.assertIn(('accepte_by__iexact', self.regular_user.username), visibility_rule.children)
        scoped_queryset.exclude.assert_called_once_with(erp_id__iendswith=' Expired')

    @patch('licensing.views.tblPacsErp')
    def test_superuser_queryset_is_unrestricted(self, mocked_model):
        base_queryset = Mock()
        mocked_model.objects.all.return_value = base_queryset
        result = views._erp_queryset_for_user(self.superuser)
        self.assertIs(result, base_queryset)
        base_queryset.filter.assert_not_called()