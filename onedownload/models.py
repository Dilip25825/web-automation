from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class DownloadLink(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=50, default='General')
    categories = models.ManyToManyField(Category, related_name='download_links', blank=True)
    is_required = models.BooleanField(
        default=False,
        help_text='Show this file first and include it with every software category.',
    )
    drive_link = models.URLField(max_length=500)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_required', 'name']

    def __str__(self):
        return self.name
