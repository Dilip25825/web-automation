from django.urls import path

from . import api_views

app_name = 'coupon_api'

urlpatterns = [
    path('csrf/', api_views.coupon_csrf, name='csrf'),
    path('redeem/', api_views.redeem_coupon, name='redeem'),
]

