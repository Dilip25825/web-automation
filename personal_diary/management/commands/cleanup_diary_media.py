from datetime import timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from personal_diary import drive_storage
from personal_diary.models import DiaryMedia


class Command(BaseCommand):
    help = 'Permanently removes Drive objects for soft-deleted diary media older than --days.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        if options['days'] < 0:
            raise ValueError('--days must be zero or greater')
        cutoff = timezone.now() - timedelta(days=options['days'])
        items = DiaryMedia.objects.filter(deleted_at__lte=cutoff).order_by('pk')
        for item in items.iterator():
            if options['dry_run']:
                self.stdout.write(f'Would remove media #{item.pk}')
                continue
            drive_storage.delete(item.drive_file_id)
            with transaction.atomic():
                DiaryMedia.objects.filter(pk=item.pk, deleted_at__lte=cutoff).delete()
            self.stdout.write(f'Removed media #{item.pk}')
