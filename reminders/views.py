from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Task, TaskCategory
from .forms import TaskForm
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.http import JsonResponse
STATS_CACHE_VERSION_KEY = 'reminders:dashboard-stats-version'


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
    return redirect('reminders:dashboard')


def _dashboard_stats_cache_key(user):
    version = cache.get_or_set(STATS_CACHE_VERSION_KEY, 1, None)
    scope = 'all' if user.is_superuser else f'user-{user.pk}'
    return f'reminders:dashboard-stats:{version}:{scope}'


def _invalidate_dashboard_stats_cache():
    """Make all cached dashboard counts obsolete after a task change."""
    version = cache.get_or_set(STATS_CACHE_VERSION_KEY, 1, None)
    cache.set(STATS_CACHE_VERSION_KEY, version + 1, None)

@login_required
def dashboard(request):
    today = timezone.now()
    week_later = today + timedelta(days=7)
    
    if request.user.is_superuser:
        tasks = Task.objects.all()
    else:
        tasks = Task.objects.filter(assigned_to=request.user)
    
    # ========== 🚀 OPTIMIZATION: select_related use karein ==========
    # Ek hi query mein saare related tables (category, user, pacs) join kar lein
    tasks = tasks.select_related(
        'category', 
        'assigned_to', 
        'created_by',  )
    
    pending = tasks.filter(status__in=['PENDING', 'IN_PROGRESS'])
    active_filter = request.GET.get('filter', 'pending')
    filters = {
        'pending': {
            'tasks': pending,
            'label': 'Pending Tasks',
            'description': 'Tasks that are pending or currently in progress.',
        },
        'overdue': {
            'tasks': pending.filter(deadline__lt=today),
            'label': 'Overdue Tasks',
            'description': 'Active tasks whose deadline has already passed.',
        },
        'due_soon': {
            'tasks': pending.filter(deadline__gte=today, deadline__lte=week_later),
            'label': 'Due This Week',
            'description': 'Active tasks due within the next seven days.',
        },
        'completed': {
            'tasks': tasks.filter(status='COMPLETED'),
            'label': 'Completed Tasks',
            'description': 'Tasks that have been marked as completed.',
        },
    }
    if active_filter not in filters:
        active_filter = 'pending'

    selected_tasks = filters[active_filter]['tasks'].order_by('-priority', 'deadline')

    stats_cache_key = _dashboard_stats_cache_key(request.user)
    stats = cache.get(stats_cache_key)
    if stats is None:
        stats = tasks.aggregate(
            overdue_count=Count(
                'id',
                filter=Q(status__in=['PENDING', 'IN_PROGRESS'], deadline__lt=today),
            ),
            due_soon_count=Count(
                'id',
                filter=Q(
                    status__in=['PENDING', 'IN_PROGRESS'],
                    deadline__gte=today,
                    deadline__lte=week_later,
                ),
            ),
            pending_count=Count('id', filter=Q(status__in=['PENDING', 'IN_PROGRESS'])),
            completed_count=Count('id', filter=Q(status='COMPLETED')),
        )
        cache.set(stats_cache_key, stats, timeout=60)

    partial_dashboard = request.GET.get('ajax_partial') == '1'
    context = {
        'tasks': selected_tasks,
        'active_filter': active_filter,
        'table_title': filters[active_filter]['label'],
        'table_description': filters[active_filter]['description'],
        'selected_count': selected_tasks.count(),
        'partial_dashboard': partial_dashboard,
        **stats,
    }
    if not partial_dashboard:
        context['form'] = TaskForm()
        context['categories'] = TaskCategory.objects.annotate(
            task_count=Count('task')
        ).order_by('name')
    return render(request, 'reminders/dashboard.html', context)



@login_required
@require_POST
def task_create(request):
    form = TaskForm(request.POST)
    if form.is_valid():
        task = form.save(commit=False)
        task.created_by = request.user
        if not task.assigned_to:
            task.assigned_to = request.user
        task.save()
        _invalidate_dashboard_stats_cache()
        return _action_response(request, True, f'Task "{task.title}" created!')
    return _action_response(
        request, False, 'Please correct the task details and try again.', _form_errors(form)
    )


@login_required
@require_POST
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    form = TaskForm(request.POST, instance=task)
    if form.is_valid():
        form.save()
        _invalidate_dashboard_stats_cache()
        return _action_response(request, True, f'Task "{task.title}" updated!')
    return _action_response(
        request, False, 'Please correct the task details and try again.', _form_errors(form)
    )


@login_required
@require_POST
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    title = task.title
    task.delete()
    _invalidate_dashboard_stats_cache()
    return _action_response(request, True, f'Task "{title}" deleted.')


@login_required
@require_POST
def task_toggle_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    status_cycle = {'PENDING': 'IN_PROGRESS', 'IN_PROGRESS': 'COMPLETED', 'COMPLETED': 'PENDING'}
    task.status = status_cycle.get(task.status, 'PENDING')
    task.save()
    _invalidate_dashboard_stats_cache()
    return _action_response(
        request, True, f'Task "{task.title}" status changed to {task.get_status_display()}.'
    )


# ========== CATEGORY MANAGEMENT VIEWS ==========

@login_required
@require_POST
def category_create(request):
    name = request.POST.get('name', '').strip()
    icon = request.POST.get('icon', 'fa-tag').strip() or 'fa-tag'
    color = request.POST.get('color', 'indigo').strip() or 'indigo'

    if not name:
        return _action_response(request, False, 'Category name is required.')
    if TaskCategory.objects.filter(name__iexact=name).exists():
        return _action_response(request, False, f'Category "{name}" already exists!')
    TaskCategory.objects.create(name=name, icon=icon, color=color)
    return _action_response(request, True, f'Category "{name}" created successfully!')


@login_required
@require_POST
def category_update(request, pk):
    category = get_object_or_404(TaskCategory, pk=pk)
    name = request.POST.get('name', '').strip()
    icon = request.POST.get('icon', 'fa-tag').strip() or 'fa-tag'
    color = request.POST.get('color', 'indigo').strip() or 'indigo'

    if not name:
        return _action_response(request, False, 'Category name is required.')
    if TaskCategory.objects.filter(name__iexact=name).exclude(pk=category.pk).exists():
        return _action_response(request, False, f'Category "{name}" already exists!')
    category.name = name
    category.icon = icon
    category.color = color
    category.save(update_fields=['name', 'icon', 'color'])
    return _action_response(request, True, f'Category "{name}" updated successfully!')


@login_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(TaskCategory, pk=pk)
    if Task.objects.filter(category=category).exists():
        return _action_response(
            request, False, f'Cannot delete "{category.name}" because it is assigned to existing tasks!'
        )
    category_name = category.name
    category.delete()
    return _action_response(request, True, f'Category "{category_name}" deleted successfully!')
