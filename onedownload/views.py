from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import CategoryForm, DownloadLinkForm
from .models import Category, DownloadLink


def _ensure_default_category():
    Category.objects.get_or_create(name='General')


def _get_categories():
    _ensure_default_category()
    return Category.objects.all().order_by('name')


def public_downloads(request):
    # Load active links once; category switching happens in the browser.
    links = DownloadLink.objects.filter(is_active=True).order_by('category', 'name')
    categories = _get_categories()
    context = {'links': links, 'categories': categories}
    if request.user.is_authenticated and request.user.is_superuser:
        context['link_form'] = DownloadLinkForm()
        context['category_form'] = CategoryForm()
    return render(request, 'onedownload/public_list.html', context)


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def link_create(request):
    form = DownloadLinkForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Link added successfully.')
    else:
        messages.error(request, 'Please correct the link details and try again.')
    return redirect('downloads:public_downloads')


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def link_update(request, pk):
    link = get_object_or_404(DownloadLink, pk=pk)
    form = DownloadLinkForm(request.POST, instance=link)
    if form.is_valid():
        form.save()
        messages.success(request, 'Link updated successfully.')
    else:
        messages.error(request, 'Please correct the link details and try again.')
    return redirect('downloads:public_downloads')


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def link_delete(request, pk):
    link = get_object_or_404(DownloadLink, pk=pk)
    link.delete()
    messages.success(request, 'Link deleted successfully.')
    return redirect('downloads:public_downloads')


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def category_create(request):
    form = CategoryForm(request.POST)
    if form.is_valid():
        form.save()
        messages.success(request, 'Category added successfully.')
    else:
        messages.error(request, 'Please enter a unique category name.')
    return redirect('downloads:public_downloads')


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.name.lower() == 'general':
        messages.error(request, 'General category cannot be deleted.')
    else:
        DownloadLink.objects.filter(category=category.name).update(category='General')
        category.delete()
        messages.success(request, 'Category deleted successfully.')
    return redirect('downloads:public_downloads')

