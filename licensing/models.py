# licensing/models.py
from django.db import models

class ClientLicense(models.Model):
    # Primary Key mapping
    id = models.AutoField(primary_key=True, db_column='ID')
    
    # Aapki table ke exact columns ka mapping (Duplicate check safe)
    pacs_id = models.CharField(max_length=50, unique=True, db_column='PacsID')
    pacs_name = models.CharField(max_length=255, db_column='PacsName')
    dist = models.CharField(max_length=100, db_column='Dist', blank=True, null=True)
    ncl_year = models.CharField(max_length=20, db_column='NCLYear', blank=True, null=True)
    
    # Active status: MySQL me agar 1/0 hai toh IntegerField ya BooleanField dono chalega
    is_active = models.IntegerField(db_column='isActive', default=1)
    
    amount = models.IntegerField(db_column='Amount', default=0)
    payment_status = models.CharField(max_length=50, db_column='PaymentStatus', blank=True, null=True)
    date_time_create = models.DateTimeField(db_column='DateTimeCreate', blank=True, null=True)
    operator_mobile = models.CharField(max_length=15, db_column='OperatorMobile', blank=True, null=True)
    remark = models.TextField(db_column='Remark', blank=True, null=True)
    entry_count = models.IntegerField(db_column='EntryCount', default=0)

    class Meta:
        managed = False        # Data safety guardrail: Django table me koi badlaav nahi karega
        db_table = 'nclData'   # Aapki actual MySQL table

    def __str__(self):
        return f"{self.pacs_id} - {self.pacs_name}"

# licensing/models.py me 'UserInfo' table ke liye naya model
# class Perpous(models.Model):
#     # ON ERROR HANDLING: CharField lagaya hai purposes/utilities ke naam ke liye
#     forWhy = models.CharField(max_length=100)

#     class Meta:
#         db_table = 'perpous' # <-- Database me table ka naam 'perpous' locked rahega

#     def __str__(self):
#         return self.forWhy

class UserInfoData(models.Model):
    # Primary Key mapping
    id = models.AutoField(primary_key=True, db_column='ID')
    
    # Core Fields matching your new screenshot
    mobile = models.BigIntegerField(db_column='Mobile', blank=True, null=True)
    pacs_name = models.CharField(max_length=255, db_column='PacsName', blank=True, null=True)
    dist = models.CharField(max_length=100, db_column='Dist', blank=True, null=True)
    f_year = models.CharField(max_length=20, db_column='fYear', blank=True, null=True) # NCLYear ki jagah fYear hai
    
    test = ('id','mobile','pacs_name','f_year','is_active','amount','payment_status')

    # Activation & Amount Status
    is_active = models.IntegerField(db_column='isActive', default=0, blank=True, null=True)
    amount = models.IntegerField(db_column='Amount', default=0, blank=True, null=True)
    payment_status = models.IntegerField(db_column='PaymentStatus', blank=True, null=True) # Screenshot ke mutabik ye 'int' hai
    
    # Mobile & Communication
    operator_mobile = models.BigIntegerField(db_column='OperatorMobile', blank=True, null=True) # bigint ke liye BigIntegerField
    
    # New specific columns from userinfo table
    accepte_by = models.TextField(db_column='AccepteBy', blank=True, null=True)
    brach = models.CharField(max_length=100, db_column='Brach', blank=True, null=True)
    branch_approve = models.IntegerField(db_column='BranchApprove', blank=True, null=True)
    branch_id = models.CharField(max_length=50, db_column='BranchID', blank=True, null=True)
    state = models.CharField(max_length=50, db_column='BranchPass', blank=True, null=True)
    
    # Date and Timestamps
    date_time = models.DateTimeField(db_column='Date_Time', blank=True, null=True)
    last_login = models.DateTimeField(db_column='lastLogin', blank=True, null=True)
    activation_date = models.DateTimeField(db_column='ActivationDate', blank=True, null=True)
    
    # Additional Fields
    entry_count = models.IntegerField(db_column='EntryCount', blank=True, null=True)
    for_whys = models.CharField(max_length=255, db_column='forWhys', blank=True, null=True)
    is_animal = models.IntegerField(db_column='IsAnimal', blank=True, null=True)
    is_pri = models.CharField(max_length=10, db_column='IsPri', blank=True, null=True)
    limit_of_entrys = models.IntegerField(db_column='LimitOfEntrys', default=20, blank=True, null=True)
    system_id = models.CharField(max_length=100, db_column='systemID', blank=True, null=True)
    u_pass = models.CharField(max_length=100, db_column='uPass', blank=True, null=True)
    utr_number = models.CharField(max_length=100, db_column='UtrNumber', blank=True, null=True)
    razorpay_payment_link_id = models.CharField(max_length=50, db_column='RazorpayPaymentLinkID', unique=True, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=50, db_column='RazorpayPaymentID', unique=True, blank=True, null=True)
    razorpay_reference_id = models.CharField(max_length=40, db_column='RazorpayReferenceID', unique=True, blank=True, null=True)
    razorpay_payment_status = models.CharField(max_length=20, db_column='RazorpayPaymentStatus', blank=True, null=True)
    # licensing/models.py ke UserInfoData model ke andar ye function add karein

    @property
    def hero_pacs_name(self):
        """Return the first PACS display name found after '/', when present."""
        name = (self.pacs_name or '').strip()
        if '/' in name:
            name_after_slash = name.split('/', 1)[1].strip()
            if name_after_slash:
                return name_after_slash
        return name or 'Unnamed PACS'

    class Meta:
        managed = False        # Data safety guardrail: Django table me koi badlaav nahi karega
        db_table = 'userinfo'   # Aapki actual MySQL table


# Purana UserInfoData model pehle se hoga, uske niche ye naya jodein:

class tblPacsErp(models.Model):
    # ON ERROR FIX: Explicit unique fields mapping for NCL PacsErp table
    id = models.AutoField(primary_key=True, db_column='ID')
    amount = models.IntegerField(db_column='Amount', default=0, null=True, blank=True)
    brach = models.CharField(max_length=255, db_column='Brach', null=True, blank=True)
    date_time = models.DateTimeField(db_column='Date_Time', auto_now_add=True, null=True, blank=True)
    dist = models.CharField(max_length=255, db_column='Dist', null=True, blank=True)
    erp_id = models.TextField(db_column='ErpID', null=True, blank=True) # <-- Ye field sirf isi table me hai
    expiry_date = models.DateField(db_column='Expiry_Date', null=True, blank=True)
    is_active = models.IntegerField(db_column='isActive', default=0, null=True, blank=True)
    last_login = models.DateTimeField(db_column='lastLogin', null=True, blank=True)
    operator_mobile = models.BigIntegerField(db_column='OperatorMobile', null=True, blank=True)
    pacs_name = models.CharField(max_length=255, db_column='PacsName', null=True, blank=True)
    payment_status = models.IntegerField(db_column='PaymentStatus', default=0, null=True, blank=True)
    remark = models.CharField(max_length=255, db_column='Remark', null=True, blank=True)
    state = models.CharField(max_length=255, db_column='State', null=True, blank=True)
    system_id = models.CharField(max_length=255, db_column='systemID', null=True, blank=True)
    utr_number = models.CharField(max_length=255, db_column='UtrNumber', null=True, blank=True)
    version_info = models.TextField(db_column='VersionInfo', null=True, blank=True)
    accepte_by = models.TextField(db_column='AccepteBy', null=True, blank=True)
    activation_date = models.DateTimeField(db_column='ActivationDate', null=True, blank=True)
    razorpay_payment_link_id = models.CharField(max_length=50, db_column='RazorpayPaymentLinkID', unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=50, db_column='RazorpayPaymentID', unique=True, null=True, blank=True)
    razorpay_reference_id = models.CharField(max_length=40, db_column='RazorpayReferenceID', unique=True, null=True, blank=True)
    razorpay_payment_status = models.CharField(max_length=20, db_column='RazorpayPaymentStatus', null=True, blank=True)
    @property
    def hero_pacs_name(self):
        """Use the PACS name segment after the first slash for compact display."""
        name = (self.pacs_name or '').strip()
        if '/' in name:
            name_after_slash = name.split('/', 1)[1].strip()
            if name_after_slash:
                return name_after_slash
        return name or 'Unnamed PACS'
    class Meta:
        # ON ERROR FIX: Strict table binding for NCL dashboard
        db_table = 'tblPacsErp'  # <-- Ensure karein ki yahan capital aur small letters exact database wale hon
        managed = False

class tblUPI(models.Model):
    # ON ERROR FIX: Explicit unique fields mapping for NCL PacsErp table
    ID = models.AutoField(primary_key=True, db_column='ID')
    upiID = models.TextField(db_column='upiID', null=True, blank=True)
    Remark = models.TextField(db_column='Remark', null=True, blank=True)
    isActive = models.IntegerField(db_column='isActive', null=True, blank=True)

    class Meta:
        # ON ERROR FIX: Strict table binding for NCL dashboard
        managed = False
        db_table = 'tblUPI'  # <-- Ensure karein ki yahan capital aur small letters exact database wale hon




class Perpous(models.Model):
    # ID automatic Django create karta hai, agar aapko custom rakhni hai to primary_key=True use karein
    ID = models.CharField(max_length=255, verbose_name="ID") 
    forWhy = models.TextField(max_length=255, null=True, blank=True, verbose_name="forWhy")
    fyear = models.TextField(null=True, blank=True, verbose_name="fyear")

    class Meta:
        # Database table ka sahi naam ensure karne ke liye
        db_table = 'perpous'
        verbose_name = 'Perpous'
        verbose_name_plural = 'Perpous'

    def __str__(self):
        # Admin panel mein list view mein jo name dikhega, wahi return karein
        return self.forWhy

class VersionInfo(models.Model):
    # id = models.CharField(max_length=255, verbose_name="id") 
    Description = models.TextField(max_length=255,null=True,blank=True,verbose_name='Description')
    Year = models.TextField(max_length=255,null=True,blank=True,verbose_name='Year')
    Version = models.TextField(max_length=255,null=True,blank=True,verbose_name='Version')
    Remark = models.TextField(max_length=255,null=True,blank=True,verbose_name='Remark')

    class Meta:
        db_table = 'VersionInfo'
    
    def __str__(self):
        return self.Description


@property
def status_active(self):
    # On Error GoTo jaise safety net: safe data-type check lagaya hai
    try:
        amt = int(self.amount or 0)
        pay_stat = int(self.payment_status or 0)
        
        # Agar Amount 0 se bada hai AUR Amount aur PaymentStatus ekdum barabar hain
        if  amt == pay_stat:
            return True
        return False
    except Exception:
        return False # Kisi bhi discrepancy me safe side Inactive return karega
class Meta:
    managed = False          # On Error Safe: Django is table ko drop ya alter nahi karega
    db_table = 'userinfo'    # <-- Aapki actual MySQL ki 'userinfo' table ka naam

def __str__(self):
    return f"{self.id} - {self.pacs_name if self.pacs_name else 'No Name'}"