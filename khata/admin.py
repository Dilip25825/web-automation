from django.contrib import admin
from .models import Customer, Transaction, ShopProfile, ActivationOperatorSettings


@admin.register(ActivationOperatorSettings)
class ActivationOperatorSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'customer', 'search_only', 'automatic_ledger', 'enabled_menus')
    fieldsets = (
        ('Operator and Khata ledger', {'fields': ('user', 'customer')}),
        ('License workflow', {'fields': ('search_only', 'automatic_ledger')}),
        ('Visible menus', {'fields': (
            'show_dashboard', 'show_user_licenses', 'show_erp_licenses',
            'show_reminders', 'show_khata', 'show_coupons', 'show_downloads',
        )}),
    )

    @admin.display(description='Enabled menus')
    def enabled_menus(self, obj):
        labels = {
            'show_dashboard': 'Dashboard', 'show_user_licenses': 'User Licenses',
            'show_erp_licenses': 'ERP Licenses', 'show_reminders': 'Reminders',
            'show_khata': 'Khata', 'show_coupons': 'Coupons', 'show_downloads': 'Download',
        }
        return ', '.join(label for field, label in labels.items() if getattr(obj, field)) or 'None'

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and (obj is None or obj.customer.user_id == request.user.pk)

    def has_delete_permission(self, request, obj=None):
        return self.has_change_permission(request, obj)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(customer__user=request.user)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'customer':
            kwargs['queryset'] = Customer.objects.filter(user=request.user)
        elif db_field.name == 'user':
            from django.contrib.auth.models import User
            kwargs['queryset'] = User.objects.filter(is_active=True, is_superuser=False)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

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
