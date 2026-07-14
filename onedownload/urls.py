from django.urls import path
from . import views

app_name = 'downloads'

urlpatterns = [
    path('', views.public_downloads, name='public_downloads'),
    path('links/create/', views.link_create, name='link_create'),
    path('links/<int:pk>/update/', views.link_update, name='link_update'),
    path('links/<int:pk>/delete/', views.link_delete, name='link_delete'),
    path('categories/create/', views.category_create, name='category_create'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
]
