from django.urls import path

from . import views

app_name = 'downloads'

urlpatterns = [
    path('', views.public_downloads, name='public_downloads'),
    path('sync/', views.sync_drive_catalog, name='sync_drive_catalog'),
    path('file/<str:file_id>/', views.file_download, name='file_download'),
    path('drive/<str:token>/', views.drive_download, name='drive_download'),
]