from django.contrib import admin
from .models import ClientLicense,tblPacsErp,UserInfoData,tblUPI,Perpous,VersionInfo

admin.site.register(ClientLicense)
admin.site.register(tblPacsErp)

@admin.register(tblUPI)
class tblUPIAdmin(admin.ModelAdmin):
    # Admin panel mein table columns ke roop mein dikhane ke liye
    # (Apne model ke actual field names yahan replace karein)
    list_display = ('ID', 'upiID', 'Remark', 'isActive')
    
    # Right side mein filter add karne ke liye
    list_filter = ('upiID', 'isActive')
    
    # Top par search bar add karne ke liye
    search_fields = ('upiID',)


@admin.register(UserInfoData)
class UserInfoDataAdmin(admin.ModelAdmin):
    list_display =  ('id','mobile','pacs_name','f_year','is_active','amount','payment_status')
    # list_filter = ('mobile','pacs_name','f_year','is_active')
    search_fields = ('mobile',)




@admin.register(Perpous)
class PerpousAdmin(admin.ModelAdmin):
    # Admin list view mein column dikhane ke liye
    list_display = ('ID', 'forWhy', 'fyear')
    search_fields = ('ID', 'forWhy')


@admin.register(VersionInfo)
class VersionAdmin(admin.ModelAdmin):
    # Admin list view mein column dikhane ke liye
    list_display = ('Description', 'Year','Version','Remark')
    search_fields = ('Description',)