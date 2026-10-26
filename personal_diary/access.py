from functools import wraps

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login

from .models import DiaryAccessSettings


def can_access_diary(user, request=None):
    """Return only explicit diary access; staff and superuser are not bypasses."""
    if not getattr(user, 'is_authenticated', False):
        return False

    cache_name = '_personal_diary_access_allowed'
    if request is not None and hasattr(request, cache_name):
        return getattr(request, cache_name)

    allowed = DiaryAccessSettings.objects.filter(user=user, can_access_diary=True).exists()
    if request is not None:
        setattr(request, cache_name, allowed)
    return allowed


def diary_access_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
        if not can_access_diary(request.user, request):
            raise PermissionDenied('Diary access is not enabled for this account.')
        return view_func(request, *args, **kwargs)

    return wrapped


def diary_access_context(request):
    return {'can_access_diary': can_access_diary(request.user, request)}
