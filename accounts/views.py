import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import NewPasswordForm, OTPVerificationForm, ProfileEmailForm
from .models import PasswordResetOTP

OTP_SESSION_KEY = 'password_reset_otp_id'
OTP_VERIFIED_SESSION_KEY = 'password_reset_otp_verified'
OTP_REQUESTED_SESSION_KEY = 'password_reset_otp_requested'
OTP_VALIDITY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5


def _get_session_otp(request, *, verified=False):
    otp_id = request.session.get(OTP_SESSION_KEY)
    if not otp_id or (verified and not request.session.get(OTP_VERIFIED_SESSION_KEY)):
        return None
    try:
        return PasswordResetOTP.objects.select_related('user').get(pk=otp_id)
    except PasswordResetOTP.DoesNotExist:
        return None


def _clear_reset_session(request):
    request.session.pop(OTP_SESSION_KEY, None)
    request.session.pop(OTP_VERIFIED_SESSION_KEY, None)
    request.session.pop(OTP_REQUESTED_SESSION_KEY, None)


@login_required
def profile(request):
    if request.method == 'POST':
        form = ProfileEmailForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your email address has been saved.')
            return redirect('accounts:profile')
    else:
        form = ProfileEmailForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def password_reset_request(request):
    user = request.user
    if not user.email:
        messages.error(request, 'Save your email address before changing the password.')
        return redirect('accounts:profile')
    if request.method == 'POST':
        _clear_reset_session(request)
        request.session[OTP_REQUESTED_SESSION_KEY] = True
        code = f'{secrets.randbelow(1_000_000):06d}'
        with transaction.atomic():
            PasswordResetOTP.objects.filter(user=user, used_at__isnull=True).update(used_at=timezone.now())
            otp = PasswordResetOTP(user=user, expires_at=timezone.now() + timedelta(minutes=OTP_VALIDITY_MINUTES))
            otp.set_code(code)
            otp.save()
            try:
                send_mail(
                    subject='Your Web Automation password reset OTP',
                    message=f'Your password reset OTP is: {code}\n\nIt is valid for {OTP_VALIDITY_MINUTES} minutes. Do not share this OTP with anyone.',
                    from_email=settings.DEFAULT_FROM_EMAIL or None,
                    recipient_list=[user.email],
                    fail_silently=False,
                )
            except Exception:
                otp.delete()
                messages.error(request, 'OTP email could not be sent right now. Please try again shortly.')
                return redirect('accounts:password_reset_request')
        request.session[OTP_SESSION_KEY] = otp.pk
        request.session.modified = True
        messages.success(request, 'A 6-digit OTP has been sent to your saved email address.')
        return redirect('accounts:password_reset_verify')
    return render(request, 'accounts/password_reset_request.html', {'email': user.email})


@login_required
def password_reset_verify(request):
    otp = _get_session_otp(request)
    if otp and not otp.is_active:
        _clear_reset_session(request)
        messages.error(request, 'Request a new OTP to continue.')
        return redirect('accounts:password_reset_request')
    if not otp and not request.session.get(OTP_REQUESTED_SESSION_KEY):
        return redirect('accounts:password_reset_request')
    form = OTPVerificationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        if otp and otp.check_code(form.cleaned_data['code']):
            request.session[OTP_VERIFIED_SESSION_KEY] = True
            request.session.modified = True
            return redirect('accounts:password_reset_confirm')
        if not otp:
            form.add_error('code', 'Incorrect OTP. Request a new OTP and try again.')
            return render(request, 'accounts/password_reset_verify.html', {'form': form})
        otp.attempts += 1
        otp.save(update_fields=['attempts'])
        remaining = OTP_MAX_ATTEMPTS - otp.attempts
        if remaining <= 0:
            _clear_reset_session(request)
            messages.error(request, 'Too many incorrect OTP attempts. Request a new OTP.')
            return redirect('accounts:password_reset_request')
        form.add_error('code', f'Incorrect OTP. {remaining} attempt(s) remaining.')
    return render(request, 'accounts/password_reset_verify.html', {'form': form, 'expires_at': otp.expires_at})


@login_required
def password_reset_confirm(request):
    otp = _get_session_otp(request, verified=True)
    if not otp or not otp.is_active:
        _clear_reset_session(request)
        messages.error(request, 'Your OTP verification has expired. Request a new OTP.')
        return redirect('accounts:password_reset_request')
    form = NewPasswordForm(otp.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            form.save()
            otp.used_at = timezone.now()
            otp.save(update_fields=['used_at'])
        _clear_reset_session(request)
        messages.success(request, 'Password changed successfully. You can now sign in.')
        return redirect('accounts:login')
    return render(request, 'accounts/password_reset_confirm.html', {'form': form})
