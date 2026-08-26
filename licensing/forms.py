import json
import re

from django import forms
from .models import UserInfoData, tblPacsErp,Perpous,tblUPI


class PurposeSettingsForm(forms.ModelForm):
    class Meta:
        model = Perpous
        fields = ['forWhy', 'fyear']
        widgets = {
            'forWhy': forms.TextInput(attrs={'placeholder': 'Example: PMFBY', 'maxlength': '30'}),
            'fyear': forms.TextInput(attrs={'placeholder': 'Example: Kharif 2026'}),
        }

    def clean_forWhy(self):
        value = ' '.join((self.cleaned_data.get('forWhy') or '').split())
        if not value:
            raise forms.ValidationError('Purpose is required.')
        if len(value) > 30:
            raise forms.ValidationError('Purpose cannot exceed 30 characters.')
        return value

    def clean_fyear(self):
        value = ' '.join((self.cleaned_data.get('fyear') or '').split())
        if not value:
            raise forms.ValidationError('Financial year is required.')
        return value

    def clean(self):
        cleaned = super().clean()
        purpose = cleaned.get('forWhy')
        year = cleaned.get('fyear')
        if purpose and year:
            duplicate = Perpous.objects.filter(forWhy__iexact=purpose, fyear__iexact=year)
            if self.instance and self.instance.pk:
                duplicate = duplicate.exclude(pk=self.instance.pk)
            if duplicate.exists():
                raise forms.ValidationError('This Purpose and Financial Year already exists.')
        return cleaned


class UpiSettingsForm(forms.ModelForm):
    isActive = forms.BooleanField(label='Active UPI', required=False)

    class Meta:
        model = tblUPI
        fields = ['upiID', 'Remark', 'isActive']
        widgets = {
            'upiID': forms.TextInput(attrs={'placeholder': 'Example: business@bank', 'maxlength': '100'}),
            'Remark': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional note', 'maxlength': '255'}),
        }

    def clean_upiID(self):
        value = (self.cleaned_data.get('upiID') or '').strip()
        if not value:
            raise forms.ValidationError('UPI ID is required.')
        if len(value) > 100 or not re.fullmatch(r'[A-Za-z0-9._-]{2,}@[A-Za-z0-9.-]{2,}', value):
            raise forms.ValidationError('Enter a valid UPI ID, for example business@bank.')
        duplicate = tblUPI.objects.filter(upiID__iexact=value)
        if self.instance and self.instance.pk:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise forms.ValidationError('This UPI ID already exists.')
        return value

    def clean_Remark(self):
        return (self.cleaned_data.get('Remark') or '').strip()


class UpiQrForm(forms.Form):
    upi_id = forms.IntegerField(label='UPI ID', min_value=1)
    amount = forms.DecimalField(
        label='Payment Amount', min_value=0.01, max_value=99999, max_digits=7, decimal_places=2,
    )
    remark = forms.CharField(label='Remark', max_length=100, strip=True)

    def clean_remark(self):
        return ' '.join(self.cleaned_data['remark'].split())


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
            'is_pri', 'entry_count', 'limit_of_entrys', 'accepte_by',
            'razorpay_payment_link_id', 'razorpay_payment_id',
            'razorpay_reference_id', 'razorpay_payment_status',
        ]
        labels = {
            'razorpay_payment_link_id': 'Razorpay Payment Link ID',
            'razorpay_payment_id': 'Razorpay Payment ID',
            'razorpay_reference_id': 'Razorpay Reference ID',
            'razorpay_payment_status': 'Razorpay Payment Status',
            'entry_count': 'Uploaded Entries',
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
            'entry_count': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'min': '0'}),
            'limit_of_entrys': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'accepte_by': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. Admin'}),
        }

    def clean_entry_count(self):
        value = self.cleaned_data.get('entry_count')
        if value is not None and value < 0:
            raise forms.ValidationError('Uploaded Entries cannot be negative.')
        return value or 0

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
                .order_by('forWhy', 'pk')
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
        fields = ['erp_id', 'pacs_name', 'brach', 'dist', 'state', 'operator_mobile', 'amount', 'current_amount', 'payment_status', 'expiry_date', 'utr_number', 'accepte_by', 'activation_date', 'razorpay_payment_link_id', 'razorpay_payment_id', 'razorpay_reference_id', 'razorpay_payment_status', 'remark']

        labels = {
            'current_amount': 'Current Amount',
            'razorpay_payment_link_id': 'Razorpay Payment Link ID',
            'razorpay_payment_id': 'Razorpay Payment ID',
            'razorpay_reference_id': 'Razorpay Reference ID',
            'razorpay_payment_status': 'Razorpay Payment Status',
        }

        widgets = {
            'erp_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'pacs_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'brach': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'dist': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'state': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'operator_mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'current_amount': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'min': '0'}),
            'payment_status': forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'date'}),
            'utr_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'accepte_by': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'activation_date': forms.DateTimeInput(format='%Y-%m-%dT%H:%M', attrs={'class': 'form-control bg-dark text-light border-secondary', 'type': 'datetime-local'}),
            'razorpay_payment_link_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_payment_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_reference_id': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'razorpay_payment_status': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),

            'remark': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['activation_date'].input_formats = ['%Y-%m-%dT%H:%M']
        if not self.instance.pk:
            self.fields['current_amount'].initial = 4500

class PublicPacsErpRegistrationForm(forms.Form):
    erp_id = forms.CharField(label='ERP User ID', max_length=100, widget=forms.TextInput(attrs={'placeholder': 'ERP login/user ID', 'autocomplete': 'off'}))
    pacs_name = forms.CharField(label='PACS Name / Bank Name', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'PACS / Bank name'}))
    brach = forms.CharField(label='Branch', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'Branch name'}))
    dist = forms.CharField(label='District', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'District'}))
    state = forms.CharField(label='State', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'State'}))
    operator_mobile = forms.CharField(label='Operator Mobile', max_length=10, widget=forms.TextInput(attrs={'readonly': 'readonly', 'inputmode': 'numeric'}))

    def clean_operator_mobile(self):
        value = ''.join(filter(str.isdigit, self.cleaned_data['operator_mobile']))
        if len(value) != 10 or value[0] not in '6789':
            raise forms.ValidationError('Valid 10 digit Indian mobile required hai.')
        return value


class PublicPmfbyRegistrationForm(forms.Form):
    mobile = forms.CharField(label='Mobile / Login Mobile ID', max_length=10, widget=forms.TextInput(attrs={'readonly': 'readonly', 'inputmode': 'numeric'}))
    pacs_name = forms.CharField(label='PACS Name / Bank Name', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'PACS / Bank name'}))
    brach = forms.CharField(label='Branch', max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Branch name'}))
    dist = forms.CharField(label='District', max_length=100, widget=forms.TextInput(attrs={'placeholder': 'District'}))
    state = forms.CharField(label='State', max_length=50, widget=forms.TextInput(attrs={'placeholder': 'e.g. MADHYA PRADESH'}))
    operator_mobile = forms.CharField(label='Operator Mobile', max_length=10, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '10 digit operator mobile'}))
    service = forms.CharField(label='Service', initial='PMFBY', disabled=True)




    financial_year = forms.ChoiceField(label='Financial Year', choices=[])


    def __init__(self, *args, financial_years=None, service_name='PMFBY', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service'].initial = service_name
        self.fields['financial_year'].choices = [('', '-- Select Financial Year --')] + [
            (year, year) for year in (financial_years or [])
        ]

    @staticmethod
    def _clean_mobile(value):
        digits = ''.join(filter(str.isdigit, value))
        if len(digits) != 10 or digits[0] not in '6789':
            raise forms.ValidationError('Valid 10 digit Indian mobile required hai.')
        return digits

    def clean_mobile(self):
        return self._clean_mobile(self.cleaned_data['mobile'])

    def clean_operator_mobile(self):
        return self._clean_mobile(self.cleaned_data['operator_mobile'])

class PublicFasalRinRegistrationForm(forms.Form):
    mobile = forms.CharField(label='Mobile / Login Mobile ID', max_length=10, widget=forms.TextInput(attrs={'readonly': 'readonly', 'inputmode': 'numeric'}))
    pacs_name = forms.CharField(label='PACS Name / Bank Name', max_length=255, widget=forms.TextInput(attrs={'placeholder': 'PACS / Bank name'}))
    brach = forms.CharField(label='Branch', max_length=100, widget=forms.TextInput(attrs={'placeholder': 'Branch name'}))
    dist = forms.CharField(label='District', max_length=100, widget=forms.TextInput(attrs={'placeholder': 'District'}))
    state = forms.CharField(label='State', max_length=50, widget=forms.TextInput(attrs={'placeholder': 'e.g. MADHYA PRADESH'}))
    operator_mobile = forms.CharField(label='Operator Mobile', max_length=10, widget=forms.TextInput(attrs={'inputmode': 'numeric', 'placeholder': '10 digit operator mobile'}))
    service = forms.CharField(label='Service', initial='FASAL RIN', disabled=True)
    work_type_name = forms.CharField(label='Upload Type', disabled=True)
    financial_year = forms.ChoiceField(label='Financial Year', choices=[])

    def __init__(self, *args, financial_years=None, work_type_name='', **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['work_type_name'].initial = work_type_name
        self.fields['financial_year'].choices = [('', '-- Select Financial Year --')] + [
            (year, year) for year in (financial_years or [])
        ]

    @staticmethod
    def _clean_mobile(value):
        digits = ''.join(filter(str.isdigit, value))
        if len(digits) != 10 or digits[0] not in '6789':
            raise forms.ValidationError('Valid 10 digit Indian mobile required hai.')
        return digits

    def clean_mobile(self):
        return self._clean_mobile(self.cleaned_data['mobile'])

    def clean_operator_mobile(self):
        return self._clean_mobile(self.cleaned_data['operator_mobile'])
