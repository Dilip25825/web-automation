from django.contrib import admin

from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('id', 'coupon_code', 'discount_amount', 'status', 'used_by', 'copied_by', 'copied_at')
    search_fields = ('coupon_code', 'used_by', 'remark', 'copied_by__username')
    list_filter = ('status',)

