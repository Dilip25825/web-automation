"""Read-only desktop-client licensing validation API."""

import json
import hmac
import hashlib
import re
import secrets
import time

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import PublicPacsErpRegistrationForm
from .models import ErpApiClientToken, UserInfoData, VersionInfo, tblPacsErp, tblUPI


ERP_REGISTRATION_SALT = 'licensing.erp-registration.v1'
ERP_REGISTRATION_MAX_AGE = 30 * 60


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


def _rate_limited(request, scope, identifier, limit):
    if limit <= 0:
        return False
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    client_ip = forwarded.split(',', 1)[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    bucket = int(time.time() // 60)
    cache_key = f'erp-api:{scope}:{client_ip}:{identifier}:{bucket}'
    if cache.add(cache_key, 1, timeout=70):
        return False
    try:
        return cache.incr(cache_key) > limit
    except ValueError:
        cache.set(cache_key, 1, timeout=70)
        return False


def _too_many_requests():
    response = JsonResponse(
        {
            'success': False,
            'authorized': False,
            'status': 'RATE_LIMITED',
            'message': 'Too many requests. Ek minute baad dobara try karein.',
        },
        status=429,
    )
    response['Retry-After'] = '60'
    return response

def _client_token_is_valid(request, operator_mobile):
    authorization = request.headers.get('Authorization', '').strip()
    if not authorization.lower().startswith('bearer '):
        return False
    raw_token = authorization[7:].strip()
    if len(raw_token) < 32:
        return False
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    credential = ErpApiClientToken.objects.filter(
        operator_mobile=operator_mobile,
        token_hash=token_hash,
        is_active=True,
    ).first()
    if not credential:
        return False
    if credential.expires_at and credential.expires_at <= timezone.now():
        return False
    credential.last_used_at = timezone.now()
    credential.save(update_fields=['last_used_at'])
    return True

def _operator_mobile(value):
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    return digits if len(digits) == 10 and digits[0] in "6789" else ""


def _erp_registration_url(request, operator_mobile):
    token = signing.dumps(
        {"operator_mobile": operator_mobile},
        salt=ERP_REGISTRATION_SALT,
        compress=True,
    )
    path = reverse("licensing:erp_self_register")
    return request.build_absolute_uri(f"{path}?token={token}")


def _erp_response(request, record, operator_mobile):
    today = timezone.localdate()
    expiry_date = record.expiry_date
    active = int(record.is_active or 0) == 1
    authorized = bool(active and expiry_date and expiry_date >= today and record.erp_id)
    current_amount = int(record.current_amount or 4500)
    payment_status = int(record.payment_status or 0)

    if authorized:
        status = "ACTIVE"
        message = "ERP subscription active hai."
    elif expiry_date and expiry_date < today:
        status = "EXPIRED"
        message = "ERP subscription expire ho chuki hai. Renewal required hai."
    elif payment_status < current_amount:
        status = "PAYMENT_REQUIRED"
        message = "ERP activation payment required hai."
    elif not active:
        status = "INACTIVE"
        message = "ERP record active nahi hai. Support se contact karein."
    else:
        status = "EXPIRY_NOT_SET"
        message = "ERP expiry date configured nahi hai. Support se contact karein."

    created_at = record.date_time
    if created_at and timezone.is_aware(created_at):
        created_at = timezone.localtime(created_at)
    registration_date = created_at.date().isoformat() if created_at else None

    return {
        "success": True,
        "authorized": authorized,
        "status": status,
        "message": message,
        "operator_mobile": operator_mobile,
        "record_id": record.pk,
        "erp_id": record.erp_id or "",
        "pacs_name": record.pacs_name or "",
        "registration_date": registration_date,
        "expiry_date": expiry_date.isoformat() if expiry_date else None,
        "server_date": today.isoformat(),
        "current_amount": current_amount,
        "payment_status": payment_status,
        "payment_create_url": request.build_absolute_uri(reverse("payments:erp_create")),
        "registration_url": None,
    }


@csrf_exempt
@require_POST
@never_cache
def register_erp_device(request):
    """Issue or rotate one device-bound ERP client token."""
    if _rate_limited(request, 'device-register-ip', '', 10):
        return _too_many_requests()

    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)

    operator_mobile = _operator_mobile(body.get('operator_mobile'))
    device_id = str(body.get('device_id') or '').strip()
    if not operator_mobile:
        return JsonResponse(
            {'success': False, 'status': 'INVALID_MOBILE', 'message': 'Valid 10 digit OperatorMobile required hai.'},
            status=400,
        )
    if len(device_id) < 8 or len(device_id) > 500:
        return JsonResponse(
            {'success': False, 'status': 'INVALID_DEVICE', 'message': 'Valid Windows device identity required hai.'},
            status=400,
        )
    if _rate_limited(request, 'device-register-mobile', operator_mobile, 5):
        return _too_many_requests()

    records = list(
        tblPacsErp.objects.filter(operator_mobile=int(operator_mobile))
        .exclude(erp_id__iendswith=' Expired')
        .order_by('-id')[:2]
    )
    if not records:
        return JsonResponse(
            {
                'success': True,
                'registered': False,
                'status': 'LICENSE_NOT_FOUND',
                'message': 'ERP record nahi mila. Pehle web registration complete karein.',
                'registration_url': _erp_registration_url(request, operator_mobile),
            }
        )
    if len(records) > 1:
        return JsonResponse(
            {
                'success': False,
                'registered': False,
                'status': 'MULTIPLE_ERP_RECORDS',
                'message': 'Is mobile par multiple current ERP records mile. Support se contact karein.',
            },
            status=409,
        )

    device_hash = hashlib.sha256(device_id.encode('utf-8')).hexdigest()
    credential = ErpApiClientToken.objects.filter(operator_mobile=operator_mobile).first()
    if credential and credential.device_hash and not hmac.compare_digest(credential.device_hash, device_hash):
        return JsonResponse(
            {
                'success': False,
                'registered': False,
                'status': 'DEVICE_ALREADY_REGISTERED',
                'message': 'Ye mobile kisi doosre device par registered hai. Admin se device reset karwayein.',
            },
            status=409,
        )
    if credential and not credential.device_hash:
        return JsonResponse(
            {
                'success': False,
                'registered': False,
                'status': 'MANUAL_TOKEN_EXISTS',
                'message': 'Is mobile ka purana manual token active hai. Admin se ek baar token record reset karwayein.',
            },
            status=409,
        )

    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    if credential:
        credential.token_hash = token_hash
        credential.token_prefix = raw_token[:12]
        credential.device_hash = device_hash
        credential.is_active = True
        credential.expires_at = None
        credential.save(update_fields=['token_hash', 'token_prefix', 'device_hash', 'is_active', 'expires_at', 'updated_at'])
    else:
        ErpApiClientToken.objects.create(
            operator_mobile=operator_mobile,
            token_hash=token_hash,
            token_prefix=raw_token[:12],
            device_hash=device_hash,
            is_active=True,
        )

    return JsonResponse(
        {
            'success': True,
            'registered': True,
            'status': 'DEVICE_REGISTERED',
            'operator_mobile': operator_mobile,
            'client_token': raw_token,
        }
    )

@csrf_exempt
@require_POST
@never_cache
def check_erp_subscription(request):
    """Validate one ERP desktop subscription using OperatorMobile only."""
    if _rate_limited(request, 'ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)

    if body is None:
        return JsonResponse(
            {"success": False, "authorized": False, "status": "INVALID_JSON"},
            status=400,
        )
    operator_mobile = _operator_mobile(body.get("operator_mobile"))
    if not operator_mobile:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "INVALID_MOBILE",
                "message": "Valid 10 digit Indian OperatorMobile required hai.",
            },
            status=400,
        )
    if _rate_limited(
        request,
        'mobile',
        operator_mobile,
        settings.ERP_API_MOBILE_RATE_LIMIT,
    ):
        return _too_many_requests()

    master_authenticated = _api_key_is_valid(request)
    client_authenticated = False
    if not master_authenticated:
        client_authenticated = _client_token_is_valid(request, operator_mobile)
    if not master_authenticated and not client_authenticated:
        return JsonResponse(
            {"success": False, "authorized": False, "status": "UNAUTHORIZED"},
            status=401,
        )

    records = list(
        tblPacsErp.objects.filter(operator_mobile=int(operator_mobile))
        .exclude(erp_id__iendswith=" Expired")
        .order_by("-id")[:2]
    )
    if not records:
        return JsonResponse(
            {
                "success": True,
                "authorized": False,
                "status": "LICENSE_NOT_FOUND",
                "message": "OperatorMobile ka ERP record nahi mila. Web page par registration karein.",
                "operator_mobile": operator_mobile,
                "registration_url": _erp_registration_url(request, operator_mobile),
            }
        )
    if len(records) > 1:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "MULTIPLE_ERP_RECORDS",
                "message": "Is OperatorMobile par multiple current ERP records mile. Support se contact karein.",
            },
            status=409,
        )

    record = records[0]
    if (
        int(record.is_active or 0) != 1
        and record.system_id == "Web registration"
        and record.expiry_date == timezone.localdate()
    ):
        record.is_active = 1
        record.save(update_fields=["is_active"])
    response_data = _erp_response(request, record, operator_mobile)
    if response_data["authorized"]:
        record.last_login = timezone.now()
        record.save(update_fields=["last_login"])
    return JsonResponse(response_data)


@require_http_methods(["GET", "POST"])
@never_cache
def erp_self_register(request):
    """Create an inactive ERP registration from a short-lived signed URL."""
    token = str(request.GET.get("token") or request.POST.get("token") or "").strip()
    try:
        payload = signing.loads(
            token,
            salt=ERP_REGISTRATION_SALT,
            max_age=ERP_REGISTRATION_MAX_AGE,
        )
        operator_mobile = _operator_mobile(payload.get("operator_mobile"))
        if not operator_mobile:
            raise signing.BadSignature
    except signing.SignatureExpired:
        return render(request, "licensing/erp_self_register.html", {"error": "Registration link expire ho gaya. Excel se dobara Login karein."}, status=410)
    except signing.BadSignature:
        return render(request, "licensing/erp_self_register.html", {"error": "Registration link valid nahi hai."}, status=400)

    if request.method == 'POST' and _rate_limited(request, 'register', operator_mobile, 10):
        return render(
            request,
            "licensing/erp_self_register.html",
            {"error": "Bahut zyada registration attempts hue. Ek minute baad try karein."},
            status=429,
        )

    current_records = tblPacsErp.objects.filter(operator_mobile=int(operator_mobile)).exclude(erp_id__iendswith=" Expired")
    if current_records.exists():
        return render(request, "licensing/erp_self_register.html", {"already_exists": True, "operator_mobile": operator_mobile})

    form = PublicPacsErpRegistrationForm(request.POST or None, initial={"operator_mobile": operator_mobile})
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["operator_mobile"] != operator_mobile:
            form.add_error("operator_mobile", "Signed OperatorMobile change nahi kiya ja sakta.")
        elif tblPacsErp.objects.filter(erp_id__iexact=form.cleaned_data["erp_id"]).exists():
            form.add_error("erp_id", "Ye ERP ID pehle se registered hai.")
        else:
            with transaction.atomic():
                if current_records.exists():
                    return render(request, "licensing/erp_self_register.html", {"already_exists": True, "operator_mobile": operator_mobile})
                record = tblPacsErp.objects.create(
                    erp_id=form.cleaned_data["erp_id"],
                    pacs_name=form.cleaned_data["pacs_name"],
                    brach=form.cleaned_data["brach"],
                    dist=form.cleaned_data["dist"],
                    state=form.cleaned_data["state"],
                    operator_mobile=int(operator_mobile),
                    amount=0,
                    current_amount=4500,
                    payment_status=0,
                    is_active=1,
                    expiry_date=timezone.localdate(),
                    system_id="Web registration",
                    remark="Trial active through registration date",
                )
            return render(request, "licensing/erp_self_register.html", {"created": True, "record": record})

    return render(request, "licensing/erp_self_register.html", {"form": form, "token": token, "operator_mobile": operator_mobile})

def _version_parts(value):
    parts = [int(item) for item in re.findall(r'\d+', str(value or ''))]
    return tuple(parts) if parts else (0,)


@csrf_exempt
@require_POST
@never_cache
def check_erp_version(request):
    if _rate_limited(request, 'version-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)

    operator_mobile = _operator_mobile(body.get('operator_mobile'))
    current_version = str(body.get('current_version') or '').strip()
    if not operator_mobile or not current_version:
        return JsonResponse(
            {
                'success': False,
                'status': 'INVALID_REQUEST',
                'message': 'OperatorMobile aur current version required hain.',
            },
            status=400,
        )
    if _rate_limited(request, 'version-mobile', operator_mobile, settings.ERP_API_MOBILE_RATE_LIMIT):
        return _too_many_requests()

    master_authenticated = _api_key_is_valid(request)
    client_authenticated = False
    if not master_authenticated:
        client_authenticated = _client_token_is_valid(request, operator_mobile)
    if not master_authenticated and not client_authenticated:
        return JsonResponse({'success': False, 'status': 'UNAUTHORIZED'}, status=401)

    version_record = VersionInfo.objects.filter(pk=4).first()
    if not version_record or not str(version_record.Version or '').strip():
        return JsonResponse(
            {
                'success': False,
                'status': 'VERSION_NOT_CONFIGURED',
                'message': 'Server par ERP version configured nahi hai.',
            },
            status=503,
        )

    latest_version = str(version_record.Version).strip()
    return JsonResponse(
        {
            'success': True,
            'status': 'UPDATE_AVAILABLE' if _version_parts(latest_version) > _version_parts(current_version) else 'UP_TO_DATE',
            'update_available': _version_parts(latest_version) > _version_parts(current_version),
            'current_version': current_version,
            'latest_version': latest_version,
            'description': version_record.Description or '',
            'year': version_record.Year or '',
            'remark': version_record.Remark or '',
        }
    )

@csrf_exempt
@require_POST
@never_cache
def get_erp_upi(request):
    """Return the currently active UPI ID to an authenticated ERP client."""
    if _rate_limited(request, 'upi-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()

    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)

    operator_mobile = _operator_mobile(body.get('operator_mobile'))
    if not operator_mobile:
        return JsonResponse(
            {
                'success': False,
                'status': 'INVALID_MOBILE',
                'message': 'Valid 10 digit Indian OperatorMobile required hai.',
            },
            status=400,
        )

    master_authenticated = _api_key_is_valid(request)
    client_authenticated = False
    if not master_authenticated:
        client_authenticated = _client_token_is_valid(request, operator_mobile)
    if not master_authenticated and not client_authenticated:
        return JsonResponse({'success': False, 'status': 'UNAUTHORIZED'}, status=401)

    upi_record = tblUPI.objects.filter(isActive=1).exclude(upiID__isnull=True).exclude(upiID='').order_by('-ID').first()
    if not upi_record:
        return JsonResponse(
            {
                'success': False,
                'status': 'UPI_NOT_CONFIGURED',
                'message': 'Server par active UPI ID configured nahi hai.',
            },
            status=503,
        )

    return JsonResponse(
        {
            'success': True,
            'status': 'OK',
            'upi_id': str(upi_record.upiID).strip(),
        }
    )

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
