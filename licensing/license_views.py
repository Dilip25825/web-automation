"""Read-only desktop-client licensing validation API."""

import json
import hmac

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import UserInfoData


def _json_body(request):
    try:
        value = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _api_key_is_valid(request):
    expected = settings.LICENSE_VALIDATION_API_KEY
    supplied = request.headers.get("X-License-API-Key", "").strip()
    return bool(expected and supplied and hmac.compare_digest(supplied, expected))


@csrf_exempt
@require_POST
def check_activation(request):
    """Check the exact zero-payment activation condition for external software."""
    if not settings.LICENSE_VALIDATION_API_KEY:
        return JsonResponse(
            {"success": False, "activated": False, "status": "API_NOT_CONFIGURED"},
            status=503,
        )
    if not _api_key_is_valid(request):
        return JsonResponse(
            {"success": False, "activated": False, "status": "UNAUTHORIZED"},
            status=401,
        )

    body = _json_body(request)
    if body is None:
        return JsonResponse(
            {"success": False, "activated": False, "status": "INVALID_JSON"},
            status=400,
        )

    user_id = str(body.get("user_id") or "").strip()
    service = str(body.get("forWhys") or body.get("service") or "").strip()
    financial_year = str(body.get("fYear") or body.get("financial_year") or "").strip()
    amount = _integer(body.get("Amount"), default=None)
    payment_status = _integer(body.get("PaymentStatus"), default=None)
    is_active = _integer(body.get("isActive"), default=None)
    if (
        not user_id.isdigit()
        or not service
        or not financial_year
        or amount is None
        or payment_status is None
        or is_active is None
    ):
        return JsonResponse(
            {"success": False, "activated": False, "status": "INVALID_REQUEST"},
            status=400,
        )

    records = list(
        UserInfoData.objects.filter(
            mobile=int(user_id),
            for_whys__iexact=service,
            f_year__iexact=financial_year,
        )[:2]
    )
    if not records:
        return JsonResponse(
            {"success": True, "activated": False, "status": "LICENSE_NOT_FOUND"}
        )
    if len(records) > 1:
        return JsonResponse(
            {"success": False, "activated": False, "status": "DUPLICATE_LICENSE"},
            status=409,
        )

    record = records[0]
    database_amount = _integer(record.amount)
    database_payment_status = _integer(record.payment_status)
    database_is_active = _integer(record.is_active)
    values_match = (
        database_amount == amount
        and database_payment_status == payment_status
        and database_is_active == is_active
    )
    activated = values_match and amount == 0 and payment_status == 0 and is_active == 1
    return JsonResponse(
        {
            "success": True,
            "activated": activated,
            "authorized": activated,
            "status": "ACTIVE" if activated else "CONDITION_NOT_MATCHED",
            "user_id": user_id,
            "forWhys": record.for_whys or service,
            "fYear": record.f_year or financial_year,
            "Amount": database_amount,
            "PaymentStatus": database_payment_status,
            "isActive": database_is_active,
        }
    )

@require_POST
def validate_license(request):
    """Validate a paid or explicitly enabled complimentary UserInfo row."""
    body = _json_body(request)
    if body is None:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "INVALID_JSON",
                "message": "Request body valid JSON honi chahiye.",
            },
            status=400,
        )

    user_id = str(body.get("user_id") or "").strip()
    service = str(body.get("service") or "").strip()
    financial_year = str(body.get("financial_year") or "").strip()
    if not user_id.isdigit() or not service or not financial_year:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "INVALID_REQUEST",
                "message": "Valid User ID, Service aur Year/Season required hai.",
            },
            status=400,
        )

    records = list(
        UserInfoData.objects.filter(
            mobile=int(user_id),
            for_whys__iexact=service,
            f_year__iexact=financial_year,
        )[:2]
    )
    if not records:
        return JsonResponse(
            {
                "success": True,
                "authorized": False,
                "status": "LICENSE_NOT_FOUND",
                "message": "Selected service aur year/season ka license record nahi mila.",
            }
        )
    if len(records) > 1:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "DUPLICATE_LICENSE",
                "message": "Multiple matching license records mile. Support se contact karein.",
            },
            status=409,
        )

    record = records[0]
    amount = _integer(record.amount)
    payment_status = _integer(record.payment_status)
    entry_limit = _integer(record.limit_of_entrys)
    active = _integer(record.is_active) == 1
    paid = amount > 0 and payment_status == amount
    complimentary = amount == 0 and entry_limit > 0
    authorized = active and (paid or complimentary)

    if authorized:
        status = "ACTIVE"
        message = "License active hai."
    elif not active:
        status = "INACTIVE"
        message = "License active nahi hai."
    elif amount > 0:
        status = "PAYMENT_REQUIRED"
        message = "Activation payment complete nahi hai."
    else:
        status = "ENTRY_LIMIT_REQUIRED"
        message = "Complimentary license ke liye entry limit configured nahi hai."

    return JsonResponse(
        {
            "success": True,
            "authorized": authorized,
            "status": status,
            "activation_type": (
                "PAID" if authorized and paid
                else "FREE" if authorized and complimentary
                else None
            ),
            "user_id": user_id,
            "service": record.for_whys or service,
            "financial_year": record.f_year or financial_year,
            "pacs_name": record.pacs_name or "",
            "entry_limit": entry_limit,
            "amount": amount,
            "payment_status": payment_status,
            "message": message,
        }
    )
