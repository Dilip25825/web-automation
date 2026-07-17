from django.contrib import admin
from django.urls import include, path
from django.http import HttpResponse
admin.site.site_header = 'Web Automation with Excel'
admin.site.site_title = 'Web Automation with Excel'
admin.site.index_title = 'Web Automation with Excel Administration'


def health_check(request):
    return HttpResponse("<h3>Health Check OK</h3>")

urlpatterns = [
    path("health/", health_check),
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('licensing/', include('licensing.urls')),
    path('reminders/', include('reminders.urls')),
    path('khata/', include('khata.urls')),
    path('downloads/', include('onedownload.urls')),
    path('', include('core.urls')),
]