from django.urls import path
from . import views

urlpatterns = [
    path('', views.public_downloads, name='public_downloads'),
    path('manage/', views.manage_links, name='manage_links'),
    path('manage/<int:pk>/edit/', views.edit_link, name='edit_link'),
]
