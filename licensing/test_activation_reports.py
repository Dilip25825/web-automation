from types import SimpleNamespace
from unittest.mock import Mock

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from licensing import views


class ActivationReportPermissionTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _model_with_records(self):
        model = Mock()
        records = Mock()
        model.objects.filter.return_value = records
        records.exclude.return_value = records
        records.filter.return_value = records
        return model, records

    def test_regular_user_report_ignores_another_users_filter(self):
        model, records = self._model_with_records()
        request = self.factory.get('/?report_user=admin')
        request.user = SimpleNamespace(username='operator', is_superuser=False)

        views._activation_report_records(model, request)

        records.filter.assert_called_once_with(accepte_by__iexact='operator')

    def test_superuser_can_filter_a_report_by_operator(self):
        model, records = self._model_with_records()
        request = self.factory.get('/?report_user=operator')
        request.user = SimpleNamespace(username='admin', is_superuser=True)

        views._activation_report_records(model, request)

        records.filter.assert_called_once_with(accepte_by__iexact='operator')

    def test_excel_export_is_an_xlsx_attachment(self):
        record = SimpleNamespace(
            id=7, pacs_name='Test PACS', mobile=9999999999, for_whys='PMFBY',
            f_year='2026', payment_status=2000, accepte_by='operator',
            activation_date=timezone.now(),
        )
        records = SimpleNamespace(iterator=lambda chunk_size: iter([record]))

        response = views._activation_report_excel(records, 'userinfo', '2026-10')

        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment; filename="user-licenses-activation-report-2026-10.xlsx"', response['Content-Disposition'])
        self.assertTrue(response.content.startswith(b'PK'))

    def test_report_template_has_filter_and_excel_export(self):
        request = self.factory.get('/')
        request.user = SimpleNamespace(is_authenticated=True, is_superuser=False, username='operator')
        html = render_to_string('licensing/activation_report.html', {
            'request': request,
            'license_type': 'userinfo',
            'report_back_url': 'licensing:userinfo_dashboard',
            'report_type': 'range',
            'report_month_value': '2026-10',
            'report_date_value': '2026-10-13',
            'range_start_value': '2026-10-01',
            'range_end_value': '2026-10-13',
            'report_month': '01 Oct 2026 - 13 Oct 2026',
            'selected_activation_count': 1,
            'selected_collection_total': 2000,
            'report_cards': [],
            'report_records': [],
        })
        self.assertIn('Export Excel', html)
        self.assertIn('name="range_start"', html)
