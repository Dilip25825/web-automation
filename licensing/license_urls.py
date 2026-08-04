from django.urls import path

from . import license_views

app_name = "license_api"

urlpatterns = [
    path("validate/", license_views.validate_license, name="validate"),
    path("activation-check/", license_views.check_activation, name="activation_check"),
]
