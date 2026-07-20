import hashlib
import hmac
import secrets

import requests
from django.conf import settings
from django.core import signing
from django.db import transaction
from django.utils import timezone

from .models import UserInfoData

TOKEN_SALT = 'licensing.razorpay-payment-status.v1'
PENDING_STATUSES = {'created', 'partially_paid'}


class PaymentError(Exception):
    def __init__(self, message, code='PAYMENT_ERROR', http_status=400):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


def _require_configuration(webhook=False):
    required = ['RAZORPAY_WEBHOOK_SECRET'] if webhook else ['RAZORPAY_KEY_ID', 'RAZORPAY_KEY_SECRET']
    missing = [name for name in required if not getattr(settings, name, '')]
    if missing:
        raise PaymentError('Payment gateway is not configured.', 'PAYMENT_NOT_CONFIGURED', 503)


def _razorpay_request(method, path, **kwargs):
    _require_configuration()
    url = f"{settings.RAZORPAY_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        response = requests.request(method, url, auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET), timeout=15, **kwargs)
    except requests.RequestException as exc:
        raise PaymentError('Payment gateway is temporarily unavailable.', 'RAZORPAY_UNAVAILABLE', 502) from exc
    if response.status_code >= 400:
        message = 'Razorpay could not complete the request.'
        try:
            error = (response.json() or {}).get('error') or {}
            description = str(error.get('description') or '').strip()
            gateway_code = str(error.get('code') or '').strip()
            if description:
                message = f'Razorpay: {description}'
            if gateway_code:
                message = f'{message} ({gateway_code})'
        except (ValueError, AttributeError, TypeError):
            pass
        raise PaymentError(message, 'RAZORPAY_API_ERROR', 502)
    try:
        return response.json()
    except ValueError as exc:
        raise PaymentError('Invalid response received from Razorpay.', 'RAZORPAY_INVALID_RESPONSE', 502) from exc


def find_payment_record(user_id, service, financial_year, for_update=False):
    if not str(user_id).isdigit():
        raise PaymentError('Invalid user ID.', 'INVALID_USER_ID')
    queryset = UserInfoData.objects
    if for_update:
        queryset = queryset.select_for_update()
    queryset = queryset.filter(mobile=int(user_id), for_whys__iexact=service.strip(), f_year__iexact=financial_year.strip())
    records = list(queryset[:2])
    if not records:
        raise PaymentError('No matching user, service and financial year record found.', 'PAYMENT_RECORD_NOT_FOUND', 404)
    if len(records) > 1:
        raise PaymentError('Multiple matching payment records exist. Please contact support.', 'DUPLICATE_PAYMENT_RECORD', 409)
    return records[0]


def is_paid(record):
    return int(record.amount or 0) > 0 and int(record.payment_status or 0) == int(record.amount or 0)


def _token_for(record):
    return signing.dumps({'record_id': record.pk, 'user_id': str(record.mobile), 'service': record.for_whys or '', 'financial_year': record.f_year or '', 'link_id': record.razorpay_payment_link_id or ''}, salt=TOKEN_SALT, compress=True)


def record_from_token(token, user_id):
    try:
        payload = signing.loads(token, salt=TOKEN_SALT, max_age=settings.PAYMENT_STATUS_TOKEN_MAX_AGE)
    except signing.SignatureExpired as exc:
        raise PaymentError('Payment status token has expired.', 'TOKEN_EXPIRED', 401) from exc
    except signing.BadSignature as exc:
        raise PaymentError('Invalid payment status token.', 'INVALID_TOKEN', 401) from exc
    if str(payload.get('user_id')) != str(user_id):
        raise PaymentError('Token does not belong to this user.', 'TOKEN_USER_MISMATCH', 403)
    try:
        record = UserInfoData.objects.get(pk=payload['record_id'], mobile=int(user_id))
    except (UserInfoData.DoesNotExist, KeyError, ValueError) as exc:
        raise PaymentError('Payment record was not found.', 'PAYMENT_RECORD_NOT_FOUND', 404) from exc
    if payload.get('service') != (record.for_whys or '') or payload.get('financial_year') != (record.f_year or ''):
        raise PaymentError('Payment token no longer matches this record.', 'TOKEN_RECORD_MISMATCH', 403)
    if payload.get('link_id') and payload['link_id'] != (record.razorpay_payment_link_id or ''):
        raise PaymentError('Payment token is no longer current.', 'STALE_TOKEN', 409)
    return record


def _response(record, link=None):
    paid = is_paid(record)
    status = 'PAID' if paid else ((record.razorpay_payment_status or 'CREATED').upper())
    return {'success': True, 'already_paid': paid, 'paid': paid, 'payment_url': None if paid else (link or {}).get('short_url'), 'payment_token': None if paid else _token_for(record), 'amount': int(record.amount or 0) * 100, 'currency': 'INR', 'status': status, 'service': record.for_whys, 'financial_year': record.f_year}


def create_razorpay_payment_link(record_id):
    with transaction.atomic():
        record = UserInfoData.objects.select_for_update().get(pk=record_id)
        if is_paid(record):
            return _response(record)
        amount_rupees = int(record.amount or 0)
        if amount_rupees <= 0:
            raise PaymentError('Required payment amount is not configured.', 'INVALID_DATABASE_AMOUNT', 409)
        if record.razorpay_payment_link_id:
            link = _razorpay_request('GET', f'payment_links/{record.razorpay_payment_link_id}')
            remote_status = str(link.get('status', '')).lower()
            if remote_status in PENDING_STATUSES:
                record.razorpay_payment_status = remote_status
                record.save(update_fields=['razorpay_payment_status'])
                return _response(record, link)
            if remote_status == 'paid' and link.get('payments'):
                payment = link['payments'][-1]
                _apply_paid_entities(record, link, payment)
                return _response(record)
        reference = f'U{record.pk}-{secrets.token_hex(8)}'[:40]
        record.razorpay_reference_id = reference
        record.razorpay_payment_link_id = None
        record.razorpay_payment_id = None
        record.razorpay_payment_status = 'initiating'
        record.save(update_fields=['razorpay_reference_id', 'razorpay_payment_link_id', 'razorpay_payment_id', 'razorpay_payment_status'])
        payload = {'amount': amount_rupees * 100, 'currency': 'INR', 'accept_partial': False, 'reference_id': reference, 'description': f'{record.for_whys} {record.f_year} {record.mobile}', 'customer': {'name': (getattr(record, 'pacs_name', None) or 'Web Automation Customer')[:255], 'contact': str(record.mobile)}, 'notify': {'sms': False, 'email': False}, 'reminder_enable': True, 'notes': {'record_id': str(record.pk), 'user_id': str(record.mobile), 'service': record.for_whys or '', 'financial_year': record.f_year or ''}}
        try:
            link = _razorpay_request('POST', 'payment_links', json=payload)
        except Exception:
            record.razorpay_payment_status = 'create_failed'
            record.save(update_fields=['razorpay_payment_status'])
            raise
        link_id = link.get('id')
        if not link_id or not link.get('short_url'):
            raise PaymentError('Razorpay did not return a usable Payment Link.', 'RAZORPAY_INVALID_RESPONSE', 502)
        record.razorpay_payment_link_id = link_id
        record.razorpay_payment_status = str(link.get('status') or 'created').lower()
        record.save(update_fields=['razorpay_payment_link_id', 'razorpay_payment_status'])
        return _response(record, link)


def verify_razorpay_webhook_signature(raw_body, signature):
    _require_configuration(webhook=True)
    if not signature:
        return False
    expected = hmac.new(settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def _apply_paid_entities(record, link, payment):
    expected = int(record.amount or 0) * 100
    if link.get('id') != record.razorpay_payment_link_id or link.get('reference_id') != record.razorpay_reference_id:
        raise PaymentError('Payment Link does not match the local record.', 'PAYMENT_LINK_MISMATCH', 400)
    if str(link.get('currency', '')).upper() != 'INR' or str(payment.get('currency', '')).upper() != 'INR':
        raise PaymentError('Payment currency is invalid.', 'WRONG_CURRENCY', 400)
    if int(link.get('amount') or 0) != expected or int(payment.get('amount') or 0) != expected:
        raise PaymentError('Paid amount does not match the required amount.', 'WRONG_AMOUNT', 400)
    if str(link.get('status', '')).lower() != 'paid' or str(payment.get('status', '')).lower() != 'captured':
        raise PaymentError('Payment has not been captured.', 'PAYMENT_NOT_CAPTURED', 400)
    payment_id = payment.get('id') or payment.get('payment_id')
    if not payment_id:
        raise PaymentError('Razorpay Payment ID is missing.', 'MISSING_PAYMENT_ID', 400)
    if record.razorpay_payment_id and record.razorpay_payment_id != payment_id:
        raise PaymentError('A different payment is already recorded.', 'PAYMENT_ID_CONFLICT', 409)
    duplicate = record.razorpay_payment_id == payment_id and is_paid(record)
    update_fields = []
    acquirer_data = payment.get('acquirer_data') or {}
    bank_rrn = ''
    if isinstance(acquirer_data, dict):
        bank_rrn = str(acquirer_data.get('rrn') or acquirer_data.get('bank_transaction_id') or '').strip()
    if bank_rrn and not getattr(record, 'utr_number', None):
        record.utr_number = bank_rrn
        update_fields.append('utr_number')
    if not duplicate:
        record.razorpay_payment_id = payment_id
        record.razorpay_payment_status = 'paid'
        record.payment_status = record.amount
        record.is_active = 1
        record.activation_date = record.activation_date or timezone.now()
        update_fields.extend(['razorpay_payment_id', 'razorpay_payment_status', 'payment_status', 'is_active', 'activation_date'])
    if update_fields:
        record.save(update_fields=update_fields)
    return duplicate


def process_payment_link_paid(link, payment):
    link_id = link.get('id')
    if not link_id:
        raise PaymentError('Payment Link ID is missing.', 'MISSING_PAYMENT_LINK_ID', 400)
    with transaction.atomic():
        try:
            record = UserInfoData.objects.select_for_update().get(razorpay_payment_link_id=link_id)
        except UserInfoData.DoesNotExist as exc:
            raise PaymentError('Unknown Payment Link ID.', 'UNKNOWN_PAYMENT_LINK', 404) from exc
        duplicate = _apply_paid_entities(record, link, payment)
        return {'duplicate': duplicate, 'record_id': record.pk}


def process_payment_link_state(link, state):
    link_id = link.get('id')
    if not link_id:
        return False
    with transaction.atomic():
        try:
            record = UserInfoData.objects.select_for_update().get(razorpay_payment_link_id=link_id)
        except UserInfoData.DoesNotExist:
            return False
        if not is_paid(record):
            if state == 'cancelled':
                record.razorpay_payment_link_id = None
                record.razorpay_payment_id = None
                record.razorpay_reference_id = None
                record.razorpay_payment_status = None
                record.save(update_fields=['razorpay_payment_link_id', 'razorpay_payment_id', 'razorpay_reference_id', 'razorpay_payment_status'])
            else:
                record.razorpay_payment_status = state
                record.save(update_fields=['razorpay_payment_status'])
    return True


def get_existing_payment_status(record):
    return {'success': True, 'paid': is_paid(record), 'status': 'PAID' if is_paid(record) else (record.razorpay_payment_status or 'CREATED').upper(), 'service': record.for_whys, 'financial_year': record.f_year, 'amount': int(record.amount or 0) * 100, 'currency': 'INR'}