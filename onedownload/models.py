from django.conf import settings
from django.db import models


class DownloadCatalogSnapshot(models.Model):
    singleton_key = models.PositiveSmallIntegerField(default=1, unique=True, editable=False)
    catalog = models.JSONField(default=dict)
    file_count = models.PositiveIntegerField(default=0)
    category_count = models.PositiveIntegerField(default=0)
    synced_at = models.DateTimeField(null=True, blank=True)
    synced_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='download_catalog_syncs',
    )

    class Meta:
        verbose_name = 'Download catalog snapshot'
        verbose_name_plural = 'Download catalog snapshot'

    def __str__(self):
        return f'Download catalog ({self.file_count} files)'
