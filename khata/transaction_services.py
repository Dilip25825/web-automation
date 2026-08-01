from django.db import transaction as db_transaction
from django.db.models import Q

from .models import ActivationLedgerEntry, Transaction


def delete_transaction_with_activation_links(transaction, owner):
    with db_transaction.atomic():
        locked_transaction = Transaction.objects.select_for_update().get(
            pk=transaction.pk,
            customer__user=owner,
        )
        ledger_entry = (
            ActivationLedgerEntry.objects.select_for_update()
            .filter(activated_by=owner)
            .filter(Q(transaction=locked_transaction) | Q(reversal_transaction=locked_transaction))
            .first()
        )

        transactions = [locked_transaction]
        if ledger_entry:
            linked_ids = {ledger_entry.transaction_id, ledger_entry.reversal_transaction_id}
            linked_ids.discard(None)
            transactions = list(
                Transaction.objects.select_for_update().filter(
                    pk__in=linked_ids,
                    customer__user=owner,
                )
            )

        attachment_ids = [item.attachment_drive_id for item in transactions if item.attachment_drive_id]
        transaction_ids = [item.pk for item in transactions]
        if ledger_entry:
            ledger_entry.delete()
        Transaction.objects.filter(pk__in=transaction_ids, customer__user=owner).delete()
        return {'attachment_ids': attachment_ids, 'linked': bool(ledger_entry), 'deleted_count': len(transaction_ids)}