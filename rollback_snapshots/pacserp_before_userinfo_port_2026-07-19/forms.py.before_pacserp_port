from django import forms
from .models import UserInfoData, tblPacsErp,Perpous,tblUPI

class UserInfoForm(forms.ModelForm):

    for_whys = forms.ChoiceField(
        choices=[],  # Shuruat me khali rahega
        widget=forms.Select(attrs={'class': 'form-select bg-dark text-light border-secondary'}),
        required=False  # Aapki requirement ke mutabik safe choice validation
    )
    class Meta:
        model = UserInfoData
        # FIXED FIELDS LIST: Sirf wahi fields rakhe hain jo database table me actual mojud hain
        fields = ['mobile','pacs_name', 'brach', 'dist','state', 'operator_mobile', 'payment_status', 'amount', 'utr_number', 'for_whys', 'f_year','is_pri','limit_of_entrys','accepte_by']
        
        widgets = {
            'mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'pacs_name': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'brach': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'dist': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'state': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. MADHYA PRADESH'}),
            'operator_mobile': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'payment_status' : forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'amount' : forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'utr_number': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'f_year': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. 2024-2025'}),
            'is_pri' : forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'limit_of_entrys' : forms.NumberInput(attrs={'class': 'form-control bg-dark text-light border-secondary'}),
            'accepte_by': forms.TextInput(attrs={'class': 'form-control bg-dark text-light border-secondary', 'placeholder': 'e.g. Admin'}),
            # ❌ software_license_key aur remark ke widgets yahan se hata diye hain
        }
    
    # 2. DYNAMIC UNIQUE VALUE ENGINE: Form load hote hi chalega
    def __init__(self, *args, **kwargs):
        super(UserInfoForm, self).__init__(*args, **kwargs)
        
        # ON ERROR HANDLING: Data fetch workflow ko safe rakhne ke liye try-except block
        try:
            # Perpous table ke forWhy column se unique, non-null aur non-empty values nikalna
            # values_list('forWhy', flat=True) se flat list milegi, distinct() duplicates ko pehle hi drop kar dega
            unique_purposes = (
                Perpous.objects.exclude(forWhy__isnull=True)
                .exclude(forWhy="")
                .exclude(forWhy__icontains='Delete')
                .values_list('forWhy', flat=True)
                .distinct()
            )
            
            # Default fallback/instruction option dropdown ke liye
            choices = [('', '-- Select Purpose --')]
            
            # DUPLICATE CHECK COMPLETED: Loop chalakar choices list me (Value, Display Text) inject kiya
            for purpose in unique_purposes:
                choices.append((purpose, purpose))
                
            # Final unique choices ko field me apply kar diya
            self.fields['for_whys'].choices = choices
            
        except Exception as e:
            # FALLBACK LOGIC: Agar table exist na kare ya migration issue ho, to server crash nahi hoga
            self.fields['for_whys'].choices = [('', '-- Select Purpose --')]

    

class PacsErpForm(forms.ModelForm):
    class Meta:
        model = tblPacsErp
        # PacsErpForm bilkul sahi hai, isey waisa hi rehne dein
        fields = ['erp_id', 'pacs_name', 'brach', 'dist', 'state', 'operator_mobile', 'amount','payment_status', 'expiry_date','utr_number', 'remark']
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
            'remark': forms.Textarea(attrs={'class': 'form-control bg-dark text-light border-secondary', 'rows': 3}),
        }
