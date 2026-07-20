from django.urls import path

from . import payment_views

app_name = 'payments'

urlpatterns = [
    path('csrf/', payment_views.payment_csrf, name='csrf'),
    path('create/', payment_views.payment_create, name='create'),
    path('status/', payment_views.payment_status, name='status'),
    path('razorpay/webhook/', payment_views.razorpay_webhook, name='razorpay_webhook'),
]