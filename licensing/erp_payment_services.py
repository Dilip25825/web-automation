import secrets

from django.core import signing
from django.db import transaction
from django.utils import timezone

from .models import tblPacsErp
from .payment_services import PaymentError, PENDING_STATUSES, _razorpay_request

ERP_TOKEN_SALT = 'licensing.erp-razorpay-payment.v1'


def _is_fully_paid(record):
    amount = int(record.amount or 0)
    return amount > 0 and int(record.payment_status or 0) == amount


def find_erp_payment_record(erp_id, for_update=False):
    erp_id = str(erp_id or '').strip()
    if not erp_id:
        raise PaymentError('ERP ID is required.', 'INVALID_ERP_ID')
    queryset = tblPacsErp.objects
    if for_update:
        queryset = queryset.select_for_update()
    records = list(queryset.filter(erp_id__iexact=erp_id).order_by('-id')[:2])
    if not records:
        raise PaymentError('Matching ERP record was not found.', 'ERP_RECORD_NOT_FOUND', 404)
    if len(records) > 1:
        raise PaymentError('Multiple matching ERP records exist. Please contact support.', 'DUPLICATE_ERP_RECORD', 409)
    return records[0]


def _erp_token(record):
    return signing.dumps(
        {'record_id': record.pk, 'erp_id': record.erp_id or '', 'link_id': record.razorpay_payment_link_id or ''},
        salt=ERP_TOKEN_SALT,
        compress=True,
    )


def erp_record_from_token(token):
    try:
        payload = signing.loads(token, salt=ERP_TOKEN_SALT, max_age=21600)
    except signing.SignatureExpired as exc:
        raise PaymentError('ERP payment status token has expired.', 'TOKEN_EXPIRED', 401) from exc
    except signing.BadSignature as exc:
        raise PaymentError('Invalid ERP payment status token.', 'INVALID_TOKEN', 401) from exc
    try:
        record = tblPacsErp.objects.get(pk=payload['record_id'])
    except (tblPacsErp.DoesNotExist, KeyError, ValueError) as exc:
        raise PaymentError('ERP payment record was not found.', 'ERP_RECORD_NOT_FOUND', 404) from exc
    if payload.get('erp_id') != (record.erp_id or ''):
        raise PaymentError('ERP payment token no longer matches this record.', 'TOKEN_RECORD_MISMATCH', 409)
    if payload.get('link_id') and payload['link_id'] != (record.razorpay_payment_link_id or ''):
        raise PaymentError('ERP payment token is no longer current.', 'STALE_TOKEN', 409)
    return record


def get_erp_payment_status(token):
    record = erp_record_from_token(token)
    if not record.razorpay_payment_link_id:
        raise PaymentError('ERP Payment Link is not available.', 'PAYMENT_LINK_NOT_FOUND', 404)
    link = _razorpay_request('GET', f'payment_links/{record.razorpay_payment_link_id}')
    remote_status = str(link.get('status') or '').lower()
    if remote_status == 'paid' and link.get('payments'):
        payment_summary = link['payments'][-1]
        payment_id = str(payment_summary.get('id') or payment_summary.get('payment_id') or '').strip()
        if not payment_id:
            raise PaymentError('Razorpay Payment ID is missing.', 'MISSING_PAYMENT_ID', 400)
        payment = _razorpay_request('GET', f'payments/{payment_id}')
        result = process_erp_payment_link_paid(link, payment)
        activated = tblPacsErp.objects.get(pk=result['record_id'])
        return {'success': True, 'paid': True, 'status': 'PAID', 'erp_id': activated.erp_id, 'record_id': activated.pk, 'amount': int(activated.payment_status or 0) * 100}
    if remote_status in PENDING_STATUSES:
        record.razorpay_payment_status = remote_status
        record.save(update_fields=['razorpay_payment_status'])
    return {'success': True, 'paid': False, 'status': (remote_status or record.razorpay_payment_status or 'created').upper(), 'erp_id': record.erp_id, 'record_id': record.pk, 'amount': int(record.current_amount or 4500) * 100}

def _response(record, link=None, paid=False):
    return {
        'success': True,
        'paid': paid,
        'already_paid': False,
        'payment_url': None if paid else (link or {}).get('short_url'),
        'payment_token': None if paid else _erp_token(record),
        'amount': int(record.current_amount or 4500) * 100,
        'currency': 'INR',
        'status': 'PAID' if paid else str(record.razorpay_payment_status or 'created').upper(),
        'erp_id': record.erp_id,
    }


def create_erp_payment_link(erp_id=None, record_id=None):
    with transaction.atomic():
        if record_id is not None:
            if not str(record_id).strip().isdigit():
                raise PaymentError('Valid ERP database ID is required.', 'INVALID_ERP_RECORD_ID')
            try:
                record = tblPacsErp.objects.select_for_update().get(pk=int(record_id))
            except tblPacsErp.DoesNotExist as exc:
                raise PaymentError('ERP database record was not found.', 'ERP_RECORD_NOT_FOUND', 404) from exc
            if (record.erp_id or '').strip().lower().endswith(' expired'):
                raise PaymentError('Expired ERP history record cannot be activated.', 'ERP_HISTORY_RECORD', 409)
        else:
            record = find_erp_payment_record(erp_id, for_update=True)
        amount_rupees = int(record.current_amount or (3500 if _is_fully_paid(record) else 4500))
        if amount_rupees <= 0:
            raise PaymentError('ERP payment amount is not configured.', 'INVALID_DATABASE_AMOUNT', 409)
        if record.razorpay_payment_link_id:
            link = _razorpay_request('GET', f'payment_links/{record.razorpay_payment_link_id}')
            remote_status = str(link.get('status') or '').lower()
            if remote_status in PENDING_STATUSES:
                record.razorpay_payment_status = remote_status
                record.save(update_fields=['razorpay_payment_status'])
                return _response(record, link)
            if remote_status == 'paid' and link.get('payments'):
                payment_summary = link['payments'][-1]
                payment_id = str(payment_summary.get('id') or payment_summary.get('payment_id') or '').strip()
                if not payment_id:
                    raise PaymentError('Razorpay Payment ID is missing.', 'MISSING_PAYMENT_ID', 400)
                payment = _razorpay_request('GET', f'payments/{payment_id}')
                result = process_erp_payment_link_paid(link, payment)
                return {**_response(record, paid=True), **result}
        reference = f'E{record.pk}-{secrets.token_hex(8)}'[:40]
        record.razorpay_reference_id = reference
        record.razorpay_payment_link_id = None
        record.razorpay_payment_status = 'initiating'
        record.save(update_fields=['razorpay_reference_id', 'razorpay_payment_link_id', 'razorpay_payment_status'])
        payload = {
            'amount': amount_rupees * 100,
            'currency': 'INR',
            'accept_partial': False,
            'reference_id': reference,
            'description': f'ERP Activation {record.erp_id}',
            'customer': {
                'name': (record.pacs_name or 'PACS ERP Customer')[:255],
                'contact': str(record.operator_mobile or ''),
            },
            'notify': {'sms': False, 'email': False},
            'reminder_enable': True,
            'notes': {'record_type': 'pacs_erp', 'record_id': str(record.pk), 'erp_id': record.erp_id or ''},
        }
        try:
            link = _razorpay_request('POST', 'payment_links', json=payload)
        except Exception:
            record.razorpay_payment_status = 'create_failed'
            record.save(update_fields=['razorpay_payment_status'])
            raise
        link_id = link.get('id')
        if not link_id or not link.get('short_url'):
            raise PaymentError('Razorpay did not return a usable ERP Payment Link.', 'RAZORPAY_INVALID_RESPONSE', 502)
        record.razorpay_payment_link_id = link_id
        record.razorpay_payment_status = str(link.get('status') or 'created').lower()
        record.save(update_fields=['razorpay_payment_link_id', 'razorpay_payment_status'])
        return _response(record, link)


def _expiry_one_year_from_today():
    today = timezone.localdate()
    try:
        return today.replace(year=today.year + 1)
    except ValueError:
        return today.replace(year=today.year + 1, day=28)


def process_erp_payment_link_paid(link, payment):
    link_id = str(link.get('id') or '').strip()
    if not link_id:
        raise PaymentError('Payment Link ID is missing.', 'MISSING_PAYMENT_LINK_ID', 400)
    with transaction.atomic():
        try:
            record = tblPacsErp.objects.select_for_update().get(razorpay_payment_link_id=link_id)
        except tblPacsErp.DoesNotExist as exc:
            raise PaymentError('Unknown ERP Payment Link ID.', 'UNKNOWN_ERP_PAYMENT_LINK', 404) from exc
        expected = int(record.current_amount or 4500) * 100
        if link.get('reference_id') != record.razorpay_reference_id:
            raise PaymentError('ERP Payment Link does not match the local record.', 'PAYMENT_LINK_MISMATCH', 400)
        if str(link.get('currency') or '').upper() != 'INR' or str(payment.get('currency') or '').upper() != 'INR':
            raise PaymentError('Payment currency is invalid.', 'WRONG_CURRENCY', 400)
        if int(link.get('amount') or 0) != expected or int(payment.get('amount') or 0) != expected:
            raise PaymentError('Paid amount does not match CurrentAmount.', 'WRONG_AMOUNT', 400)
        if str(link.get('status') or '').lower() != 'paid' or str(payment.get('status') or '').lower() != 'captured':
            raise PaymentError('Payment has not been captured.', 'PAYMENT_NOT_CAPTURED', 400)
        payment_id = str(payment.get('id') or payment.get('payment_id') or '').strip()
        if not payment_id:
            raise PaymentError('Razorpay Payment ID is missing.', 'MISSING_PAYMENT_ID', 400)
        existing = tblPacsErp.objects.filter(razorpay_payment_id=payment_id).first()
        if existing:
            return {'duplicate': True, 'record_id': existing.pk, 'erp_id': existing.erp_id}
        rrn = ''
        acquirer = payment.get('acquirer_data') or {}
        if isinstance(acquirer, dict):
            rrn = str(acquirer.get('rrn') or acquirer.get('bank_transaction_id') or '').strip()
        activation_time = timezone.now()
        expiry_date = _expiry_one_year_from_today()
        paid_amount = expected // 100
        if _is_fully_paid(record):
            original_erp_id = (record.erp_id or '').strip()
            record.erp_id = f'{original_erp_id} Expired'
            record.is_active = 0
            record.razorpay_payment_link_id = None
            record.razorpay_reference_id = None
            record.razorpay_payment_status = None
            record.save(update_fields=['erp_id', 'is_active', 'razorpay_payment_link_id', 'razorpay_reference_id', 'razorpay_payment_status'])
            record = tblPacsErp.objects.create(
                amount=paid_amount, current_amount=3500, brach=record.brach, dist=record.dist,
                erp_id=original_erp_id, expiry_date=expiry_date, is_active=1,
                last_login=record.last_login, operator_mobile=record.operator_mobile,
                pacs_name=record.pacs_name, payment_status=paid_amount,
                remark='Activated automatically by Razorpay.', state=record.state,
                system_id=record.system_id, utr_number=rrn, version_info=record.version_info,
                accepte_by='Razorpay', activation_date=activation_time,
                razorpay_payment_link_id=link_id, razorpay_payment_id=payment_id,
                razorpay_reference_id=str(link.get('reference_id') or ''), razorpay_payment_status='paid',
            )
        else:
            record.amount = paid_amount
            record.current_amount = 3500
            record.payment_status = paid_amount
            record.utr_number = rrn or record.utr_number
            record.accepte_by = 'Razorpay'
            record.activation_date = activation_time
            record.expiry_date = expiry_date
            record.is_active = 1
            record.razorpay_payment_id = payment_id
            record.razorpay_payment_status = 'paid'
            record.remark = 'Activated automatically by Razorpay.'
            record.save()
        return {'duplicate': False, 'record_id': record.pk, 'erp_id': record.erp_id}


def process_erp_payment_link_state(link, state):
    link_id = str(link.get('id') or '').strip()
    if not link_id:
        return False
    with transaction.atomic():
        try:
            record = tblPacsErp.objects.select_for_update().get(razorpay_payment_link_id=link_id)
        except tblPacsErp.DoesNotExist:
            return False
        if state == 'cancelled':
            record.razorpay_payment_link_id = None
            record.razorpay_reference_id = None
            record.razorpay_payment_status = None
            record.save(update_fields=['razorpay_payment_link_id', 'razorpay_reference_id', 'razorpay_payment_status'])
        else:
            record.razorpay_payment_status = state
            record.save(update_fields=['razorpay_payment_status'])
    return True
