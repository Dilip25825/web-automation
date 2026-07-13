from django.urls import path

from . import views

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
    path('delete-record/<int:record_id>/', views.delete_record_view, name='delete_record'),
    path('userinfo/delete/<int:user_id>/', views.delete_userinfo_view, name='delete_userinfo'),
    path('userinfo/update/<int:client_id>/', views.update_userinfo_view, name='update_userinfo'),
    path('pacserp/update/<int:record_id>/', views.update_pacserp_view, name='update_pacserp'),
]