from django.conf import settings
from django.db import models


class Coupon(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    coupon_code = models.CharField(max_length=48, unique=True, db_column='CouponCode')
    discount_amount = models.PositiveIntegerField(db_column='DiscountAmount')
    status = models.BooleanField(default=True, db_column='Status')
    used_by = models.CharField(max_length=100, blank=True, null=True, unique=True, db_column='UsedBy')
    remark = models.TextField(blank=True, null=True, db_column='Remark')
    copied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='copied_coupons',
        db_column='CopiedBy',
    )
    copied_at = models.DateTimeField(blank=True, null=True, db_column='CopiedAt')

    class Meta:
        db_table = 'coupons_coupon'
        ordering = ['-id']

    def __str__(self):
        return self.coupon_code
