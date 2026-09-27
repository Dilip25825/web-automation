from django.http import HttpResponseForbidden, JsonResponse

from .models import ActivationOperatorSettings


MENU_FIELDS = (
    'dashboard', 'user_licenses', 'erp_licenses', 'reminders',
    'khata', 'coupons', 'downloads',
)


def menu_permissions(user):
    permissions = {name: True for name in MENU_FIELDS}
    if not user.is_authenticated or user.is_superuser:
        return permissions
    settings = ActivationOperatorSettings.objects.filter(user=user).first()
    if not settings:
        return permissions
    return {name: getattr(settings, f'show_{name}') for name in MENU_FIELDS}


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
        permissions = menu_permissions(request.user)
        request.menu_permissions = permissions
        menu = required_menu(request)
        if not menu or permissions[menu]:
            return None
        message = 'Aapko is section ka access nahi diya gaya hai.'
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=403)
        return HttpResponseForbidden(message)
