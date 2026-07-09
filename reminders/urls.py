from django.urls import path
from . import views

app_name = 'reminders'  # <-- NAMESPACE - YEH BOHOT IMPORTANT HAI

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.task_create, name='task_create'),
    path('<int:pk>/update/', views.task_update, name='task_update'),
    path('<int:pk>/delete/', views.task_delete, name='task_delete'),
    path('<int:pk>/toggle/', views.task_toggle_status, name='task_toggle_status'),
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),
]