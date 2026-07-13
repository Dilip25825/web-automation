from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from onedownload.models import DownloadLink


def home(request):
    download_links = DownloadLink.objects.filter(is_active=True).order_by('category', 'name')[:6]
    return render(request, 'core/home.html', {'download_links': download_links})


def pricing(request):
    return render(request, 'core/pricing.html')


@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')
