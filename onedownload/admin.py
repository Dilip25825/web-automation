from django.contrib import admin

from .models import DownloadCatalogSnapshot


@admin.register(DownloadCatalogSnapshot)
class DownloadCatalogSnapshotAdmin(admin.ModelAdmin):
    list_display = ('file_count', 'category_count', 'synced_at', 'synced_by')
    readonly_fields = ('singleton_key', 'catalog', 'file_count', 'category_count', 'synced_at', 'synced_by')

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
