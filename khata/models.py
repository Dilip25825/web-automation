from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

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
    attachment_drive_id = models.CharField(max_length=255, blank=True, null=True, unique=True)
    attachment_name = models.CharField(max_length=255, blank=True, null=True)
    attachment_mime_type = models.CharField(max_length=100, blank=True, null=True)
    attachment_size = models.PositiveBigIntegerField(blank=True, null=True)
    attachment_uploaded_at = models.DateTimeField(blank=True, null=True)

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

class ActivationLedgerMapping(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activation_ledger_mappings')
    accepted_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accepted_activation_ledgers')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='activation_user_mappings')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['owner', 'accepted_user'], name='unique_activation_ledger_user_mapping'),
        ]


class ActivationLedgerEntry(models.Model):
    SOURCE_TYPES = (('USERINFO', 'UserInfo'), ('PACS_ERP', 'PACS ERP'))

    activation_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPES)
    source_record_id = models.PositiveBigIntegerField()
    activated_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_activation_ledger_entries')
    accepted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assigned_activation_ledger_entries')
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name='activation_ledger_entries')
    transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='activation_entry')
    reversal_transaction = models.OneToOneField(Transaction, on_delete=models.PROTECT, related_name='activation_reversal', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['source_type', 'source_record_id'], name='khata_activ_source__918027_idx')]