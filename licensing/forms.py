import json

from django import forms
from .models import UserInfoData, tblPacsErp,Perpous,tblUPI

class UserInfoForm(forms.ModelForm):
    for_whys = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        required=False,
    )
    f_year = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        required=False,
    )

    class Meta:
        model = UserInfoData
        fields = [
            'mobile', 'pacs_name', 'brach', 'dist', 'state', 'operator_mobile',
            'payment_status', 'amount', 'utr_number', 'for_whys', 'f_year',
            'is_pri', 'limit_of_entrys', 'accepte_by',
            'razorpay_payment_link_id', 'razorpay_payment_id',
            'razorpay_reference_id', 'razorpay_payment_status',
        ]
        labels = {
            'razorpay_payment_link_id': 'Razorpay Payment Link ID',
            'razorpay_payment_id': 'Razorpay Payment ID',
            'razorpay_reference_id': 'Razorpay Reference ID',
            'razorpay_payment_status': 'Razorpay Payment Status',
        }
        widgets = {
            'mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'pacs_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'brach': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'dist': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'state': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. MADHYA PRADESH'}),
            'operator_mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'payment_status': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'utr_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_payment_link_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_payment_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_reference_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_payment_status': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'is_pri': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'limit_of_entrys': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'accepte_by': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. Admin'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            purpose_rows = (
                Perpous.objects.exclude(forWhy__isnull=True)
                .exclude(forWhy='')
                .exclude(forWhy__icontains='Delete')
                .exclude(fyear__isnull=True)
                .exclude(fyear='')
                .values_list('forWhy', 'fyear')
                .order_by('forWhy', 'id')
            )
            purpose_years = {}
            for purpose, financial_year in purpose_rows:
                purpose = str(purpose).strip()
                financial_year = str(financial_year).strip()
                years = purpose_years.setdefault(purpose, [])
                if financial_year not in years:
                    years.append(financial_year)

            self.fields['for_whys'].choices = [('', '-- Select Purpose --')] + [
                (purpose, purpose) for purpose in purpose_years
            ]
            selected_purpose = (
                self.data.get(self.add_prefix('for_whys'))
                if self.is_bound
                else (getattr(self.instance, 'for_whys', '') or self.initial.get('for_whys', ''))
            )
            selected_year = (
                self.data.get(self.add_prefix('f_year'))
                if self.is_bound
                else (getattr(self.instance, 'f_year', '') or self.initial.get('f_year', ''))
            )
            year_choices = [('', '-- Select Financial Year --')]
            year_choices.extend(
                (financial_year, financial_year)
                for financial_year in purpose_years.get(selected_purpose, [])
            )
            if selected_year and selected_year not in dict(year_choices):
                year_choices.append((selected_year, selected_year))
            self.fields['f_year'].choices = year_choices
            self.fields['f_year'].widget.attrs['data-purpose-years'] = json.dumps(
                purpose_years,
                ensure_ascii=False,
            )
        except Exception:
            self.fields['for_whys'].choices = [('', '-- Select Purpose --')]
            self.fields['f_year'].choices = [('', '-- Select Financial Year --')]

class PacsErpForm(forms.ModelForm):
    class Meta:
        model = tblPacsErp
        # PacsErpForm bilkul sahi hai, isey waisa hi rehne dein
        fields = ['erp_id', 'pacs_name', 'brach', 'dist', 'state', 'operator_mobile', 'amount', 'payment_status', 'expiry_date', 'utr_number', 'accepte_by', 'activation_date', 'remark']

        widgets = {
            'erp_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'pacs_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'brach': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'dist': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'state': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'operator_mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'payment_status': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
            'utr_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'accepte_by': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'activation_date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'datetime-local'}),

            'remark': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activation_date'].input_formats = ['%Y-%m-%dT%H:%M']
