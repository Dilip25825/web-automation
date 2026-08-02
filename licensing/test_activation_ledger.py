from uuid import uuid4

from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase

from khata.models import ActivationLedgerEntry, ActivationLedgerMapping, Customer, Transaction
from khata.transaction_services import delete_transaction_with_activation_links
from licensing.activation_ledger import (
    ActivationLedgerError,
    create_activation_ledger_entry,
    prepare_manual_activation,
    reverse_activation_ledger_entry,
)


class ActivationKhataIntegrationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = User.objects.create_superuser(username='Admin', password='test-pass')
        self.operator = User.objects.create_user(username='operator-one', password='test-pass')
        self.customer = Customer.objects.create(user=self.owner, name='Operator One Ledger', phone='9999999999')

    def request(self, data):
        request = self.factory.post('/licensing/toggle/7/', data)
        request.user = self.owner
        return request

    def test_non_admin_can_activate_without_khata_effect(self):
        request = self.request({'accepted_by_user': self.operator.id})
        result = prepare_manual_activation(request, 2000)
        self.assertFalse(result['ledger_enabled'])
        self.assertEqual(result['accepted_username'], 'operator-one')

    def test_admin_can_activate_without_khata_effect(self):
        request = self.request({'accepted_by_user': self.owner.id})
        result = prepare_manual_activation(request, 2000)
        self.assertFalse(result['ledger_enabled'])
        self.assertEqual(result['accepted_username'], 'Admin')

    def test_ledger_entry_is_given_and_mapping_is_saved(self):
        token = uuid4()
        request = self.request({
            'accepted_by_user': self.operator.id,
            'khata_effect': '1',
            'khata_customer': self.customer.id,
            'activation_token': str(token),
        })
        plan = prepare_manual_activation(request, 3500)
        entry = create_activation_ledger_entry(
            plan,
            request_user=self.owner,
            source_type='PACS_ERP',
            source_record_id=17,
            source_label='ERP ID TEST17',
        )
        self.assertEqual(entry.transaction.trans_type, 'GIVEN')
        self.assertEqual(entry.transaction.amount, 3500)
        self.assertTrue(ActivationLedgerMapping.objects.filter(
            owner=self.owner, accepted_user=self.operator, customer=self.customer
        ).exists())

    def test_duplicate_activation_token_does_not_create_second_transaction(self):
        token = uuid4()
        request = self.request({
            'accepted_by_user': self.operator.id,
            'khata_effect': '1',
            'khata_customer': self.customer.id,
            'activation_token': str(token),
        })
        plan = prepare_manual_activation(request, 2000)
        create_activation_ledger_entry(
            plan, request_user=self.owner, source_type='USERINFO', source_record_id=8, source_label='Record #8'
        )
        with self.assertRaisesMessage(ActivationLedgerError, 'pehle hi ban chuki hai'):
            create_activation_ledger_entry(
                plan, request_user=self.owner, source_type='USERINFO', source_record_id=8, source_label='Record #8'
            )
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(ActivationLedgerEntry.objects.count(), 1)
        self.assertEqual(Transaction.objects.get().remarks, 'Record #8')
    def test_reversal_creates_got_entry_without_deleting_original(self):
        request = self.request({
            'accepted_by_user': self.operator.id,
            'khata_effect': '1',
            'khata_customer': self.customer.id,
            'activation_token': str(uuid4()),
        })
        plan = prepare_manual_activation(request, 2000)
        entry = create_activation_ledger_entry(
            plan, request_user=self.owner, source_type='USERINFO', source_record_id=9, source_label='Record #9'
        )
        reversal = reverse_activation_ledger_entry(source_type='USERINFO', source_record_id=9)
        entry.refresh_from_db()
        self.assertEqual(reversal.trans_type, 'GOT')
        self.assertEqual(reversal.amount, entry.amount)
        self.assertEqual(entry.reversal_transaction_id, reversal.id)
        self.assertEqual(Transaction.objects.count(), 2)

    def test_same_activation_cannot_be_reversed_twice(self):
        request = self.request({
            'accepted_by_user': self.operator.id,
            'khata_effect': '1',
            'khata_customer': self.customer.id,
            'activation_token': str(uuid4()),
        })
        plan = prepare_manual_activation(request, 2000)
        create_activation_ledger_entry(
            plan, request_user=self.owner, source_type='PACS_ERP', source_record_id=21, source_label='ERP #21'
        )
        reverse_activation_ledger_entry(source_type='PACS_ERP', source_record_id=21)
        with self.assertRaisesMessage(ActivationLedgerError, 'pehle hi reverse'):
            reverse_activation_ledger_entry(source_type='PACS_ERP', source_record_id=21)
    def test_manual_delete_removes_linked_original_and_reversal_entries(self):
        request = self.request({
            'accepted_by_user': self.operator.id,
            'khata_effect': '1',
            'khata_customer': self.customer.id,
            'activation_token': str(uuid4()),
        })
        plan = prepare_manual_activation(request, 1750)
        entry = create_activation_ledger_entry(
            plan, request_user=self.owner, source_type='USERINFO', source_record_id=11583, source_label='PMFBY Kharif 2026 | Mobile 9216081342 / Record #11583'
        )
        reverse_activation_ledger_entry(source_type='USERINFO', source_record_id=11583)
        result = delete_transaction_with_activation_links(entry.transaction, self.owner)
        self.assertTrue(result['linked'])
        self.assertEqual(result['deleted_count'], 2)
        self.assertEqual(Transaction.objects.count(), 0)
        self.assertEqual(ActivationLedgerEntry.objects.count(), 0)