from decimal import Decimal
from uuid import UUID

from django.contrib.auth.models import User
from django.utils import timezone

from khata.models import ActivationLedgerEntry, ActivationLedgerMapping, Customer, Transaction


class ActivationLedgerError(ValueError):
    pass


def activation_ledger_context(user):
    if not user.is_superuser:
        return {'activation_user_options': [], 'activation_khata_customers': []}

    mappings = dict(
        ActivationLedgerMapping.objects.filter(owner=user).values_list('accepted_user_id', 'customer_id')
    )
    user_options = [
        {
            'id': item.id,
            'username': item.username,
            'customer_id': mappings.get(item.id, ''),
            'selected': item.id == user.id,
        }
        for item in User.objects.filter(is_active=True).order_by('username')
    ]
    customers = Customer.objects.filter(user=user).order_by('name', 'id')
    return {'activation_user_options': user_options, 'activation_khata_customers': customers}


def prepare_manual_activation(request, amount):
    if not request.user.is_superuser:
        return {
            'accepted_user': request.user,
            'accepted_username': request.user.username,
            'ledger_enabled': False,
        }

    accepted_user_id = str(request.POST.get('accepted_by_user', '')).strip()
    if not accepted_user_id.isdigit():
        raise ActivationLedgerError('Activated By user select karna zaroori hai.')
    try:
        accepted_user = User.objects.get(pk=int(accepted_user_id), is_active=True)
    except User.DoesNotExist as exc:
        raise ActivationLedgerError('Selected Activated By user valid nahi hai.') from exc

    ledger_enabled = str(request.POST.get('khata_effect', '')).strip() == '1'
    ledger_required = accepted_user.username.casefold() != 'admin'
    if ledger_required and not ledger_enabled:
        raise ActivationLedgerError('Admin ke alawa user select karne par Khata ledger effect zaroori hai.')

    prepared = {
        'accepted_user': accepted_user,
        'accepted_username': accepted_user.username,
        'ledger_enabled': ledger_enabled,
    }
    if not ledger_enabled:
        return prepared

    if int(amount or 0) <= 0:
        raise ActivationLedgerError('Khata ledger ke liye amount zero se bada hona chahiye.')
    customer_id = str(request.POST.get('khata_customer', '')).strip()
    if not customer_id.isdigit():
        raise ActivationLedgerError('Khata customer/ledger select karna zaroori hai.')
    try:
        customer = Customer.objects.get(pk=int(customer_id), user=request.user)
    except Customer.DoesNotExist as exc:
        raise ActivationLedgerError('Selected Khata customer aapke ledger me nahi mila.') from exc

    token_value = str(request.POST.get('activation_token', '')).strip()
    try:
        activation_token = UUID(token_value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ActivationLedgerError('Activation security token invalid hai. Modal dobara kholkar try karein.') from exc

    prepared.update({'customer': customer, 'activation_token': activation_token, 'amount': Decimal(str(amount))})
    return prepared


def create_activation_ledger_entry(prepared, *, request_user, source_type, source_record_id, source_label):
    if not prepared.get('ledger_enabled'):
        return None

    token = prepared['activation_token']
    if ActivationLedgerEntry.objects.filter(activation_token=token).exists():
        raise ActivationLedgerError('Is activation ki Khata entry pehle hi ban chuki hai.')

    accepted_user = prepared['accepted_user']
    customer = prepared['customer']
    amount = prepared['amount']
    transaction_remark = (
        source_label
        if source_type == 'USERINFO'
        else f'{source_type} Activation: {source_label} | Activated By: {accepted_user.username}'
    )
    khata_transaction = Transaction.objects.create(
        customer=customer,
        amount=amount,
        trans_type='GIVEN',
        date=timezone.localdate(),
        remarks=transaction_remark,
    )
    ActivationLedgerMapping.objects.update_or_create(
        owner=request_user,
        accepted_user=accepted_user,
        defaults={'customer': customer},
    )
    return ActivationLedgerEntry.objects.create(
        activation_token=token,
        source_type=source_type,
        source_record_id=source_record_id,
        activated_by=request_user,
        accepted_by=accepted_user,
        customer=customer,
        transaction=khata_transaction,
        amount=amount,
    )

def reverse_activation_ledger_entry(*, source_type, source_record_id):
    try:
        entry = (
            ActivationLedgerEntry.objects.select_for_update()
            .filter(source_type=source_type, source_record_id=source_record_id)
            .latest('created_at')
        )
    except ActivationLedgerEntry.DoesNotExist as exc:
        raise ActivationLedgerError('Is activation se linked Khata entry nahi mili.') from exc
    if entry.reversal_transaction_id:
        raise ActivationLedgerError('Is activation ka Khata balance pehle hi reverse ho chuka hai.')

    reversal = Transaction.objects.create(
        customer=entry.customer,
        amount=entry.amount,
        trans_type='GOT',
        date=timezone.localdate(),
        remarks=f'{entry.source_type} Activation Reversal: Record #{entry.source_record_id} | Accepted By: {entry.accepted_by.username}',
    )
    entry.reversal_transaction = reversal
    entry.save(update_fields=['reversal_transaction'])
    return reversal