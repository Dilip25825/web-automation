from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .forms import CategoryForm, DownloadLinkForm
from .models import Category, DownloadLink


def _is_ajax(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def _form_errors(form):
    return [message for errors in form.errors.values() for message in errors]


def _action_response(request, success, message, errors=None):
    if _is_ajax(request):
        return JsonResponse(
            {'success': success, 'message': message, 'errors': errors or []},
            status=200 if success else 400,
        )
    (messages.success if success else messages.error)(request, message)
    return redirect('downloads:public_downloads')


def _resource_icon(*values):
    """Choose an icon using the resource name, category and description."""
    text = ' '.join(str(value or '') for value in values).lower()
    mappings = [
        (('prerequisites pack', 'automation prerequisites'), 'fa-solid fa-gears', 'bg-violet-100 text-violet-700'),
        (('chromedriver', 'chrome driver'), 'fa-brands fa-chrome', 'bg-amber-100 text-amber-700'),
        (('.net', 'net35', 'framework'), 'fa-solid fa-code', 'bg-violet-100 text-violet-700'),
        (('pdf to excel',), 'fa-solid fa-file-export', 'bg-rose-100 text-rose-700'),
        (('excel', 'xlsx', 'spreadsheet'), 'fa-solid fa-file-excel', 'bg-emerald-100 text-emerald-700'),
        (('pmfby', 'fasal bima'), 'fa-solid fa-wheat-awn', 'bg-green-100 text-green-700'),
        (('jpg', 'jpeg', 'image compressor'), 'fa-solid fa-file-image', 'bg-pink-100 text-pink-700'),
        (('access database', 'database engine'), 'fa-solid fa-database', 'bg-red-100 text-red-700'),
        (('ms office', 'microsoft office'), 'fa-brands fa-microsoft', 'bg-orange-100 text-orange-700'),
        (('erp',), 'fa-solid fa-building-columns', 'bg-blue-100 text-blue-700'),
        (('krp', 'fasal rin', 'loan application'), 'fa-solid fa-hand-holding-dollar', 'bg-indigo-100 text-indigo-700'),
        (('interest',), 'fa-solid fa-percent', 'bg-cyan-100 text-cyan-700'),
        (('uparjan', 'loanentry'), 'fa-solid fa-tractor', 'bg-lime-100 text-lime-700'),
        (('ppacs', 'pacs'), 'fa-solid fa-landmark', 'bg-sky-100 text-sky-700'),
        (('delete',), 'fa-solid fa-trash-can', 'bg-rose-100 text-rose-700'),
        (('approval', 'approvel'), 'fa-solid fa-circle-check', 'bg-teal-100 text-teal-700'),
        (('driver', 'connector'), 'fa-solid fa-plug', 'bg-yellow-100 text-yellow-700'),
        (('zip', 'archive'), 'fa-solid fa-file-zipper', 'bg-purple-100 text-purple-700'),
        (('utility', 'tool'), 'fa-solid fa-screwdriver-wrench', 'bg-slate-100 text-slate-700'),
    ]
    for keywords, icon_class, colour_class in mappings:
        if any(keyword in text for keyword in keywords):
            return icon_class, colour_class
    return 'fa-solid fa-cloud-arrow-down', 'bg-indigo-100 text-indigo-700'


def _ensure_default_category():
    Category.objects.get_or_create(name='General')


def _get_categories():
    _ensure_default_category()
    return Category.objects.all().order_by('name')


def public_downloads(request):
    # Load active links once; category switching happens in the browser.
    links = (
        DownloadLink.objects.filter(is_active=True)
        .prefetch_related('categories')
        .order_by('-is_required', 'name')
    )
    categories = _get_categories()
    for link in links:
        link.icon_class, link.icon_colour_class = _resource_icon(link.name, link.category, link.description)
    for category in categories:
        category.icon_class, category.icon_colour_class = _resource_icon(category.name)
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
        return _action_response(request, True, 'Link added successfully.')
    else:
        return _action_response(request, False, 'Please correct the link details and try again.', _form_errors(form))


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def link_update(request, pk):
    link = get_object_or_404(DownloadLink, pk=pk)
    form = DownloadLinkForm(request.POST, instance=link)
    if form.is_valid():
        form.save()
        return _action_response(request, True, 'Link updated successfully.')
    else:
        return _action_response(request, False, 'Please correct the link details and try again.', _form_errors(form))


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def link_delete(request, pk):
    link = get_object_or_404(DownloadLink, pk=pk)
    link.delete()
    return _action_response(request, True, 'Link deleted successfully.')


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def category_create(request):
    form = CategoryForm(request.POST)
    if form.is_valid():
        category = form.save()
        for link in DownloadLink.objects.filter(is_required=True):
            link.categories.add(category)
        return _action_response(request, True, 'Category added successfully.')
    else:
        return _action_response(request, False, 'Please enter a unique category name.', _form_errors(form))


@user_passes_test(lambda user: user.is_active and user.is_superuser, login_url='/admin/login/')
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if category.name.lower() == 'general':
        return _action_response(request, False, 'General category cannot be deleted.')
    else:
        DownloadLink.objects.filter(category=category.name).update(category='General')
        category.delete()
        return _action_response(request, True, 'Category deleted successfully.')

