import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core import signing
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from . import interest_subvention_views as views


@override_settings(
    ALLOWED_HOSTS=["testserver"],
    ERP_API_IP_RATE_LIMIT=100,
    ERP_API_MOBILE_RATE_LIMIT=100,
)
class InterestSubventionApiTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def post(self, route_name, body):
        return self.factory.post(
            reverse(f"license_api:{route_name}"),
            data=json.dumps(body),
            content_type="application/json",
        )

    @staticmethod
    def record(**overrides):
        values = {
            "pk": 7,
            "mobile": 8462012451,
            "pacs_name": "21UJJ/UNH/BAR",
            "for_whys": views.PURPOSE,
            "f_year": "2025-2026",
            "is_active": 1,
            "amount": 2500,
            "payment_status": 2500,
            "entry_count": 4,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    @patch("licensing.interest_subvention_views.Perpous.objects")
    def test_options_returns_only_interest_subvention_years(self, objects):
        queryset = objects.filter.return_value
        queryset.exclude.return_value.exclude.return_value.order_by.return_value.values_list.return_value.distinct.return_value = [
            "2025-2026", "2024-2025"
        ]
        response = views.options(self.post("interest_subvention_options", {}))
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["financial_years"], ["2025-2026", "2024-2025"])
        objects.filter.assert_called_once_with(forWhy__iexact=views.PURPOSE)
    @patch("licensing.interest_subvention_views._select_record")
    def test_exact_paid_identity_is_authorized(self, select_record):
        select_record.return_value = (self.record(), False)
        response = views.subscription(
            self.post(
                "interest_subvention_subscription",
                {
                    "mobile": "8462012451",
                    "pacs_name": "21UJJ/UNH/BAR",
                    "forWhys": "INTEREST SUBVENTION",
                    "fYear": "2025-2026",
                },
            )
        )
        data = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["authorized"])
        self.assertTrue(data["record_token"])
        select_record.assert_called_once_with("8462012451", "2025-2026")
        token_data = signing.loads(data["record_token"], salt=views.TOKEN_SALT)
        self.assertEqual(token_data["service"], views.PURPOSE)

    @patch("licensing.interest_subvention_views._select_record")
    def test_payment_must_equal_amount(self, select_record):
        select_record.return_value = (
            self.record(amount=2500, payment_status=0),
            False,
        )
        response = views.subscription(
            self.post(
                "interest_subvention_subscription",
                {
                    "mobile": "8462012451",
                    "pacs_name": "21UJJ/UNH/BAR",
                    "forWhys": views.PURPOSE,
                    "fYear": "2025-2026",
                },
            )
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(json.loads(response.content)["status"], "PAYMENT_REQUIRED")

    @patch("licensing.interest_subvention_views._select_record")
    def test_zero_amount_is_valid_when_payment_status_is_also_zero(self, select_record):
        select_record.return_value = (
            self.record(amount=0, payment_status=0),
            False,
        )
        response = views.subscription(
            self.post(
                "interest_subvention_subscription",
                {
                    "mobile": "8462012451",
                    "pacs_name": "21UJJ/UNH/BAR",
                    "forWhys": views.PURPOSE,
                    "fYear": "2025-2026",
                },
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(json.loads(response.content)["authorized"])
    def test_wrong_service_is_rejected(self):
        response = views.subscription(
            self.post(
                "interest_subvention_subscription",
                {
                    "mobile": "8462012451",
                    "pacs_name": "21UJJ/UNH/BAR",
                    "forWhys": "PMFBY",
                    "fYear": "2025-2026",
                },
            )
        )
        self.assertEqual(response.status_code, 400)

    @patch("licensing.interest_subvention_views.transaction.atomic", return_value=nullcontext())
    @patch("licensing.interest_subvention_views.UserInfoData.objects")
    @patch("licensing.interest_subvention_views._record_from_token")
    def test_consume_increments_entry_count(self, token_record, objects, _atomic):
        record = self.record()
        locked = self.record()
        locked.save = MagicMock()
        token_record.return_value = (record, None)
        objects.select_for_update.return_value.filter.return_value.first.return_value = locked
        response = views.consume_entries(
            self.post(
                "interest_subvention_entries_consume",
                {"record_token": "signed-token", "uploaded_count": 3},
            )
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(locked.entry_count, 7)
        locked.save.assert_called_once_with(update_fields=["entry_count"])