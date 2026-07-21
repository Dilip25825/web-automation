import re

from django import forms

from .models import Coupon


COUPON_PATTERN = re.compile(r'^CPN-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{6}$')


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
            'coupon_code': forms.TextInput(attrs={'placeholder': 'CPN-ABCDE-FGHIJ-KLMNO-PQRST-UVWXYZ', 'autocomplete': 'off'}),
            'discount_amount': forms.NumberInput(attrs={'min': 1, 'placeholder': '750'}),
            'status': forms.CheckboxInput(),
            'used_by': forms.TextInput(attrs={'placeholder': 'Customer ID / name (optional)'}),
            'remark': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional note'}),
        }

    def clean_coupon_code(self):
        code = (self.cleaned_data.get('coupon_code') or '').strip().upper()
        if not COUPON_PATTERN.fullmatch(code):
            raise forms.ValidationError('Use the generated 128-bit coupon format.')
        return code

    def clean_used_by(self):
        return (self.cleaned_data.get('used_by') or '').strip() or None
