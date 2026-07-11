from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'description', 'category', 'priority', 'status', 'deadline', 'reminder_at', 'assigned_to']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Task title'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional description'}),
            'deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'reminder_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
