"""Read-only desktop-client licensing validation API."""

import json
import hmac
import hashlib
import re
import secrets
import time
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .forms import PublicFasalRinRegistrationForm, PublicPacsErpRegistrationForm, PublicPmfbyRegistrationForm
from .models import ErpApiClientToken, Perpous, UserInfoData, VersionInfo, tblPacsErp, tblUPI
from .utils import generate_erp_invoice_pdf


ERP_REGISTRATION_SALT = 'licensing.erp-registration.v1'
ERP_REGISTRATION_MAX_AGE = 30 * 60
ERP_INVOICE_SALT = 'licensing.erp-invoice.v1'
ERP_INVOICE_MAX_AGE = 10 * 60


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


def _select_erp_record(operator_mobile):
    """Prefer one active/unexpired row; otherwise return latest renewal row."""
    today = timezone.localdate()
    base_queryset = (
        tblPacsErp.objects.filter(operator_mobile=int(operator_mobile))
        .exclude(erp_id__iendswith=' Expired')
    )
    active_records = list(
        base_queryset.filter(is_active=1, expiry_date__gte=today)
        .order_by('-id')[:2]
    )
    if len(active_records) > 1:
        return None, True
    if active_records:
        return active_records[0], False

    fallback_records = list(base_queryset.order_by('-id')[:1])
    return (fallback_records[0] if fallback_records else None), False

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

    record, multiple_active = _select_erp_record(operator_mobile)
    if not record and not multiple_active:
        return JsonResponse(
            {
                'success': True,
                'registered': False,
                'status': 'LICENSE_NOT_FOUND',
                'message': 'ERP record nahi mila. Pehle web registration complete karein.',
                'registration_url': _erp_registration_url(request, operator_mobile),
            }
        )
    if multiple_active:
        return JsonResponse(
            {
                'success': False,
                'registered': False,
                'status': 'MULTIPLE_ACTIVE_RECORDS',
                'message': 'Is mobile par multiple active aur valid ERP records mile. Support se contact karein.',
            },
            status=409,
        )

    device_hash = hashlib.sha256(device_id.encode('utf-8')).hexdigest()
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    credential, created = ErpApiClientToken.objects.update_or_create(
        operator_mobile=operator_mobile,
        device_hash=device_hash,
        defaults={
            'token_hash': token_hash,
            'token_prefix': raw_token[:12],
            'is_active': True,
            'expires_at': None,
            'last_used_at': None,
        },
    )

    return JsonResponse(
        {
            'success': True,
            'registered': True,
            'status': 'DEVICE_REGISTERED',
            'operator_mobile': operator_mobile,
            'client_token': raw_token,
            'new_device': created,
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

    record, multiple_active = _select_erp_record(operator_mobile)
    if not record and not multiple_active:
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
    if multiple_active:
        return JsonResponse(
            {
                "success": False,
                "authorized": False,
                "status": "MULTIPLE_ACTIVE_RECORDS",
                "message": "Is OperatorMobile par multiple active aur valid ERP records mile. Support se contact karein.",
            },
            status=409,
        )

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
                'message': 'Payment service abhi uplabdh nahi hai. Kripya support se sampark karein.',
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
@never_cache
def create_erp_invoice(request):
    """Create a short-lived invoice URL without exposing the stored ERP price."""
    if _rate_limited(request, 'invoice-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()

    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)

    operator_mobile = _operator_mobile(body.get('operator_mobile'))
    erp_id = str(body.get('erp_id') or '').strip()
    if not operator_mobile or not erp_id or len(erp_id) > 255:
        return JsonResponse(
            {'success': False, 'status': 'INVALID_REQUEST', 'message': 'Valid Operator Mobile aur ERP ID required hain.'},
            status=400,
        )

    try:
        invoice_amount = Decimal(str(body.get('amount') or '').strip())
    except (InvalidOperation, TypeError, ValueError):
        invoice_amount = Decimal('0')
    if not invoice_amount.is_finite() or invoice_amount <= 0 or invoice_amount > Decimal('1000000') or invoice_amount.as_tuple().exponent < -2:
        return JsonResponse(
            {'success': False, 'status': 'INVALID_AMOUNT', 'message': 'Invoice amount 0 se zyada aur maximum 10,00,000 hona chahiye.'},
            status=400,
        )

    if not (_api_key_is_valid(request) or _client_token_is_valid(request, operator_mobile)):
        return JsonResponse({'success': False, 'status': 'UNAUTHORIZED'}, status=401)

    record = (
        tblPacsErp.objects.filter(erp_id__iexact=erp_id)
        .exclude(erp_id__iendswith=' Expired')
        .order_by('-is_active', '-expiry_date', '-id')
        .first()
    )
    if not record:
        return JsonResponse(
            {'success': False, 'status': 'ERP_NOT_FOUND', 'message': 'Di gayi ERP ID ka record nahi mila.'},
            status=404,
        )
    stored_amount = int(record.amount or 0)
    payment_status = int(record.payment_status or 0)
    if stored_amount <= 0 or stored_amount != payment_status:
        return JsonResponse(
            {
                'success': False,
                'status': 'PAYMENT_REQUIRED',
                'message': 'Invoice sirf complete payment wale ERP record ke liye ban sakta hai.',
            },
            status=403,
        )

    token = signing.dumps(
        {'record_id': record.pk, 'amount': format(invoice_amount, '.2f')},
        salt=ERP_INVOICE_SALT,
        compress=True,
    )
    invoice_path = reverse('licensing:erp_online_invoice', kwargs={'token': token})
    return JsonResponse(
        {'success': True, 'status': 'INVOICE_READY', 'invoice_url': request.build_absolute_uri(invoice_path)}
    )


@require_http_methods(['GET'])
@never_cache
def erp_online_invoice(request, token):
    try:
        payload = signing.loads(token, salt=ERP_INVOICE_SALT, max_age=ERP_INVOICE_MAX_AGE)
        record_id = int(payload.get('record_id'))
        invoice_amount = Decimal(str(payload.get('amount')))
        if not invoice_amount.is_finite() or invoice_amount <= 0 or invoice_amount > Decimal('1000000'):
            raise signing.BadSignature
    except signing.SignatureExpired:
        return JsonResponse(
            {'success': False, 'status': 'INVOICE_LINK_EXPIRED', 'message': 'Invoice link expire ho gaya. Excel se naya invoice banayein.'},
            status=410,
        )
    except (signing.BadSignature, InvalidOperation, TypeError, ValueError):
        return JsonResponse({'success': False, 'status': 'INVALID_INVOICE_LINK'}, status=400)

    record = tblPacsErp.objects.filter(pk=record_id).first()
    if not record:
        return JsonResponse({'success': False, 'status': 'ERP_NOT_FOUND'}, status=404)
    stored_amount = int(record.amount or 0)
    payment_status = int(record.payment_status or 0)
    if stored_amount <= 0 or stored_amount != payment_status:
        return JsonResponse(
            {'success': False, 'status': 'PAYMENT_REQUIRED', 'message': 'Is ERP record ka complete payment nahi mila.'},
            status=403,
        )
    pdf_buffer = generate_erp_invoice_pdf(request, record, invoice_amount=invoice_amount)
    return FileResponse(pdf_buffer, as_attachment=False, content_type='application/pdf')

PMFBY_PURPOSE = 'PMFBY'
OPTOUT_FORM_PURPOSE = 'OptedOutForm'
PMFBY_ALLOWED_SERVICES = {
    PMFBY_PURPOSE.upper(): PMFBY_PURPOSE,
    OPTOUT_FORM_PURPOSE.upper(): OPTOUT_FORM_PURPOSE,
}
PMFBY_DEFAULT_AMOUNT = 2500
OPTOUT_FORM_DEFAULT_AMOUNT = 1000
PMFBY_ENTRY_LIMIT = 10
PMFBY_TOKEN_SALT = 'licensing.pmfby-session.v1'
PMFBY_TOKEN_MAX_AGE = 12 * 60 * 60


def _pmfby_service(value=None):
    """Keep old clients on PMFBY while allowing the approved OptedOutForm service."""
    normalized = str(value or PMFBY_PURPOSE).strip().upper()
    return PMFBY_ALLOWED_SERVICES.get(normalized, '')


def _pmfby_default_amount(service):
    if service == OPTOUT_FORM_PURPOSE:
        return OPTOUT_FORM_DEFAULT_AMOUNT
    return PMFBY_DEFAULT_AMOUNT


def _pmfby_queryset(mobile, financial_year, service=PMFBY_PURPOSE):
    return UserInfoData.objects.filter(
        mobile=int(mobile),
        for_whys__iexact=service,
        f_year__iexact=financial_year.strip(),
    )


def _select_pmfby_record(mobile, financial_year, service=PMFBY_PURPOSE):
    service_queryset = _pmfby_queryset(mobile, financial_year, service)
    active_records = list(service_queryset.filter(is_active=1).order_by('-id')[:2])
    if len(active_records) > 1:
        return None, True
    if active_records:
        return active_records[0], False
    return service_queryset.order_by('-id').first(), False


def _pmfby_request_identity(body):
    mobile = _operator_mobile(body.get('mobile') or body.get('user_id'))
    financial_year = str(body.get('financial_year') or body.get('fYear') or '').strip()
    service = _pmfby_service(body.get('service') or body.get('for_whys') or body.get('forWhys'))
    return mobile, financial_year, service


def _pmfby_years(service=PMFBY_PURPOSE):
    values = list(
        Perpous.objects.filter(forWhy__iexact=service)
        .exclude(fyear__isnull=True)
        .exclude(fyear='')
        .order_by('-fyear')
        .values_list('fyear', flat=True)
        .distinct()
    )
    if not values and service == OPTOUT_FORM_PURPOSE:
        values = list(
            Perpous.objects.filter(forWhy__iexact=PMFBY_PURPOSE)
            .exclude(fyear__isnull=True)
            .exclude(fyear='')
            .order_by('-fyear')
            .values_list('fyear', flat=True)
            .distinct()
        )
    return [str(year).strip() for year in values if str(year).strip()]


def _pmfby_registration_url(request, mobile, service=PMFBY_PURPOSE):
    token = signing.dumps({'mobile': mobile, 'service': service}, salt=PMFBY_TOKEN_SALT, compress=True)
    return request.build_absolute_uri(f"{reverse('licensing:pmfby_self_register')}?token={token}")


def _pmfby_registration_initial(mobile, service=PMFBY_PURPOSE):
    initial = {'mobile': mobile, 'operator_mobile': mobile, 'service': service}
    previous = UserInfoData.objects.filter(mobile=int(mobile)).order_by('-id').first()
    if not previous:
        return initial
    for field_name in ('pacs_name', 'brach', 'dist', 'state'):
        value = str(getattr(previous, field_name, '') or '').strip()
        if value:
            initial[field_name] = value
    operator_mobile = _operator_mobile(getattr(previous, 'operator_mobile', None))
    if operator_mobile:
        initial['operator_mobile'] = operator_mobile
    return initial


def _pmfby_session_token(record, service=None):
    service = _pmfby_service(service or record.for_whys)
    return signing.dumps(
        {
            'record_id': record.pk,
            'mobile': str(record.mobile),
            'financial_year': record.f_year,
            'service': service,
        },
        salt=PMFBY_TOKEN_SALT,
        compress=True,
    )


def _pmfby_entry_limit(record):
    configured_limit = getattr(record, 'limit_of_entrys', None)
    if configured_limit is None:
        return PMFBY_ENTRY_LIMIT
    return max(0, _integer(configured_limit))


@csrf_exempt
@require_POST
@never_cache
def pmfby_options(request):
    if _rate_limited(request, 'pmfby-options', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    service = _pmfby_service(body.get('service') or body.get('for_whys') or body.get('forWhys'))
    if not service:
        return JsonResponse({'success': False, 'status': 'INVALID_SERVICE', 'message': 'Selected service valid nahi hai.'}, status=400)
    return JsonResponse({
        'success': True,
        'status': 'OK',
        'app_code': 'PMFBY',
        'for_whys': service,
        'financial_years': _pmfby_years(service),
    })


@csrf_exempt
@require_POST
@never_cache
def pmfby_subscription(request):
    if _rate_limited(request, 'pmfby-login-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'authorized': False, 'status': 'INVALID_JSON'}, status=400)
    mobile, financial_year, service = _pmfby_request_identity(body)
    if not mobile or not financial_year:
        return JsonResponse({'success': False, 'authorized': False, 'status': 'INVALID_REQUEST', 'message': 'Kripya valid 10 digit mobile number aur sahi season/year select karein.'}, status=400)
    if not service:
        return JsonResponse({'success': False, 'authorized': False, 'status': 'INVALID_SERVICE', 'message': 'Selected service valid nahi hai.'}, status=400)
    if _rate_limited(request, 'pmfby-login-mobile', mobile, settings.ERP_API_MOBILE_RATE_LIMIT):
        return _too_many_requests()
    record, multiple_active = _select_pmfby_record(mobile, financial_year, service)
    if multiple_active:
        return JsonResponse({'success': False, 'authorized': False, 'status': 'MULTIPLE_ACTIVE_RECORDS', 'message': 'Is mobile, service aur season ke liye ek se adhik active accounts mile hain. Kripya support se sampark karein.'}, status=409)
    if not record:
        return JsonResponse({
            'success': True,
            'authorized': False,
            'status': 'LICENSE_NOT_FOUND',
            'message': 'Is mobile, service aur season ka account abhi bana nahi hai. Kripya registration complete karein.',
            'registration_url': _pmfby_registration_url(request, mobile, service),
        })

    authorized = _integer(record.is_active) == 1
    if authorized:
        status, message = 'ACTIVE', 'Login verification successful.'
    else:
        status, message = 'INACTIVE', 'Aapka account abhi active nahi hai. Kripya support se sampark karein.'

    return JsonResponse({
        'success': True, 'authorized': authorized, 'status': status, 'message': message,
        'record_id': record.pk, 'mobile': str(record.mobile or mobile), 'pacs_name': record.pacs_name or '',
        'for_whys': service, 'financial_year': record.f_year or financial_year,
        'record_token': _pmfby_session_token(record, service) if authorized else '',
    })


def _pmfby_record_from_token(record_token, lock=False):
    try:
        token_data = signing.loads(record_token, salt=PMFBY_TOKEN_SALT, max_age=PMFBY_TOKEN_MAX_AGE)
        mobile = _operator_mobile(token_data.get('mobile'))
        financial_year = str(token_data.get('financial_year') or '').strip()
        service = _pmfby_service(token_data.get('service'))
        record_id = _integer(token_data.get('record_id'))
    except signing.SignatureExpired:
        return None, JsonResponse({'success': False, 'status': 'TOKEN_EXPIRED', 'message': 'Aapka login session samapt ho gaya hai. Kripya dobara login karein.'}, status=401)
    except signing.BadSignature:
        return None, JsonResponse({'success': False, 'status': 'INVALID_TOKEN', 'message': 'Login verification nahi ho saki. Kripya dobara login karein.'}, status=401)
    if not mobile or not financial_year or not service or record_id <= 0:
        return None, JsonResponse({'success': False, 'status': 'INVALID_REQUEST'}, status=400)
    queryset = _pmfby_queryset(mobile, financial_year, service)
    if lock:
        queryset = queryset.select_for_update()
    record = queryset.filter(pk=record_id).first()
    if not record:
        return None, JsonResponse({'success': False, 'status': 'LICENSE_NOT_FOUND'}, status=404)
    return record, None


@csrf_exempt
@require_POST
@never_cache
def check_pmfby_entry(request):
    if _rate_limited(request, 'pmfby-entry-check-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'allowed': False, 'status': 'INVALID_JSON'}, status=400)
    record, error_response = _pmfby_record_from_token(str(body.get('record_token') or '').strip())
    if error_response:
        return error_response
    if _integer(record.is_active) != 1:
        return JsonResponse({'success': True, 'allowed': False, 'status': 'LICENSE_NOT_ACTIVE', 'message': 'Aapka account abhi active nahi hai. Kripya support se sampark karein.'})
    paid = _integer(record.amount) > 0 and _integer(record.payment_status) == _integer(record.amount)
    entry_count = max(0, _integer(record.entry_count))
    entry_limit = _pmfby_entry_limit(record)
    allowed = paid or entry_count < entry_limit
    if paid:
        message = 'Aapka payment complete hai. Upload shuru kiya ja sakta hai.'
    elif allowed:
        message = 'Aap free upload suvidha ka upyog kar rahe hain.'
    else:
        message = f'Aapne {entry_count} free entries successfully upload kar li hain. Aage upload karne ke liye payment karna hoga.'
    return JsonResponse({
        'success': True,
        'allowed': allowed,
        'status': 'ENTRY_ALLOWED' if allowed else 'ENTRY_LIMIT_REACHED',
        'message': message,
        'access_type': 'PAID' if paid else 'FREE_TRIAL',
    })


@csrf_exempt
@require_POST
@never_cache
def get_pmfby_upi(request):
    if _rate_limited(request, 'pmfby-upi-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    record, error_response = _pmfby_record_from_token(str(body.get('record_token') or '').strip())
    if error_response:
        return error_response
    if _integer(record.is_active) != 1:
        return JsonResponse({'success': False, 'status': 'LICENSE_NOT_ACTIVE'}, status=403)
    upi_record = tblUPI.objects.filter(isActive=1).exclude(upiID__isnull=True).exclude(upiID='').order_by('-ID').first()
    if not upi_record:
        return JsonResponse({'success': False, 'status': 'UPI_NOT_CONFIGURED', 'message': 'Payment service abhi uplabdh nahi hai. Kripya support se sampark karein.'}, status=503)
    return JsonResponse({'success': True, 'status': 'OK', 'upi_id': str(upi_record.upiID).strip()})


@csrf_exempt
@require_POST
@never_cache
def consume_pmfby_entries(request):
    if _rate_limited(request, 'pmfby-consume-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    record_token = str(body.get('record_token') or '').strip()
    uploaded_count = _integer(body.get('uploaded_count'), default=0)
    if uploaded_count <= 0:
        return JsonResponse({'success': False, 'status': 'INVALID_REQUEST'}, status=400)
    session_record, error_response = _pmfby_record_from_token(record_token)
    if error_response:
        return error_response

    with transaction.atomic():
        record = UserInfoData.objects.select_for_update().filter(pk=session_record.pk).first()
        if not record:
            return JsonResponse({'success': False, 'status': 'LICENSE_NOT_FOUND'}, status=404)
        if _integer(record.is_active) != 1:
            return JsonResponse({'success': False, 'status': 'LICENSE_NOT_ACTIVE'}, status=403)
        new_count = max(0, _integer(record.entry_count)) + uploaded_count
        paid = _integer(record.amount) > 0 and _integer(record.payment_status) == _integer(record.amount)
        entry_limit = _pmfby_entry_limit(record)
        if not paid and new_count > entry_limit:
            return JsonResponse({'success': False, 'status': 'ENTRY_LIMIT_EXCEEDED', 'message': 'Aapki free upload suvidha poori ho chuki hai. Aage upload karne ke liye payment karein.'}, status=409)
        record.entry_count = new_count
        record.save(update_fields=['entry_count'])
    return JsonResponse({'success': True, 'status': 'UPLOAD_RECORDED'})


@require_http_methods(['GET', 'POST'])
@never_cache
def pmfby_self_register(request):
    token = str(request.GET.get('token') or request.POST.get('token') or '').strip()
    try:
        payload = signing.loads(token, salt=PMFBY_TOKEN_SALT, max_age=PMFBY_TOKEN_MAX_AGE)
        mobile = _operator_mobile(payload.get('mobile'))
        service = _pmfby_service(payload.get('service'))
        if not mobile or not service:
            raise signing.BadSignature
    except signing.SignatureExpired:
        return render(request, 'licensing/pmfby_self_register.html', {'error': 'Registration link expire ho gaya. Excel se dobara login karein.'}, status=410)
    except signing.BadSignature:
        return render(request, 'licensing/pmfby_self_register.html', {'error': 'Registration link valid nahi hai.'}, status=400)

    years = _pmfby_years(service)
    context = {'token': token, 'mobile': mobile, 'service_name': service}
    form = PublicPmfbyRegistrationForm(
        request.POST or None,
        financial_years=years,
        service_name=service,
        initial=_pmfby_registration_initial(mobile, service),
    )
    if request.method == 'POST' and form.is_valid():
        if form.cleaned_data['mobile'] != mobile:
            form.add_error('mobile', 'Signed mobile number change nahi kiya ja sakta.')
            context['form'] = form
            return render(request, 'licensing/pmfby_self_register.html', context)
        year = form.cleaned_data['financial_year']
        if _pmfby_queryset(mobile, year, service).exists():
            context['already_exists'] = True
            return render(request, 'licensing/pmfby_self_register.html', context)
        with transaction.atomic():
            if _pmfby_queryset(mobile, year, service).exists():
                context['already_exists'] = True
                return render(request, 'licensing/pmfby_self_register.html', context)
            record = UserInfoData.objects.create(
                mobile=int(mobile),
                pacs_name=form.cleaned_data['pacs_name'],
                brach=form.cleaned_data['brach'],
                dist=form.cleaned_data['dist'],
                state=form.cleaned_data['state'],
                operator_mobile=int(form.cleaned_data['operator_mobile']),
                f_year=year,
                for_whys=service,
                is_pri=None,
                u_pass=None,
                amount=_pmfby_default_amount(service),
                payment_status=0,
                utr_number=None,
                is_active=1,
                entry_count=0,
                limit_of_entrys=PMFBY_ENTRY_LIMIT,
                date_time=timezone.now(),
                activation_date=None,
                accepte_by=None,
                razorpay_payment_link_id=None,
                razorpay_payment_id=None,
                razorpay_reference_id=None,
                razorpay_payment_status=None,
                system_id=f'{service} Web Registration',
            )
        context.update({'created': True, 'record': record})
        return render(request, 'licensing/pmfby_self_register.html', context)
    context['form'] = form
    return render(request, 'licensing/pmfby_self_register.html', context)

FASAL_RIN_PURPOSE = 'FASAL RIN'
FASAL_RIN_DEFAULT_AMOUNT = 2000
FASAL_RIN_ENTRY_LIMIT = 20
FASAL_RIN_PAID_ENTRY_LIMIT = 3000
FASAL_RIN_TOKEN_SALT = 'licensing.fasal-rin-session.v1'
FASAL_RIN_TOKEN_MAX_AGE = 12 * 60 * 60
FASAL_RIN_WORK_TYPES = {
    1: 'Loan Application',
    2: 'Loan Approval',
    3: 'IS/PRI Upload',
}


def _fasal_work_type(value):
    work_type = _integer(value)
    return work_type if work_type in FASAL_RIN_WORK_TYPES else 0


def _fasal_queryset(mobile, financial_year, work_type):
    return UserInfoData.objects.filter(
        mobile=int(mobile),
        for_whys__iexact=FASAL_RIN_PURPOSE,
        f_year__iexact=financial_year.strip(),
        is_pri=str(work_type),
    )


def _select_fasal_record(mobile, financial_year, work_type):
    active_records = list(
        _fasal_queryset(mobile, financial_year, work_type)
        .filter(is_active=1)
        .order_by('-id')[:2]
    )
    if len(active_records) > 1:
        return None, True
    if active_records:
        return active_records[0], False
    return _fasal_queryset(mobile, financial_year, work_type).order_by('-id').first(), False


def _fasal_request_identity(body):
    mobile = _operator_mobile(body.get('mobile') or body.get('user_id'))
    financial_year = str(body.get('financial_year') or body.get('fYear') or '').strip()
    work_type = _fasal_work_type(body.get('work_type') or body.get('is_pri') or body.get('IsPri'))
    return mobile, financial_year, work_type


def _fasal_years(work_type=0):
    queryset = Perpous.objects.filter(forWhy__iexact=FASAL_RIN_PURPOSE)
    if work_type == 3:
        queryset = queryset.filter(fyear__icontains='ISSClaim')
    values = (
        queryset.exclude(fyear__isnull=True).exclude(fyear='')
        .order_by('-fyear').values_list('fyear', flat=True).distinct()
    )
    return [str(year).strip() for year in values if str(year).strip()]


def _fasal_registration_url(request, mobile, work_type):
    token = signing.dumps(
        {'mobile': mobile, 'work_type': work_type},
        salt=FASAL_RIN_TOKEN_SALT,
        compress=True,
    )
    return request.build_absolute_uri(f"{reverse('licensing:fasal_rin_self_register')}?token={token}")


def _fasal_session_token(record, work_type):
    return signing.dumps(
        {
            'record_id': record.pk,
            'mobile': str(record.mobile),
            'financial_year': record.f_year,
            'work_type': work_type,
        },
        salt=FASAL_RIN_TOKEN_SALT,
        compress=True,
    )


def _fasal_record_from_token(record_token):
    try:
        token_data = signing.loads(
            record_token,
            salt=FASAL_RIN_TOKEN_SALT,
            max_age=FASAL_RIN_TOKEN_MAX_AGE,
        )
        mobile = _operator_mobile(token_data.get('mobile'))
        financial_year = str(token_data.get('financial_year') or '').strip()
        work_type = _fasal_work_type(token_data.get('work_type'))
        record_id = _integer(token_data.get('record_id'))
    except signing.SignatureExpired:
        return None, 0, JsonResponse(
            {'success': False, 'status': 'TOKEN_EXPIRED', 'message': 'Aapka login session samapt ho gaya hai. Kripya dobara login karein.'},
            status=401,
        )
    except signing.BadSignature:
        return None, 0, JsonResponse(
            {'success': False, 'status': 'INVALID_TOKEN', 'message': 'Login verification nahi ho saki. Kripya dobara login karein.'},
            status=401,
        )
    if not mobile or not financial_year or not work_type or record_id <= 0:
        return None, 0, JsonResponse({'success': False, 'status': 'INVALID_REQUEST'}, status=400)
    record = _fasal_queryset(mobile, financial_year, work_type).filter(pk=record_id).first()
    if not record:
        return None, 0, JsonResponse({'success': False, 'status': 'LICENSE_NOT_FOUND'}, status=404)
    return record, work_type, None


@csrf_exempt
@require_POST
@never_cache
def fasal_rin_options(request):
    if _rate_limited(request, 'fasal-options', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    work_type = _fasal_work_type(body.get('work_type'))
    if not work_type:
        return JsonResponse({'success': False, 'status': 'INVALID_WORK_TYPE', 'message': 'Is Excel file ka upload type valid nahi hai.'}, status=400)
    return JsonResponse({
        'success': True,
        'status': 'OK',
        'app_code': 'FASAL_RIN',
        'service': FASAL_RIN_PURPOSE,
        'work_type': work_type,
        'work_type_name': FASAL_RIN_WORK_TYPES[work_type],
        'financial_years': _fasal_years(work_type),
    })


@csrf_exempt
@require_POST
@never_cache
def fasal_rin_subscription(request):
    if _rate_limited(request, 'fasal-login-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'authorized': False, 'status': 'INVALID_JSON'}, status=400)
    mobile, financial_year, work_type = _fasal_request_identity(body)
    if not mobile or not financial_year or not work_type:
        return JsonResponse(
            {'success': False, 'authorized': False, 'status': 'INVALID_REQUEST', 'message': 'Kripya valid mobile, financial year aur upload type use karein.'},
            status=400,
        )
    if _rate_limited(request, 'fasal-login-mobile', mobile, settings.ERP_API_MOBILE_RATE_LIMIT):
        return _too_many_requests()
    record, multiple_active = _select_fasal_record(mobile, financial_year, work_type)
    if multiple_active:
        return JsonResponse(
            {'success': False, 'authorized': False, 'status': 'MULTIPLE_ACTIVE_RECORDS', 'message': 'Is mobile, year aur upload type ke ek se adhik active accounts mile hain. Kripya support se sampark karein.'},
            status=409,
        )
    if not record:
        return JsonResponse({
            'success': True,
            'authorized': False,
            'status': 'LICENSE_NOT_FOUND',
            'message': 'Is mobile, year aur upload type ka account abhi bana nahi hai.',
            'registration_url': _fasal_registration_url(request, mobile, work_type),
        })
    authorized = _integer(record.is_active) == 1
    return JsonResponse({
        'success': True,
        'authorized': authorized,
        'status': 'ACTIVE' if authorized else 'INACTIVE',
        'message': 'Login verification successful.' if authorized else 'Aapka account abhi active nahi hai. Kripya support se sampark karein.',
        'record_id': record.pk,
        'mobile': str(record.mobile or mobile),
        'pacs_name': record.pacs_name or '',
        'service': FASAL_RIN_PURPOSE,
        'financial_year': record.f_year or financial_year,
        'work_type': work_type,
        'work_type_name': FASAL_RIN_WORK_TYPES[work_type],
        'record_token': _fasal_session_token(record, work_type) if authorized else '',
    })


@csrf_exempt
@require_POST
@never_cache
def check_fasal_rin_entry(request):
    if _rate_limited(request, 'fasal-entry-check-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'allowed': False, 'status': 'INVALID_JSON'}, status=400)
    record, work_type, error_response = _fasal_record_from_token(str(body.get('record_token') or '').strip())
    if error_response:
        return error_response
    if _integer(record.is_active) != 1:
        return JsonResponse({'success': True, 'allowed': False, 'status': 'LICENSE_NOT_ACTIVE', 'message': 'Aapka account abhi active nahi hai. Kripya support se sampark karein.'})
    paid = _integer(record.amount) > 0 and _integer(record.payment_status) == _integer(record.amount)
    entry_count = max(0, _integer(record.entry_count))
    entry_limit = _pmfby_entry_limit(record)
    allowed = paid or entry_count < entry_limit
    if paid:
        message = 'Aapka payment complete hai. Upload shuru kiya ja sakta hai.'
    elif allowed:
        message = 'Aap free upload suvidha ka upyog kar rahe hain.'
    else:
        message = f'Aapne {entry_count} free entries successfully upload kar li hain. Aage upload karne ke liye payment karna hoga.'
    return JsonResponse({
        'success': True,
        'allowed': allowed,
        'status': 'ENTRY_ALLOWED' if allowed else 'ENTRY_LIMIT_REACHED',
        'message': message,
        'access_type': 'PAID' if paid else 'FREE_TRIAL',
        'work_type': work_type,
    })


@csrf_exempt
@require_POST
@never_cache
def consume_fasal_rin_entries(request):
    if _rate_limited(request, 'fasal-consume-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    uploaded_count = _integer(body.get('uploaded_count'))
    if uploaded_count <= 0:
        return JsonResponse({'success': False, 'status': 'INVALID_REQUEST'}, status=400)
    session_record, work_type, error_response = _fasal_record_from_token(str(body.get('record_token') or '').strip())
    if error_response:
        return error_response
    with transaction.atomic():
        record = UserInfoData.objects.select_for_update().filter(pk=session_record.pk).first()
        if not record:
            return JsonResponse({'success': False, 'status': 'LICENSE_NOT_FOUND'}, status=404)
        if _integer(record.is_active) != 1:
            return JsonResponse({'success': False, 'status': 'LICENSE_NOT_ACTIVE'}, status=403)
        new_count = max(0, _integer(record.entry_count)) + uploaded_count
        paid = _integer(record.amount) > 0 and _integer(record.payment_status) == _integer(record.amount)
        entry_limit = _pmfby_entry_limit(record)
        if not paid and new_count > entry_limit:
            return JsonResponse(
                {'success': False, 'status': 'ENTRY_LIMIT_EXCEEDED', 'message': 'Aapki free upload suvidha poori ho chuki hai. Aage upload karne ke liye payment karein.'},
                status=409,
            )
        record.entry_count = new_count
        record.save(update_fields=['entry_count'])
    return JsonResponse({'success': True, 'status': 'UPLOAD_RECORDED', 'work_type': work_type})


@csrf_exempt
@require_POST
@never_cache
def get_fasal_rin_upi(request):
    if _rate_limited(request, 'fasal-upi-ip', '', settings.ERP_API_IP_RATE_LIMIT):
        return _too_many_requests()
    body = _json_body(request)
    if body is None:
        return JsonResponse({'success': False, 'status': 'INVALID_JSON'}, status=400)
    record, _work_type, error_response = _fasal_record_from_token(str(body.get('record_token') or '').strip())
    if error_response:
        return error_response
    if _integer(record.is_active) != 1:
        return JsonResponse({'success': False, 'status': 'LICENSE_NOT_ACTIVE'}, status=403)
    upi_record = tblUPI.objects.filter(isActive=1).exclude(upiID__isnull=True).exclude(upiID='').order_by('-ID').first()
    if not upi_record:
        return JsonResponse({'success': False, 'status': 'UPI_NOT_CONFIGURED', 'message': 'Payment service abhi uplabdh nahi hai. Kripya support se sampark karein.'}, status=503)
    return JsonResponse({'success': True, 'status': 'OK', 'upi_id': str(upi_record.upiID).strip()})


@require_http_methods(['GET', 'POST'])
@never_cache
def fasal_rin_self_register(request):
    token = str(request.GET.get('token') or request.POST.get('token') or '').strip()
    try:
        payload = signing.loads(token, salt=FASAL_RIN_TOKEN_SALT, max_age=FASAL_RIN_TOKEN_MAX_AGE)
        mobile = _operator_mobile(payload.get('mobile'))
        work_type = _fasal_work_type(payload.get('work_type'))
        if not mobile or not work_type:
            raise signing.BadSignature
    except signing.SignatureExpired:
        return render(request, 'licensing/fasal_rin_self_register.html', {'error': 'Registration link expire ho gaya. Excel se dobara login karein.'}, status=410)
    except signing.BadSignature:
        return render(request, 'licensing/fasal_rin_self_register.html', {'error': 'Registration link valid nahi hai.'}, status=400)

    years = _fasal_years(work_type)
    form = PublicFasalRinRegistrationForm(
        request.POST or None,
        financial_years=years,
        work_type_name=FASAL_RIN_WORK_TYPES[work_type],
        initial=_pmfby_registration_initial(mobile),
    )
    if request.method == 'POST' and form.is_valid():
        if form.cleaned_data['mobile'] != mobile:
            form.add_error('mobile', 'Signed mobile number change nahi kiya ja sakta.')
            return render(request, 'licensing/fasal_rin_self_register.html', {'form': form, 'token': token, 'mobile': mobile})
        year = form.cleaned_data['financial_year']
        if _fasal_queryset(mobile, year, work_type).exists():
            return render(request, 'licensing/fasal_rin_self_register.html', {'already_exists': True, 'mobile': mobile, 'work_type_name': FASAL_RIN_WORK_TYPES[work_type]})
        with transaction.atomic():
            if _fasal_queryset(mobile, year, work_type).exists():
                return render(request, 'licensing/fasal_rin_self_register.html', {'already_exists': True, 'mobile': mobile, 'work_type_name': FASAL_RIN_WORK_TYPES[work_type]})
            record = UserInfoData.objects.create(
                mobile=int(mobile),
                pacs_name=form.cleaned_data['pacs_name'],
                brach=form.cleaned_data['brach'],
                dist=form.cleaned_data['dist'],
                state=form.cleaned_data['state'],
                operator_mobile=int(form.cleaned_data['operator_mobile']),
                f_year=year,
                for_whys=FASAL_RIN_PURPOSE,
                is_pri=str(work_type),
                u_pass=None,
                amount=FASAL_RIN_DEFAULT_AMOUNT,
                payment_status=0,
                utr_number=None,
                is_active=1,
                entry_count=0,
                limit_of_entrys=FASAL_RIN_ENTRY_LIMIT,
                date_time=timezone.now(),
                activation_date=None,
                accepte_by=None,
                razorpay_payment_link_id=None,
                razorpay_payment_id=None,
                razorpay_reference_id=None,
                razorpay_payment_status=None,
                system_id='FASAL RIN Web Registration',
            )
        return render(request, 'licensing/fasal_rin_self_register.html', {'created': True, 'record': record, 'work_type_name': FASAL_RIN_WORK_TYPES[work_type]})
    return render(request, 'licensing/fasal_rin_self_register.html', {'form': form, 'token': token, 'mobile': mobile, 'work_type_name': FASAL_RIN_WORK_TYPES[work_type]})


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
