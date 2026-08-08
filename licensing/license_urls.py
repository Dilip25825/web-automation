from django.urls import path

from . import license_views

app_name = "license_api"

urlpatterns = [
    path("validate/", license_views.validate_license, name="validate"),
    path("activation-check/", license_views.check_activation, name="activation_check"),
    path("erp/device/register/", license_views.register_erp_device, name="erp_device_register"),
    path("erp/subscription/", license_views.check_erp_subscription, name="erp_subscription"),
    path("erp/version/", license_views.check_erp_version, name="erp_version"),
    path("erp/upi/", license_views.get_erp_upi, name="erp_upi"),
]
