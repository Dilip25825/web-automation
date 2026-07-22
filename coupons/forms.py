import re

from django import forms

from .models import Coupon


COUPON_PATTERN = re.compile(r'^C(?P<amount>\d+)-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{5}-[A-Z2-7]{6}$')


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['coupon_code', 'discount_amount', 'status', 'used_by', 'remark']
        labels = {
            'coupon_code': 'Coupon Code',
            'discount_amount': 'Discount Amount',
            'used_by': 'Assigned / Used By',
        }
        widgets = {
            'coupon_code': forms.TextInput(attrs={'placeholder': 'C750-ABCDE-FGHIJ-KLMNO-PQRST-UVWXYZ', 'autocomplete': 'off'}),
            'discount_amount': forms.NumberInput(attrs={'min': 1, 'placeholder': '750'}),
            'status': forms.CheckboxInput(),
            'used_by': forms.TextInput(attrs={'placeholder': 'UserInfo ID (optional)', 'inputmode': 'numeric'}),
            'remark': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Optional note'}),
        }

    def clean_coupon_code(self):
        code = (self.cleaned_data.get('coupon_code') or '').strip().upper()
        match = COUPON_PATTERN.fullmatch(code)
        if not match:
            raise forms.ValidationError('Use the generated discount-prefixed 128-bit coupon format.')
        return code

    def clean_used_by(self):
        user_info_id = (self.cleaned_data.get('used_by') or '').strip()
        if not user_info_id:
            return None
        if user_info_id.startswith('RESERVED:') and self.instance.pk and self.instance.used_by == user_info_id:
            return user_info_id
        if not user_info_id.isdigit() or int(user_info_id) <= 0:
            raise forms.ValidationError('Enter a valid numeric UserInfo ID.')
        return str(int(user_info_id))

    def clean(self):
        cleaned = super().clean()
        code = cleaned.get('coupon_code')
        amount = cleaned.get('discount_amount')
        match = COUPON_PATTERN.fullmatch(code or '')
        if match and amount is not None and int(match.group('amount')) != amount:
            self.add_error('coupon_code', 'Coupon discount hint must match Discount Amount.')
        return cleaned
