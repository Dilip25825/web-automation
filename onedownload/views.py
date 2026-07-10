from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, DownloadLinkForm
from .models import Category, DownloadLink


def _ensure_default_category():
    Category.objects.get_or_create(name='General')


def _get_categories():
    _ensure_default_category()
    return Category.objects.all().order_by('name')


def public_downloads(request):
    selected_category = request.GET.get('category', '').strip()
    links = DownloadLink.objects.filter(is_active=True)
    if selected_category:
        links = links.filter(category=selected_category)

    categories = _get_categories()
    return render(
        request,
        'onedownload/public_list.html',
        {'links': links, 'categories': categories, 'selected_category': selected_category},
    )


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
def manage_links(request):
    selected_category = request.GET.get('category', '').strip()
    links = DownloadLink.objects.all().order_by('category', 'name')
    if selected_category:
        links = links.filter(category=selected_category)

    categories = _get_categories()
    form = DownloadLinkForm()
    category_form = CategoryForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'save_link')

        if action == 'add_category':
            category_form = CategoryForm(request.POST)
            if category_form.is_valid():
                category_form.save()
                messages.success(request, 'Category added successfully.')
            return redirect('manage_links')

        if action == 'delete_category':
            category_id = request.POST.get('category_id')
            category = get_object_or_404(Category, pk=category_id)
            if category.name.lower() == 'general':
                messages.error(request, 'General category cannot be deleted.')
            else:
                DownloadLink.objects.filter(category=category.name).update(category='General')
                category.delete()
                messages.success(request, 'Category deleted successfully.')
            return redirect('manage_links')

        form = DownloadLinkForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Link added successfully.')
            return redirect('manage_links')

    return render(
        request,
        'onedownload/manage_links.html',
        {'links': links, 'form': form, 'category_form': category_form, 'edit_obj': None, 'categories': categories, 'selected_category': selected_category},
    )


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
def edit_link(request, pk):
    selected_category = request.GET.get('category', '').strip()
    link = get_object_or_404(DownloadLink, pk=pk)
    links = DownloadLink.objects.all().order_by('category', 'name')
    if selected_category:
        links = links.filter(category=selected_category)

    categories = _get_categories()
    category_form = CategoryForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'save_link')

        if action == 'add_category':
            category_form = CategoryForm(request.POST)
            if category_form.is_valid():
                category_form.save()
                messages.success(request, 'Category added successfully.')
            return redirect('manage_links')

        if action == 'delete_category':
            category_id = request.POST.get('category_id')
            category = get_object_or_404(Category, pk=category_id)
            if category.name.lower() == 'general':
                messages.error(request, 'General category cannot be deleted.')
            else:
                DownloadLink.objects.filter(category=category.name).update(category='General')
                category.delete()
                messages.success(request, 'Category deleted successfully.')
            return redirect('manage_links')

        form = DownloadLinkForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, 'Link updated successfully.')
            return redirect('manage_links')
    else:
        form = DownloadLinkForm(instance=link)

    return render(
        request,
        'onedownload/manage_links.html',
        {'links': links, 'form': form, 'category_form': category_form, 'edit_obj': link, 'categories': categories, 'selected_category': selected_category},
    )
