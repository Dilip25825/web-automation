from django.db import models
from django.contrib.auth.models import User
from licensing.models import UserInfoData, tblPacsErp
from django.utils import timezone

class TaskCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    icon = models.CharField(max_length=50, blank=True, default='fa-tag')
    color = models.CharField(max_length=20, default='primary')
    
    def __str__(self):
        return self.name

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    ]
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    category = models.ForeignKey(TaskCategory, on_delete=models.SET_NULL, null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    deadline = models.DateTimeField(null=True, blank=True)
    reminder_at = models.DateTimeField(null=True, blank=True)
    
    # linked_pacs = models.ForeignKey(UserInfoData, on_delete=models.SET_NULL, null=True, blank=True)
    # linked_erp = models.ForeignKey(tblPacsErp, on_delete=models.SET_NULL, null=True, blank=True)
    
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tasks')
    
    reminder_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
   
    class Meta:
        ordering = ['-priority', 'deadline']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['deadline']),
            models.Index(fields=['priority']),
            models.Index(fields=['assigned_to', 'status']),  # Common filter
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def is_overdue(self):
        if self.deadline and self.status not in ['COMPLETED', 'CANCELLED']:
            return timezone.now() > self.deadline
        return False
    
    @property
    def days_until(self):
        if self.deadline:
            delta = self.deadline - timezone.now()
            return delta.days
        return None