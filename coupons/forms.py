import re

from django import forms

from .models import Coupon


COUPON_PATTERN = re.compile(r'^SAVE(?P<amount>\d+)-[A-Z0-9]{5}-[A-Z0-9]{5}$')


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['coupon_code', 'discount_amount', 'status', 'used_by', 'remark']
        labels = {
            'coupon_code': 'Coupon Code',
            'discount_amount': 'Discount Amount',
            'used_by': 'Used By',
        }
        widgets = {
            'coupon_code': forms.TextInput(attrs={'placeholder': 'SAVE750-TFS1X-EFYTD', 'autocomplete': 'off'}),
            'discount_amount': forms.NumberInput(attrs={'min': 1, 'placeholder': '750'}),
            'status': forms.CheckboxInput(),
            'used_by': forms.TextInput(attrs={'placeholder': 'Customer ID / name (optional)'}),
            'remark': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional note'}),
        }

    def clean_coupon_code(self):
        code = (self.cleaned_data.get('coupon_code') or '').strip().upper()
        match = COUPON_PATTERN.fullmatch(code)
        if not match:
            raise forms.ValidationError('Use format SAVE750-TFS1X-EFYTD.')
        return code

    def clean_used_by(self):
        return (self.cleaned_data.get('used_by') or '').strip() or None

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('coupon_code')
        amount = cleaned.get('discount_amount')
        match = COUPON_PATTERN.fullmatch(code or '')
        if match and amount is not None and int(match.group('amount')) != amount:
            self.add_error('coupon_code', 'SAVE amount must match Discount Amount.')
        return cleaned

