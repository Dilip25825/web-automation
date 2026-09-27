from unittest.mock import Mock, patch
from types import SimpleNamespace

from django.contrib import admin
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase

from khata.admin import ActivationOperatorSettingsAdmin
from khata.access import menu_permissions
from khata.models import ActivationLedgerMapping, ActivationOperatorSettings, Customer, Transaction
from licensing.activation_ledger import (
    ActivationLedgerError, create_activation_ledger_entry,
    prepare_manual_activation, search_only_operator,
)
from licensing import views


class SelectedOperatorTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_superuser('admin', password='test-only')
        self.operator = User.objects.create_user('selected')
        self.other = User.objects.create_user('other')
        self.customer = Customer.objects.create(user=self.owner, name='Operator ledger', phone='9999999999')
        self.settings = ActivationOperatorSettings.objects.create(
            user=self.operator, customer=self.customer, automatic_ledger=True,
        )
        self.factory = RequestFactory()

    def request(self, user=None):
        request = self.factory.post('/', {'khata_effect': '0', 'khata_customer': '999'})
        request.user = user or self.operator
        return request

    def test_only_selected_user_creates_private_entry_for_both_sources(self):
        for source in ('USERINFO', 'PACS_ERP'):
            plan = prepare_manual_activation(self.request(), 2000)
            entry = create_activation_ledger_entry(
                plan, request_user=self.operator, source_type=source,
                source_record_id=1, source_label='Test license',
            )
            self.assertEqual(entry.customer.user, self.owner)
            self.assertEqual(entry.activated_by, self.operator)
            self.assertEqual(entry.transaction.trans_type, 'GIVEN')
            self.assertEqual(entry.amount, 2000)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertFalse(prepare_manual_activation(self.request(self.other), 2000)['ledger_enabled'])
        self.assertTrue(ActivationLedgerMapping.objects.filter(owner=self.owner, accepted_user=self.operator).exists())
        self.assertFalse(ActivationLedgerMapping.objects.filter(owner=self.operator).exists())

    def test_off_disables_entries_but_keeps_search_only(self):
        self.settings.automatic_ledger = False
        self.settings.save()
        self.assertFalse(prepare_manual_activation(self.request(), 2000)['ledger_enabled'])
        self.assertTrue(search_only_operator(self.operator))
        self.assertFalse(search_only_operator(self.other))
        self.assertFalse(search_only_operator(self.owner))

    def test_invalid_amount_and_demoted_owner_fail_closed(self):
        with self.assertRaises(ActivationLedgerError):
            prepare_manual_activation(self.request(), 0)
        self.owner.is_superuser = False
        self.owner.save()
        with self.assertRaises(ActivationLedgerError):
            prepare_manual_activation(self.request(), 2000)
        with self.assertRaises(ValidationError):
            self.settings.full_clean()

    def test_operator_cannot_read_superuser_ledger(self):
        from khata import views as khata_views
        with patch.object(khata_views, 'render') as render, patch.object(khata_views, 'messages'):
            response = khata_views.customer_detail(self.request(), self.customer.pk)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/khata/')
        render.assert_not_called()

    def test_userinfo_activation_adds_once_without_exposing_whatsapp(self):
        record = SimpleNamespace(pk=9, id=9, is_active=0, amount=0, payment_status=0, accepte_by='', for_whys='PMFBY',
                                 activation_date=None, f_year='2026', mobile=1234567890, save=Mock())
        with patch.object(views, 'UserInfoData') as model, \
                patch.object(views, '_utr_used_elsewhere', return_value=False), \
                patch.object(views, '_activation_whatsapp_url') as whatsapp, \
                patch.object(views, 'messages'), patch.object(views, 'logger'):
            model.objects.select_for_update.return_value.get.return_value = record
            for _ in range(2):
                request = self.factory.post('/', {'amount': '2000'})
                request.user = self.operator
                views.toggle_activation(request, 9)
                self.assertFalse(hasattr(request, '_licensing_whatsapp_url'))
            whatsapp.assert_not_called()
        self.assertEqual(Transaction.objects.count(), 1)
        record.save.assert_called_once()

    def test_userinfo_activation_cannot_modify_another_users_record(self):
        record = SimpleNamespace(accepte_by='someone-else', save=Mock())
        with patch.object(views, 'UserInfoData') as model, \
                patch.object(views, '_utr_used_elsewhere', return_value=False), \
                patch.object(views, 'messages'), patch.object(views, 'logger'):
            model.objects.select_for_update.return_value.get.return_value = record
            request = self.factory.post('/', {'amount': '2000'})
            request.user = self.operator
            views.toggle_activation(request, 9)
        record.save.assert_not_called()
        self.assertFalse(Transaction.objects.exists())

    def test_incomplete_userinfo_record_can_be_activated(self):
        record = SimpleNamespace(pk=10, id=10, is_active=1, amount=0, payment_status=0,
                                 accepte_by='', for_whys='PMFBY', activation_date=None,
                                 f_year='2026', mobile=1234567890, save=Mock())
        with patch.object(views, 'UserInfoData') as model, \
                patch.object(views, '_utr_used_elsewhere', return_value=False), \
                patch.object(views, 'messages'), patch.object(views, 'logger'):
            model.objects.select_for_update.return_value.get.return_value = record
            request = self.factory.post('/', {'amount': '2000'})
            request.user = self.operator
            views.toggle_activation(request, 10)
        record.save.assert_called_once()
        self.assertEqual(Transaction.objects.count(), 1)

    def test_paid_userinfo_record_cannot_be_activated_twice(self):
        record = SimpleNamespace(pk=11, id=11, is_active=1, amount=2000, payment_status=2000,
                                 accepte_by='', for_whys='PMFBY', activation_date=None,
                                 f_year='2026', mobile=1234567890, save=Mock())
        with patch.object(views, 'UserInfoData') as model, \
                patch.object(views, '_utr_used_elsewhere', return_value=False), \
                patch.object(views, 'messages'), patch.object(views, 'logger'):
            model.objects.select_for_update.return_value.get.return_value = record
            request = self.factory.post('/', {'amount': '2000'})
            request.user = self.operator
            views.toggle_activation(request, 11)
        record.save.assert_not_called()
        self.assertFalse(Transaction.objects.exists())

    def test_settings_admin_is_superuser_only_and_owner_scoped(self):
        model_admin = ActivationOperatorSettingsAdmin(ActivationOperatorSettings, admin.site)
        request = self.request()
        for check in (model_admin.has_view_permission, model_admin.has_add_permission,
                      model_admin.has_change_permission, model_admin.has_delete_permission):
            self.assertFalse(check(request))
        self.assertFalse(model_admin.get_queryset(request).exists())
        self.assertEqual(model_admin.get_queryset(self.request(self.owner)).count(), 1)

    def test_menu_permissions_apply_to_navigation_and_direct_urls(self):
        self.settings.show_dashboard = False
        self.settings.show_reminders = False
        self.settings.show_khata = False
        self.settings.show_coupons = False
        self.settings.show_downloads = False
        self.settings.save()
        permissions = menu_permissions(self.operator)
        self.assertTrue(permissions['user_licenses'])
        self.assertTrue(permissions['erp_licenses'])
        self.assertFalse(permissions['khata'])
        self.client.force_login(self.operator)
        self.assertEqual(self.client.get('/khata/').status_code, 403)
        self.assertEqual(self.client.get('/reminders/').status_code, 403)
        response = self.client.get('/licensing/userinfo/')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'href="/khata/"')
        self.assertContains(response, 'href="/licensing/userinfo/"')

    def test_blank_search_clears_both_dashboard_querysets(self):
        for view, model in ((views.userinfo_dashboard, 'UserInfoData'), (views.pacserp_dashboard, 'tblPacsErp')):
            with self.subTest(view=view.__name__), patch.object(views, model) as mocked_model, \
                    patch.object(views, '_erp_queryset_for_user') as erp, \
                    patch.object(views, 'render'), patch.object(views, 'messages'), \
                    patch.object(views, 'logger'):
                queryset = Mock()
                mocked_model.objects.filter.return_value = queryset
                erp.return_value = queryset
                # Stop report processing after the empty-queryset decision.
                with patch.object(views, '_activation_report_period', side_effect=ValueError):
                    for query in ('', '?search_id=+++', '?record_id=10', '?partial=1&page=2'):
                        queryset.reset_mock()
                        request = self.factory.get('/' + query)
                        request.user = self.operator
                        view(request)
                        queryset.none.assert_called_once()
                    queryset.reset_mock()
                    request = self.factory.get('/?search_id=1234567890')
                    request.user = self.operator
                    view(request)
                    queryset.none.assert_not_called()
