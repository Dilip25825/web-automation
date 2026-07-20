import hmac
import json

from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from .models import UserInfoData
from .payment_services import (PaymentError, create_razorpay_payment_link, find_payment_record, get_existing_payment_status, process_payment_link_paid, process_payment_link_state, record_from_token, verify_razorpay_webhook_signature)


def _error(error):
    return JsonResponse({'success': False, 'error': str(error), 'code': error.code}, status=error.http_status)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PaymentError('Request body must be valid JSON.', 'INVALID_JSON') from exc


def authenticate_license(request, expected_user_id=None):
    user_id = request.headers.get('X-User-ID', '').strip()
    authorization = request.headers.get('Authorization', '')
    prefix = 'License '
    if not user_id or not authorization.startswith(prefix) or not user_id.isdigit():
        raise PaymentError('Valid licensing authentication is required.', 'UNAUTHORIZED', 401)
    supplied = authorization[len(prefix):].strip()
    passwords = UserInfoData.objects.filter(mobile=int(user_id)).exclude(u_pass__isnull=True).values_list('u_pass', flat=True)
    if not supplied or not any(hmac.compare_digest(str(password), supplied) for password in passwords):
        raise PaymentError('Valid licensing authentication is required.', 'UNAUTHORIZED', 401)
    if expected_user_id is not None and str(expected_user_id) != user_id:
        raise PaymentError('Authenticated user does not match request user.', 'USER_MISMATCH', 403)
    return user_id


@require_GET
@ensure_csrf_cookie
def payment_csrf(request):
    return JsonResponse({'success': True, 'csrf_token': get_token(request)})


@require_POST
def payment_create(request):
    try:
        body = _json_body(request)
        user_id = str(body.get('user_id') or '').strip()
        service = str(body.get('service') or '').strip()
        financial_year = str(body.get('financial_year') or '').strip()
        if not user_id:
            raise PaymentError('User ID is required.', 'INVALID_USER_ID')
        if not service:
            raise PaymentError('Service is required.', 'INVALID_SERVICE')
        if not financial_year:
            raise PaymentError('Financial year is required.', 'INVALID_FINANCIAL_YEAR')
        record = find_payment_record(user_id, service, financial_year)
        return JsonResponse(create_razorpay_payment_link(record.pk))
    except PaymentError as error:
        return _error(error)


@require_GET
def payment_status(request):
    try:
        user_id = authenticate_license(request)
        token = request.GET.get('token', '').strip()
        if not token:
            raise PaymentError('Payment token is required.', 'TOKEN_REQUIRED')
        return JsonResponse(get_existing_payment_status(record_from_token(token, user_id)))
    except PaymentError as error:
        return _error(error)


@csrf_exempt
@require_POST
def razorpay_webhook(request):
    signature = request.headers.get('X-Razorpay-Signature', '')
    try:
        if not verify_razorpay_webhook_signature(request.body, signature):
            raise PaymentError('Invalid webhook signature.', 'INVALID_WEBHOOK_SIGNATURE', 401)
        payload = _json_body(request)
        event = payload.get('event')
        link = ((payload.get('payload') or {}).get('payment_link') or {}).get('entity') or {}
        if event == 'payment_link.paid':
            payment = ((payload.get('payload') or {}).get('payment') or {}).get('entity') or {}
            result = process_payment_link_paid(link, payment)
            return JsonResponse({'success': True, 'processed': True, **result})
        if event in {'payment_link.expired', 'payment_link.cancelled'}:
            process_payment_link_state(link, event.rsplit('.', 1)[-1])
        return JsonResponse({'success': True, 'processed': False})
    except PaymentError as error:
        return _error(error)