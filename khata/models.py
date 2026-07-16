from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Customer(models.Model):
    # Har customer kisi ek user (dukaandaar) se juda hoga
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('GIVEN', 'Maine Diye'), # Udhaar
        ('GOT', 'Mujhe Mile'),   # Jama
    )
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    trans_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    date = models.DateField(default=timezone.now)
    remarks = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        indexes = [models.Index(fields=['customer', '-date']), models.Index(fields=['date'])]
        constraints = [models.CheckConstraint(condition=models.Q(amount__gt=0), name='transaction_amount_positive')]

    def __str__(self):
        return f"{self.customer.name} - {self.amount} ({self.trans_type})"

# khata/models.py

class ShopProfile(models.Model):
    # Har ek user (dukaandaar) ka ek hi profile hoga
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    shop_name = models.CharField(max_length=150, default="Meri Dukaan")
    address = models.TextField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)

    def __str__(self):
        return self.shop_name