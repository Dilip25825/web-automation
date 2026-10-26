from django.conf import settings
from django.db import models
from django.utils import timezone


def current_local_time():
    return timezone.localtime().time().replace(microsecond=0)


class DiaryAccessSettings(models.Model):
    """Administrator-managed entitlement for one user's private diary."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='diary_access_settings',
    )
    can_access_diary = models.BooleanField(default=False)
    storage_quota_bytes = models.PositiveBigIntegerField(
        null=True,
        blank=True,
        help_text='Blank means the future application default quota will be used.',
    )
    photo_max_upload_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    video_max_upload_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    audio_max_upload_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Diary access setting'
        verbose_name_plural = 'Diary access settings'

    def __str__(self):
        return f'{self.user} — {"enabled" if self.can_access_diary else "disabled"}'


class DiaryTag(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diary_tags')
    name = models.CharField(max_length=40)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('user', 'name'), name='unique_diary_tag_per_user')]
        ordering = ('name',)

    def __str__(self):
        return self.name


class DiaryEntry(models.Model):
    class Mood(models.TextChoices):
        VERY_HAPPY = 'VERY_HAPPY', 'बहुत खुश'
        HAPPY = 'HAPPY', 'खुश'
        NORMAL = 'NORMAL', 'सामान्य'
        SAD = 'SAD', 'उदास'
        ANGRY = 'ANGRY', 'गुस्सा'
        EXCITED = 'EXCITED', 'उत्साहित'
        TIRED = 'TIRED', 'थका हुआ'

    class Category(models.TextChoices):
        DAILY_LIFE = 'DAILY_LIFE', 'दैनिक जीवन'
        PERSONAL_THOUGHTS = 'PERSONAL_THOUGHTS', 'व्यक्तिगत विचार'
        FAMILY = 'FAMILY', 'परिवार'
        SPECIAL_MEMORIES = 'SPECIAL_MEMORIES', 'विशेष यादें'
        TRAVEL = 'TRAVEL', 'यात्रा'
        FESTIVALS = 'FESTIVALS', 'त्योहार'
        CELEBRATIONS = 'CELEBRATIONS', 'उत्सव'
        HEALTH = 'HEALTH', 'स्वास्थ्य और कल्याण'
        GOALS = 'GOALS', 'व्यक्तिगत लक्ष्य'
        OTHER = 'OTHER', 'अन्य'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diary_entries')
    entry_date = models.DateField(default=timezone.localdate, db_index=True)
    entry_time = models.TimeField(default=current_local_time)
    title = models.CharField(max_length=180)
    content = models.TextField()
    mood = models.CharField(max_length=16, choices=Mood.choices, default=Mood.NORMAL)
    mood_note = models.CharField(max_length=280, blank=True)
    category = models.CharField(max_length=24, choices=Category.choices, default=Category.DAILY_LIFE)
    location = models.CharField(max_length=160, blank=True)
    weather = models.CharField(max_length=100, blank=True)
    is_draft = models.BooleanField(default=False, db_index=True)
    is_favorite = models.BooleanField(default=False, db_index=True)
    is_locked = models.BooleanField(default=False)
    tags = models.ManyToManyField(DiaryTag, blank=True, related_name='entries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ('-entry_date', '-entry_time', '-id')
        indexes = [models.Index(fields=('user', 'entry_date'), name='diary_entry_user_date_idx')]

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=('deleted_at',))

    def __str__(self):
        return f'{self.entry_date} — {self.title}'


class DiaryMedia(models.Model):
    class MediaType(models.TextChoices):
        PHOTO = 'PHOTO', 'Photo'
        VIDEO = 'VIDEO', 'Video'
        AUDIO = 'AUDIO', 'Audio'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diary_media')
    entry = models.ForeignKey(DiaryEntry, on_delete=models.CASCADE, related_name='media')
    drive_file_id = models.CharField(max_length=255, unique=True)
    drive_parent_folder_id = models.CharField(max_length=255)
    original_filename = models.CharField(max_length=255)
    media_type = models.CharField(max_length=8, choices=MediaType.choices)
    mime_type = models.CharField(max_length=100)
    file_size = models.PositiveBigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=('user', 'deleted_at'), name='diary_media_user_deleted_idx')]

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save(update_fields=('deleted_at',))


class ImportantEvent(models.Model):
    class EventType(models.TextChoices):
        BIRTHDAY = 'BIRTHDAY', 'Birthday'
        ANNIVERSARY = 'ANNIVERSARY', 'Anniversary'
        FESTIVAL = 'FESTIVAL', 'Festival'
        TRAVEL = 'TRAVEL', 'Travel'
        FAMILY = 'FAMILY', 'Family'
        MILESTONE = 'MILESTONE', 'Milestone'
        OTHER = 'OTHER', 'Other'
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diary_events')
    title = models.CharField(max_length=180)
    event_date = models.DateField(db_index=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices, default=EventType.OTHER)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('event_date', 'title')


class DiaryPreference(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='diary_preference')
    on_this_day_enabled = models.BooleanField(default=True)
    pin_hash = models.CharField(max_length=256, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
