from django.http import HttpResponseForbidden, JsonResponse

from .models import ActivationOperatorSettings

_UNSET = object()


MENU_FIELDS = (
    'dashboard', 'user_licenses', 'erp_licenses', 'reminders',
    'khata', 'coupons', 'downloads',
)


def menu_permissions(user, activation_settings=_UNSET):
    permissions = {name: True for name in MENU_FIELDS}
    if not user.is_authenticated or user.is_superuser:
        return permissions
    settings = (
        ActivationOperatorSettings.objects.filter(user=user).first()
        if activation_settings is _UNSET else activation_settings
    )
    if not settings:
        return permissions
    return {name: getattr(settings, f'show_{name}') for name in MENU_FIELDS}


def request_operator_settings(request):
    """Load an operator setting once per request without cross-request caching."""
    if not request.user.is_authenticated or request.user.is_superuser:
        return None
    if getattr(request, '_activation_operator_settings_loaded', False):
        return request._activation_operator_settings
    request._activation_operator_settings = (
        ActivationOperatorSettings.objects.select_related('customer__user')
        .filter(user=request.user)
        .first()
    )
    request._activation_operator_settings_loaded = True
    return request._activation_operator_settings


def menu_permissions_context(request):
    return {
        'menu_permissions': getattr(request, 'menu_permissions', menu_permissions(request.user)),
    }


def required_menu(request):
    match = request.resolver_match
    if not match:
        return None
    if match.namespace == 'core' and match.url_name == 'dashboard':
        return 'dashboard'
    if match.namespace in {'reminders', 'khata', 'coupons', 'downloads'}:
        return match.namespace if match.namespace != 'downloads' else 'downloads'
    if match.namespace != 'licensing':
        return None
    if match.url_name in {'userinfo_dashboard', 'toggle_activation', 'generate_invoice', 'create_userinfo', 'delete_userinfo', 'update_userinfo'}:
        return 'user_licenses'
    if match.url_name in {'pacserp_dashboard', 'toggle_erp_activation', 'generate_erp_invoice', 'create_pacserp', 'delete_record', 'update_pacserp'}:
        return 'erp_licenses'
    return None


class OperatorMenuAccessMiddleware:
    """Keep configured menu visibility and direct URL access in sync."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        activation_settings = request_operator_settings(request)
        permissions = menu_permissions(request.user, activation_settings)
        request.menu_permissions = permissions
        menu = required_menu(request)
        if not menu or permissions[menu]:
            return None
        message = 'Aapko is section ka access nahi diya gaya hai.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=403)
        return HttpResponseForbidden(message)
