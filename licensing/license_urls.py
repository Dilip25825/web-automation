from django.urls import path

from . import interest_subvention_views, license_views

app_name = "license_api"

urlpatterns = [
    path(
        "userinfo/interest-subvention/options/",
        interest_subvention_views.options,
        name="interest_subvention_options",
    ),
    path(
        "userinfo/interest-subvention/subscription/",
        interest_subvention_views.subscription,
        name="interest_subvention_subscription",
    ),
    path(
        "userinfo/interest-subvention/entries/consume/",
        interest_subvention_views.consume_entries,
        name="interest_subvention_entries_consume",
    ),
    path("userinfo/fasal-rin/options/", license_views.fasal_rin_options, name="fasal_rin_options"),
    path("userinfo/fasal-rin/subscription/", license_views.fasal_rin_subscription, name="fasal_rin_subscription"),
    path("userinfo/fasal-rin/entries/check/", license_views.check_fasal_rin_entry, name="fasal_rin_entry_check"),
    path("userinfo/fasal-rin/entries/consume/", license_views.consume_fasal_rin_entries, name="fasal_rin_entries_consume"),
    path("userinfo/fasal-rin/upi/", license_views.get_fasal_rin_upi, name="fasal_rin_upi"),    path("userinfo/pmfby/options/", license_views.pmfby_options, name="pmfby_options"),
    path("userinfo/pmfby/subscription/", license_views.pmfby_subscription, name="pmfby_subscription"),
    path("userinfo/pmfby/entries/check/", license_views.check_pmfby_entry, name="pmfby_entry_check"),
    path("userinfo/pmfby/upi/", license_views.get_pmfby_upi, name="pmfby_upi"),
    path("userinfo/pmfby/entries/consume/", license_views.consume_pmfby_entries, name="pmfby_entries_consume"),
    path("validate/", license_views.validate_license, name="validate"),
    path("activation-check/", license_views.check_activation, name="activation_check"),
    path("erp/device/register/", license_views.register_erp_device, name="erp_device_register"),
    path("erp/subscription/", license_views.check_erp_subscription, name="erp_subscription"),
    path("erp/version/", license_views.check_erp_version, name="erp_version"),
    path("erp/upi/", license_views.get_erp_upi, name="erp_upi"),
    path("erp/invoice/create/", license_views.create_erp_invoice, name="erp_invoice_create"),
]
