# khata/urls.py
from django.urls import path
from . import views
app_name = 'khata'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('add-customer/', views.add_customer, name='add_customer'),
    path('transfer-voucher/', views.transfer_voucher, name='transfer_voucher'),
    
    # Grahak delete karne ka URL (id ke saath)
    path('delete-customer/<int:customer_id>/', views.delete_customer, name='delete_customer'),
    
    # Grahak ka personal hisaab dekhne ka URL
    path('customer/<int:customer_id>/', views.customer_detail, name='customer_detail'),
    path('delete-transaction/<str:b64_trans_id>/', views.delete_transaction, name='delete_transaction'),
    path('add-interest/<str:b64_id>/', views.add_interest, name='add_interest'),
    path('download-pdf/<str:b64_id>/', views.download_ledger_pdf, name='download_ledger_pdf'),
    path('attachment/<str:b64_trans_id>/', views.view_transaction_attachment, name='view_transaction_attachment'),
    path('update-customer/<str:b64_id>/', views.update_customer, name='update_customer'),
    path('update-transaction/<str:b64_trans_id>/', views.update_transaction, name='update_transaction'),
    path('settings/', views.shop_profile, name='shop_profile'),
    path('report/', views.report_page, name='report_page'),
    
]
