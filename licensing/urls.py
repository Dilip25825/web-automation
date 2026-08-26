from django.urls import path

from . import license_views, views

app_name = 'licensing'

urlpatterns = [
    path('userinfo/', views.userinfo_dashboard, name='userinfo_dashboard'),
    path('toggle/<int:pk>/', views.toggle_activation, name='toggle_activation'),
    path('pacserp/', views.pacserp_dashboard, name='pacserp_dashboard'),
    path('toggle-erp/<int:pk>/', views.toggle_erp_activation, name='toggle_erp_activation'),
    path('userinfo/invoice/<int:pk>/', views.generate_invoice, name='generate_invoice'),
    path('pacserp/invoice/<int:pk>/', views.generate_erp_invoice, name='generate_erp_invoice'),
    path('userinfo/add/', views.create_userinfo, name='create_userinfo'),
    path('pacserp/add/', views.create_pacserp, name='create_pacserp'),
    path('erp/register/', license_views.erp_self_register, name='erp_self_register'),
    path('erp/invoice/online/<str:token>/', license_views.erp_online_invoice, name='erp_online_invoice'),
    path('pmfby/register/', license_views.pmfby_self_register, name='pmfby_self_register'),
    path('fasal-rin/register/', license_views.fasal_rin_self_register, name='fasal_rin_self_register'),
    path('delete-record/<int:record_id>/', views.delete_record_view, name='delete_record'),
    path('userinfo/delete/<int:user_id>/', views.delete_userinfo_view, name='delete_userinfo'),
    path('userinfo/update/<int:client_id>/', views.update_userinfo_view, name='update_userinfo'),
    path('pacserp/update/<int:record_id>/', views.update_pacserp_view, name='update_pacserp'),
    path('system-settings/', views.system_settings, name='system_settings'),
    path('system-settings/purposes/add/', views.create_purpose, name='create_purpose'),
    path('system-settings/purposes/<int:pk>/update/', views.update_purpose, name='update_purpose'),
    path('system-settings/purposes/<int:pk>/delete/', views.delete_purpose, name='delete_purpose'),
    path('system-settings/upi/add/', views.create_upi, name='create_upi'),
    path('system-settings/upi/<int:pk>/update/', views.update_upi, name='update_upi'),
    path('system-settings/upi/<int:pk>/delete/', views.delete_upi, name='delete_upi'),
    path('system-settings/upi/qr/', views.generate_upi_qr, name='generate_upi_qr'),
]
