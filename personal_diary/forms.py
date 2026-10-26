from django import forms
from django.utils import timezone

from .models import DiaryEntry, DiaryTag, ImportantEvent


class DiaryEntryForm(forms.ModelForm):
    tags_text = forms.CharField(required=False, max_length=400, help_text='Comma se alag tags likhein, jaise Family, Travel')

    class Meta:
        model = DiaryEntry
        fields = ('entry_date', 'entry_time', 'title', 'content', 'mood', 'mood_note', 'category', 'location', 'weather', 'is_draft', 'is_favorite', 'is_locked')
        widgets = {
            'entry_date': forms.DateInput(attrs={'type': 'date'}),
            'entry_time': forms.TimeInput(attrs={'type': 'time'}),
            'content': forms.Textarea(attrs={'rows': 10, 'placeholder': 'Aaj ke din ke baare me likhein…'}),
            'mood_note': forms.TextInput(attrs={'placeholder': 'Mood ka reason (optional)'}),
            'location': forms.TextInput(attrs={'placeholder': 'Jagah (optional)'}),
            'weather': forms.TextInput(attrs={'placeholder': 'Mausam (optional)'}),
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['entry_date'].initial = timezone.localdate()
            self.fields['entry_time'].initial = timezone.localtime().strftime('%H:%M')
        else:
            self.fields['tags_text'].initial = ', '.join(self.instance.tags.values_list('name', flat=True))

    def clean_tags_text(self):
        tags = []
        for raw_tag in self.cleaned_data['tags_text'].split(','):
            name = ' '.join(raw_tag.split())
            if name and name.casefold() not in {item.casefold() for item in tags}:
                tags.append(name[:40])
        return tags

    def save(self, commit=True):
        entry = super().save(commit=False)
        if commit:
            entry.save()
            tag_objects = [DiaryTag.objects.get_or_create(user=self.user, name=name)[0] for name in self.cleaned_data['tags_text']]
            entry.tags.set(tag_objects)
        return entry


class ImportantEventForm(forms.ModelForm):
    class Meta:
        model = ImportantEvent
        fields = ('title', 'event_date', 'event_type', 'note')
        widgets = {'event_date': forms.DateInput(attrs={'type': 'date'}), 'note': forms.Textarea(attrs={'rows': 4})}
