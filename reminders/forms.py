from django import forms
from .models import Task

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        # ✅ REMOVED: 'linked_pacs', 'linked_erp' (isliye ye fields nahi dikhengi)
        fields = ['title', 'description', 'category', 'priority', 'status', 
                  'deadline', 'reminder_at', 'assigned_to']
        
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'description': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
            'priority': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
            'status': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
            'deadline': forms.DateTimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'datetime-local'}),
            'reminder_at': forms.DateTimeInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'datetime-local'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        }