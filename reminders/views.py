from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Task, TaskCategory
from .forms import TaskForm
from django.utils import timezone
from datetime import timedelta

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
    overdue = pending.filter(deadline__lt=today)
    due_soon = pending.filter(deadline__gte=today, deadline__lte=week_later)
    completed = tasks.filter(status='COMPLETED')
    
    # Pending tasks limit karein (already hai)
    pending_tasks = pending.order_by('-priority', 'deadline')[:20]
    
    context = {
        'tasks': pending_tasks,
        'overdue_count': overdue.count(),
        'due_soon_count': due_soon.count(),
        'pending_count': pending.count(),
        'completed_count': completed.count(),
        'form': TaskForm(),
    }
    return render(request, 'reminders/dashboard.html', context)



@login_required
def task_create(request):
    if request.method == 'POST':
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if not task.assigned_to:
                task.assigned_to = request.user
            task.save()
            messages.success(request, f'✅ Task "{task.title}" created!')
            return redirect('reminders:dashboard')
        messages.error(request, 'Please correct the task details and try again.')
        return redirect('reminders:dashboard')
    return redirect('reminders:dashboard')

@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, f'✅ Task "{task.title}" updated!')
            return redirect('reminders:dashboard')
    else:
        form = TaskForm(instance=task)
    return render(request, 'reminders/task_form.html', {'form': form, 'action': 'Update'})

@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if request.method == 'POST':
        task.delete()
        messages.warning(request, f'🗑️ Task "{task.title}" deleted.')
        return redirect('reminders:dashboard')
    return redirect('reminders:dashboard')

@login_required
def task_toggle_status(request, pk):
    task = get_object_or_404(Task, pk=pk)
    status_cycle = {'PENDING': 'IN_PROGRESS', 'IN_PROGRESS': 'COMPLETED', 'COMPLETED': 'PENDING'}
    task.status = status_cycle.get(task.status, 'PENDING')
    task.save()
    messages.info(request, f'🔄 Task "{task.title}" status changed to {task.get_status_display()}')
    return redirect('reminders:dashboard')


# ========== CATEGORY MANAGEMENT VIEWS ==========

@login_required
def category_list(request):
    """List all categories with add/delete options"""
    categories = TaskCategory.objects.all().order_by('name')
    return render(request, 'reminders/category_list.html', {'categories': categories})

@login_required
def category_create(request):
    """Add a new category via AJAX or normal POST"""
    if request.method == 'POST':
        name = request.POST.get('name')
        icon = request.POST.get('icon', 'fa-tag')
        color = request.POST.get('color', 'primary')
        
        if name:
            # Duplicate check
            if TaskCategory.objects.filter(name__iexact=name).exists():
                messages.error(request, f'❌ Category "{name}" already exists!')
            else:
                TaskCategory.objects.create(name=name, icon=icon, color=color)
                messages.success(request, f'✅ Category "{name}" created successfully!')
        else:
            messages.error(request, '❌ Category name is required.')
        
        return redirect('reminders:category_list')
    
    return render(request, 'reminders/category_form.html')

@login_required
def category_delete(request, pk):
    """Delete a category (only if not in use)"""
    category = get_object_or_404(TaskCategory, pk=pk)
    
    # Check if any task is using this category
    if Task.objects.filter(category=category).exists():
        messages.error(request, f'❌ Cannot delete "{category.name}" because it is assigned to existing tasks!')
        return redirect('reminders:category_list')
    
    if request.method == 'POST':
        category_name = category.name
        category.delete()
        messages.success(request, f'🗑️ Category "{category_name}" deleted successfully!')
        return redirect('reminders:category_list')
    
    return redirect('reminders:category_list')