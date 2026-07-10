from django import forms
from .models import Category, DownloadLink


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'New category name'}),
        }


class DownloadLinkForm(forms.ModelForm):
    category = forms.ChoiceField(
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = DownloadLink
        fields = ['name', 'description', 'category', 'drive_link', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Software name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short description'}),
            'drive_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Category.objects.get_or_create(name='General')
        categories = Category.objects.order_by('name')
        choices = [(category.name, category.name) for category in categories]
        self.fields['category'].choices = [('', 'Select category')] + choices

        if self.instance and self.instance.category:
            current = self.instance.category
            if current not in [choice[0] for choice in choices]:
                self.fields['category'].choices.append((current, current))

        if self.instance and self.instance.pk is None and not self.data:
            self.initial['category'] = 'General'
