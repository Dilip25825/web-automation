from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'Software Admin'
admin.site.site_title = 'Software Admin'
admin.site.index_title = 'Software Admin Administration'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('licensing/', include('licensing.urls')),
    path('reminders/', include('reminders.urls')),
    path('khata/', include('khata.urls')),
    path('downloads/', include('onedownload.urls')),
    path('', include('core.urls')),
]