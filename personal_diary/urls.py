from django.urls import path

from . import views

app_name = 'personal_diary'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('entries/', views.entry_list, name='entry_list'),
    path('entries/new/', views.entry_create, name='entry_create'),
    path('entries/<int:pk>/', views.entry_detail, name='entry_detail'),
    path('entries/<int:pk>/edit/', views.entry_update, name='entry_update'),
    path('entries/<int:pk>/delete/', views.entry_delete, name='entry_delete'),
    path('entries/<int:pk>/media/upload/', views.media_upload, name='media_upload'),
    path('media/<int:pk>/download/', views.media_download, name='media_download'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('gallery/', views.gallery, name='gallery'),
    path('media/<int:pk>/delete/', views.media_delete, name='media_delete'),
    path('events/', views.event_list, name='event_list'),
    path('events/new/', views.event_form, name='event_create'),
    path('events/<int:pk>/edit/', views.event_form, name='event_edit'),
    path('events/<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('autosave/', views.autosave, name='autosave_create'),
    path('entries/<int:pk>/autosave/', views.autosave, name='autosave'),
    path('entries/<int:pk>/unlock/', views.unlock_entry, name='unlock_entry'),
    path('pin/', views.pin_settings, name='pin_settings'),
    path('pin/reset/', views.pin_reset, name='pin_reset'),
    path('preferences/on-this-day/', views.on_this_day_preference, name='on_this_day_preference'),
    path('export/json/', views.export_json, name='export_json'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
]
