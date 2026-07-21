import json

from django.db import transaction
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from licensing.models import UserInfoData

from .models import Coupon


def _error(message, code, status=400):
    return JsonResponse({'success': False, 'error': message, 'code': code}, status=status)


@require_GET
@ensure_csrf_cookie
def coupon_csrf(request):
    return JsonResponse({'success': True, 'csrf_token': get_token(request)})


@require_POST
def redeem_coupon(request):
    try:
        body = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error('Request body must be valid JSON.', 'INVALID_JSON')

    coupon_code = str(body.get('coupon_code') or '').strip().upper()
    user_id = str(body.get('user_id') or '').strip()
    service = str(body.get('service') or '').strip()
    financial_year = str(body.get('financial_year') or '').strip()
    if not coupon_code:
        return _error('Coupon code is required.', 'COUPON_REQUIRED')
    if not user_id.isdigit():
        return _error('Valid user ID is required.', 'INVALID_USER_ID')
    if not service or not financial_year:
        return _error('Service and financial year are required.', 'PAYMENT_RECORD_REQUIRED')

    with transaction.atomic():
        if Coupon.objects.select_for_update().filter(used_by=user_id).exists():
            return _error('This user has already used a coupon.', 'COUPON_ALREADY_USED_BY_USER', 409)
        try:
            coupon = Coupon.objects.select_for_update().get(coupon_code=coupon_code, status=True, used_by__isnull=True)
        except Coupon.DoesNotExist:
            return _error('Coupon is invalid, inactive or already used.', 'COUPON_NOT_AVAILABLE', 404)

        records = list(UserInfoData.objects.select_for_update().filter(
            mobile=int(user_id), for_whys__iexact=service, f_year__iexact=financial_year
        )[:2])
        if not records:
            return _error('Matching UserInfo payment record was not found.', 'USERINFO_RECORD_NOT_FOUND', 404)
        if len(records) > 1:
            return _error('Multiple matching UserInfo records were found.', 'DUPLICATE_USERINFO_RECORD', 409)
        record = records[0]
        if int(record.payment_status or 0) > 0 or record.razorpay_payment_link_id:
            return _error('Apply the coupon before starting payment.', 'PAYMENT_ALREADY_STARTED', 409)
        old_amount = int(record.amount or 0)
        discount = int(coupon.discount_amount or 0)
        if discount <= 0:
            return _error('Coupon discount amount is invalid.', 'INVALID_DISCOUNT', 409)
        if discount > old_amount:
            return _error('Coupon discount is greater than the payable amount.', 'DISCOUNT_EXCEEDS_AMOUNT', 409)

        record.amount = old_amount - discount
        record.save(update_fields=['amount'])
        coupon.used_by = user_id
        coupon.status = False
        coupon.save(update_fields=['used_by', 'status'])

    return JsonResponse({
        'success': True,
        'message': 'Coupon applied successfully.',
        'coupon_code': coupon.coupon_code,
        'discount_amount': discount,
        'old_amount': old_amount,
        'new_amount': record.amount,
        'user_id': user_id,
    })

