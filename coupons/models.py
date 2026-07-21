from django.db import models


class Coupon(models.Model):
    id = models.BigAutoField(primary_key=True, db_column='ID')
    coupon_code = models.CharField(max_length=40, unique=True, db_column='CouponCode')
    discount_amount = models.PositiveIntegerField(db_column='DiscountAmount')
    status = models.BooleanField(default=True, db_column='Status')
    used_by = models.CharField(max_length=100, blank=True, null=True, unique=True, db_column='UsedBy')
    remark = models.TextField(blank=True, null=True, db_column='Remark')

    class Meta:
        db_table = 'coupons_coupon'
        ordering = ['-id']

    def __str__(self):
        return self.coupon_code
