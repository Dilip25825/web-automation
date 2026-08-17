import json
from unittest.mock import Mock, patch

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from licensing.views import _utr_used_elsewhere, userinfo_ajax_action


class DuplicateUtrLookupTests(SimpleTestCase):
    @patch('licensing.views.tblPacsErp.objects')
    @patch('licensing.views.UserInfoData.objects')
    def test_blank_utr_is_not_duplicate(self, userinfo_objects, erp_objects):
        self.assertFalse(_utr_used_elsewhere('  '))
        userinfo_objects.filter.assert_not_called()
        erp_objects.filter.assert_not_called()

    @patch('licensing.views.tblPacsErp.objects')
    @patch('licensing.views.UserInfoData.objects')
    def test_other_userinfo_record_is_detected(self, userinfo_objects, erp_objects):
        matches = Mock()
        userinfo_objects.filter.return_value = matches
        matches.exclude.return_value.exists.return_value = True
        erp_objects.filter.return_value.exclude.return_value.exists.return_value = False

        self.assertTrue(_utr_used_elsewhere('ABC123', userinfo_pk=7))
        matches.exclude.assert_called_once_with(pk=7)

    @patch('licensing.views.tblPacsErp.objects')
    @patch('licensing.views.UserInfoData.objects')
    def test_other_erp_record_is_detected(self, userinfo_objects, erp_objects):
        userinfo_objects.filter.return_value.exclude.return_value.exists.return_value = False
        erp_objects.filter.return_value.exclude.return_value.exists.return_value = True

        self.assertTrue(_utr_used_elsewhere('ABC123', erp_pk=9))


class DuplicateUtrAjaxResponseTests(SimpleTestCase):
    def test_confirmation_response_uses_http_409(self):
        request = RequestFactory().post(
            '/licensing/test/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )

        @userinfo_ajax_action
        def view(inner_request):
            inner_request._duplicate_utr_confirmation = 'Confirm duplicate UTR'
            return HttpResponse()

        response = view(request)
        payload = json.loads(response.content)

        self.assertEqual(response.status_code, 409)
        self.assertFalse(payload['success'])
        self.assertTrue(payload['requires_confirmation'])
        self.assertEqual(payload['message'], 'Confirm duplicate UTR')
