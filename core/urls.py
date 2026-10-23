from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('pricing/', views.pricing, name='pricing'),
    path('solutions/<slug:slug>/', views.solution_detail, name='solution_detail'),
    path('contact/', views.contact, name='contact'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('documentation/', views.documentation, name='documentation'),
    path('client-guide/', views.client_guide, name='client_guide'),
    path('erp-guide/', views.erp_guide, name='erp_guide'),
    path('terms-and-conditions/', views.terms_and_conditions, name='terms_and_conditions'),
    path('refund-policy/', views.refund_policy, name='refund_policy'),
    path('privacy-policy/', views.privacy_policy, name='privacy_policy'),
    path('ads.txt', views.ads_txt, name='ads_txt'),
]
