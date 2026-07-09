# licensing/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.contrib import admin

admin.site.site_header = "Web Automation With Excel"  # Ye header mein dikhega
admin.site.site_title = "Web Automation"            # Ye browser tab ke title mein dikhega
admin.site.index_title = "Web Automation With Excel administration" # Admin home page ke top par dikhega

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='licensing/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Main Hub
    path('', views.main_hub, name='main_hub'),
    
    # 1. User Info Data Table Blocks
    path('userinfo/', views.userinfo_dashboard, name='userinfo_dashboard'),
    path('toggle/<int:pk>/', views.toggle_activation, name='toggle_activation'),
    
    # 2. NCL (tblPacsErp) Data Table Blocks [NEW]
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
    # path('ajax/load-f-years/', views.load_f_years, name='ajax_load_f_years'),
]