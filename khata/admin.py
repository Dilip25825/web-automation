from django.contrib import admin
from .models import Customer, Transaction, ShopProfile

# In teeno models ko Admin Panel mein register kar rahe hain
# admin.site.register(Customer)
# admin.site.register(Transaction)
admin.site.register(ShopProfile)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'user') # Admin list me ye columns dikhenge
    search_fields = ('name', 'phone')        # Admin me search ka option aa jayega

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('customer', 'amount', 'trans_type', 'date')
    list_filter = ('trans_type', 'date')     # Side me filter aa jayenge