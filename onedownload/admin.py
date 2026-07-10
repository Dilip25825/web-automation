from django.contrib import admin
from .models import Category, DownloadLink


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)


@admin.register(DownloadLink)
class DownloadLinkAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'drive_link', 'is_active', 'updated_at')
    search_fields = ('name', 'description', 'category')
    list_filter = ('category', 'is_active')
