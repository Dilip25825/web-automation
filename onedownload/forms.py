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
    categories = forms.ModelMultipleChoiceField(
        queryset=Category.objects.none(),
        required=True,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = DownloadLink
        fields = ['name', 'description', 'categories', 'drive_link', 'is_required', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Software name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Short description'}),
            'drive_link': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://drive.google.com/...'}),
            'is_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        general, _ = Category.objects.get_or_create(name='General')
        self.fields['categories'].queryset = Category.objects.order_by('name')
        if self.instance and self.instance.pk is None and not self.data:
            self.initial['categories'] = [general.pk]

    def save(self, commit=True):
        instance = super().save(commit=False)
        selected_categories = self.cleaned_data.get('categories')
        if selected_categories:
            instance.category = selected_categories[0].name
        if commit:
            instance.save()
            self.save_m2m()
            if instance.is_required:
                instance.categories.set(Category.objects.all())
        return instance
