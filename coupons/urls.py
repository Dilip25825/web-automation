from django.urls import path

from . import views

app_name = 'coupons'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('generate/', views.generate_code, name='generate'),
    path('create/', views.create_coupon, name='create'),
    path('bulk-create/', views.bulk_create_coupons, name='bulk_create'),
    path('<int:pk>/update/', views.update_coupon, name='update'),
    path('<int:pk>/delete/', views.delete_coupon, name='delete'),
]

