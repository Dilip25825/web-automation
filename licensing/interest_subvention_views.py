import json
import re
import time

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .models import Perpous, UserInfoData


PURPOSE = "INTEREST SUBVENTION"
TOKEN_SALT = "licensing.interest-subvention-session.v1"
TOKEN_MAX_AGE = 12 * 60 * 60


def _json_body(request):
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return body if isinstance(body, dict) else None


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _mobile(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 and digits[0] in "6789" else ""


def _rate_limited(request, scope, identifier, limit):
    if limit <= 0:
        return False
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    client_ip = (
        forwarded.split(",", 1)[0].strip()
        if forwarded
        else request.META.get("REMOTE_ADDR", "")
    )
    bucket = int(time.time() // 60)
    key = f"interest-api:{scope}:{client_ip}:{identifier}:{bucket}"
    if cache.add(key, 1, timeout=70):
        return False
    try:
        return cache.incr(key) > limit
    except ValueError:
        cache.set(key, 1, timeout=70)
        return False


def _rate_limit_response():
    response = JsonResponse(
        {
            "success": False,
            "authorized": False,
            "status": "RATE_LIMITED",
            "message": "Too many requests. Ek minute baad dobara try karein.",
        },
        status=429,
    )
    response["Retry-After"] = "60"
    return response


def _queryset(mobile, financial_year):
    return UserInfoData.objects.filter(
        mobile=int(mobile),
        for_whys__iexact=PURPOSE,
        f_year__iexact=financial_year.strip(),
    )


def _select_record(mobile, financial_year):
    queryset = _queryset(mobile, financial_year)
    active = list(queryset.filter(is_active=1).order_by("-id")[:2])
    if len(active) > 1:
        return None, True
    if active:
        return active[0], False
    return queryset.order_by("-id").first(), False


def _token(record):
    return signing.dumps(
        {
            "record_id": record.pk,
            "mobile": str(record.mobile),
            "pacs_name": record.pacs_name or "",
            "portal_user_id": record.pacs_name or "",
            "financial_year": record.f_year or "",
            "service": PURPOSE,
        },
        salt=TOKEN_SALT,
        compress=True,
    )


def _record_from_token(raw_token):
    try:
        data = signing.loads(raw_token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
        mobile = _mobile(data.get("mobile"))
        pacs_name = str(data.get("pacs_name") or "").strip()
        financial_year = str(data.get("financial_year") or "").strip()
        record_id = _integer(data.get("record_id"))
        service = str(data.get("service") or "").strip()
    except signing.SignatureExpired:
        return None, JsonResponse(
            {"success": False, "status": "TOKEN_EXPIRED", "message": "Software session expire ho gaya."},
            status=401,
        )
    except signing.BadSignature:
        return None, JsonResponse(
            {"success": False, "status": "INVALID_TOKEN", "message": "Software login token valid nahi hai."},
            status=401,
        )
    if not mobile or not pacs_name or not financial_year or record_id <= 0 or service != PURPOSE:
        return None, JsonResponse({"success": False, "status": "INVALID_REQUEST"}, status=400)
    record = _queryset(mobile, financial_year).filter(pk=record_id, pacs_name__iexact=pacs_name).first()
    if not record:
        return None, JsonResponse({"success": False, "status": "LICENSE_NOT_FOUND"}, status=404)
    return record, None


@csrf_exempt
@require_POST
@never_cache
def options(request):
    if _rate_limited(request, "options-ip", "", settings.ERP_API_IP_RATE_LIMIT):
        return _rate_limit_response()
    years = list(
        Perpous.objects.filter(forWhy__iexact=PURPOSE)
        .exclude(fyear__isnull=True)
        .exclude(fyear="")
        .order_by("-fyear")
        .values_list("fyear", flat=True)
        .distinct()
    )
    return JsonResponse(
        {
            "success": True,
            "status": "OK",
            "for_whys": PURPOSE,
            "financial_years": [
                str(year).strip() for year in years if str(year).strip()
            ],
        }
    )

@csrf_exempt
@require_POST
@never_cache
def subscription(request):
    if _rate_limited(request, "login-ip", "", settings.ERP_API_IP_RATE_LIMIT):
        return _rate_limit_response()
    body = _json_body(request)
    if body is None:
        return JsonResponse(
            {"success": False, "authorized": False, "status": "INVALID_JSON"}, status=400
        )

    mobile = _mobile(body.get("mobile") or body.get("user_id"))
    financial_year = str(body.get("financial_year") or body.get("fYear") or "").strip()
    service = str(body.get("service") or body.get("for_whys") or body.get("forWhys") or "").strip()
    if not mobile or not financial_year or service.upper() != PURPOSE:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "INVALID_REQUEST",
                "message": "Valid mobile, service aur financial year bhejein.",
            },
            status=400,
        )
    if _rate_limited(request, "login-mobile", mobile, settings.ERP_API_MOBILE_RATE_LIMIT):
        return _rate_limit_response()

    record, multiple = _select_record(mobile, financial_year)
    if multiple:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "MULTIPLE_ACTIVE_RECORDS",
                "message": "Matching details ke multiple active records mile.",
            },
            status=409,
        )
    if not record:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "LICENSE_NOT_FOUND",
                "message": "Mobile, service aur financial year ka matching license nahi mila.",
            },
            status=404,
        )
    if _integer(record.is_active) != 1:
        return JsonResponse(
            {"success": False, "authorized": False, "status": "INACTIVE", "message": "Software license active nahi hai."},
            status=403,
        )

    amount = _integer(record.amount)
    payment_status = _integer(record.payment_status)
    paid = amount > 0 and payment_status == amount
    entry_count = max(0, _integer(record.entry_count))
    entry_limit = max(0, _integer(getattr(record, "limit_of_entrys", 20), 20))
    remaining_entries = max(0, entry_limit - entry_count)

    return JsonResponse(
        {
            "success": True,
            "authorized": True,
            "status": "ACTIVE",
            "message": (
                "Software login verification successful."
                if paid or remaining_entries > 0
                else "Login successful, lekin free entry limit poori ho chuki hai."
            ),
            "record_id": record.pk,
            "mobile": str(record.mobile),
            "pacs_name": record.pacs_name or "",
            "portal_user_id": record.pacs_name or "",
            "for_whys": PURPOSE,
            "financial_year": record.f_year or financial_year,
            "access_type": "PAID" if paid else "FREE_TRIAL",
            "entry_limit": entry_limit,
            "entry_count": entry_count,
            "remaining_entries": remaining_entries,
            "record_token": _token(record),
        }
    )


@csrf_exempt
@require_POST
@never_cache
def consume_entries(request):
    if _rate_limited(request, "consume-ip", "", settings.ERP_API_IP_RATE_LIMIT):
        return _rate_limit_response()
    body = _json_body(request)
    if body is None:
        return JsonResponse({"success": False, "status": "INVALID_JSON"}, status=400)
    uploaded_count = _integer(body.get("uploaded_count"))
    if uploaded_count <= 0:
        return JsonResponse({"success": False, "status": "INVALID_REQUEST"}, status=400)

    record, error = _record_from_token(str(body.get("record_token") or "").strip())
    if error:
        return error
    with transaction.atomic():
        locked = UserInfoData.objects.select_for_update().filter(pk=record.pk).first()
        if not locked:
            return JsonResponse({"success": False, "status": "LICENSE_NOT_FOUND"}, status=404)
        amount = _integer(locked.amount)
        if _integer(locked.is_active) != 1:
            return JsonResponse({"success": False, "status": "INACTIVE"}, status=403)
        paid = amount > 0 and _integer(locked.payment_status) == amount
        entry_count = max(0, _integer(locked.entry_count))
        entry_limit = max(0, _integer(getattr(locked, "limit_of_entrys", 20), 20))
        new_count = entry_count + uploaded_count
        if not paid and new_count > entry_limit:
            return JsonResponse(
                {
                    "success": False,
                    "status": "ENTRY_LIMIT_EXCEEDED",
                    "message": "Free entry limit poori ho chuki hai.",
                },
                status=409,
            )
        locked.entry_count = new_count
        locked.save(update_fields=["entry_count"])
    return JsonResponse(
        {
            "success": True,
            "status": "UPLOAD_RECORDED",
            "entry_count": new_count,
            "entry_limit": entry_limit,
            "remaining_entries": max(0, entry_limit - new_count),
            "access_type": "PAID" if paid else "FREE_TRIAL",
        }
    )