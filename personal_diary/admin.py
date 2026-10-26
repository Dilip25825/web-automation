from django.contrib import admin
from django.contrib.auth import get_user_model

from .models import DiaryAccessSettings


@admin.register(DiaryAccessSettings)
class DiaryAccessSettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'can_access_diary', 'storage_quota_bytes', 'updated_at')
    list_filter = ('can_access_diary',)
    search_fields = ('user__username', 'user__email')
    list_select_related = ('user',)
    fields = (
        'user', 'can_access_diary', 'storage_quota_bytes',
        'photo_max_upload_bytes', 'video_max_upload_bytes', 'audio_max_upload_bytes',
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'user':
            kwargs['queryset'] = get_user_model().objects.filter(is_active=True).order_by('username')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
