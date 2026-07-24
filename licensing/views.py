from django.shortcuts import render, redirect, get_object_or_404, get_object_or_404
from django.contrib import messages
from django.db import models, transaction
from .models import UserInfoData
from .models import tblPacsErp,tblUPI
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, JsonResponse
from .utils import generate_pacs_invoice_pdf
from .utils import generate_erp_invoice_pdf  # Naya function import kiya
from django.utils import timezone
from .forms import UserInfoForm, PacsErpForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import date
from functools import wraps
from django.db.models import Count, Sum
from django.views.decorators.http import require_POST



def userinfo_ajax_action(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        response = view_func(request, *args, **kwargs)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            queued = list(messages.get_messages(request))
            failed = any(message.level >= messages.ERROR for message in queued)
            text = ' '.join(str(message) for message in queued)
            return JsonResponse(
                {'success': not failed, 'message': text or ('Action failed.' if failed else 'Changes saved successfully.')},
                status=400 if failed else 200,
            )
        return response
    return wrapped


@login_required(login_url='accounts:login')
def userinfo_dashboard(request):
    search_query = request.GET.get('search_id', '').strip()
    partial_results = request.GET.get('partial') == '1'

    try:
        if request.user.is_superuser:
            clients = UserInfoData.objects.all()
        else:
            clients = UserInfoData.objects.filter(
                models.Q(accepte_by__icontains=request.user.username)
                | models.Q(accepte_by__isnull=True)
                | models.Q(accepte_by__exact='')
            )

        if search_query:
            search_filter = (
                models.Q(pacs_name__icontains=search_query)
                | models.Q(utr_number__iexact=search_query)
            )
            if search_query.isdigit():
                numeric_query = int(search_query)
                search_filter |= models.Q(mobile=numeric_query) | models.Q(operator_mobile=numeric_query)
            clients = clients.filter(search_filter).distinct()

        clients = Paginator(clients.order_by('-id'), 10).get_page(request.GET.get('page'))

        current_month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        requested_month = request.GET.get('report_month', '').strip()
        month_start = current_month_start
        if requested_month:
            try:
                parsed_month = datetime.strptime(requested_month, '%Y-%m')
                month_start = timezone.make_aware(parsed_month, timezone.get_current_timezone())
                if month_start > current_month_start:
                    month_start = current_month_start
            except ValueError:
                month_start = current_month_start
        if month_start.month == 12:
            next_month = month_start.replace(year=month_start.year + 1, month=1)
        else:
            next_month = month_start.replace(month=month_start.month + 1)
        if month_start.month == 1:
            previous_month = month_start.replace(year=month_start.year - 1, month=12)
        else:
            previous_month = month_start.replace(month=month_start.month - 1)
        monthly_records = UserInfoData.objects.filter(
            is_active=1,
            activation_date__gte=month_start,
            activation_date__lt=next_month,
        ).exclude(accepte_by__isnull=True).exclude(accepte_by__exact='')
        if not request.user.is_superuser:
            monthly_records = monthly_records.none()
        monthly_activation_report = list(
            monthly_records.values('accepte_by')
            .annotate(activation_count=Count('id'), payment_total=Sum('payment_status'))
            .order_by('-activation_count', 'accepte_by')
        )
        monthly_activation_count = sum(item['activation_count'] for item in monthly_activation_report)
        monthly_payment_total = sum((item['payment_total'] or 0) for item in monthly_activation_report)
        report_month = month_start.strftime('%B %Y')
        report_month_value = month_start.strftime('%Y-%m')
        previous_month_value = previous_month.strftime('%Y-%m')
        next_month_value = next_month.strftime('%Y-%m') if next_month <= current_month_start else ''
    except Exception as error:
        messages.error(request, f'Database Fetch Error: {error}')
        clients = []
        monthly_activation_report = []
        monthly_activation_count = 0
        monthly_payment_total = 0
        report_month = timezone.localdate().strftime('%B %Y')
        report_month_value = timezone.localdate().strftime('%Y-%m')
        previous_month_value = ''
        next_month_value = ''

    context = {
        'clients': clients,
        'search_query': search_query,
        'partial_results': partial_results,
        'farmer_form': None if partial_results else UserInfoForm(),
        'monthly_activation_report': monthly_activation_report,
        'monthly_activation_count': monthly_activation_count,
        'monthly_payment_total': monthly_payment_total,
        'report_month': report_month,
        'report_month_value': report_month_value,
        'previous_month_value': previous_month_value,
        'next_month_value': next_month_value,
    }
    return render(request, 'licensing/userinfo_dashboard.html', context)
@login_required(login_url='accounts:login')
@userinfo_ajax_action
def toggle_activation(request, pk):
    """
    UserInfoData table ke liye activation/deactivation action logic.
    """
    # ON ERROR HANDLING: Try-Except lagaya hai taaki invalid request par core crash na ho
    try:
        client = get_object_or_404(UserInfoData, pk=pk)
        current_search = request.GET.get('search_id', '').strip()
        
        if request.method == 'POST':
            input_amount = request.POST.get('amount', '0').strip()
            input_utr_number = request.POST.get('utr_number', '').strip()
            
            # VALIDATION CHECK: Agar non-numeric data hai to safe format me 0 karein
            if not input_amount.isdigit(): 
                input_amount = 0

            logged_in_user = request.user.username if request.user.is_authenticated else "System"

            client.amount = int(input_amount)
            client.payment_status = int(input_amount)
            client.accepte_by = logged_in_user     
            client.utr_number = input_utr_number       
            client.is_active = 1                       
            client.activation_date = timezone.now()
            client.save()
            messages.success(request, f"PACS ID {client.id} Activated successfully by {logged_in_user}!")
        else:
            # Deactivation flow
            if client.amount == client.payment_status:
                client.payment_status = 0 
                client.amount = 2000 
                client.is_active = 0
                client.accepte_by = ""       
                client.save()
                messages.warning(request, f"PACS ID {client.id} Deactivated successfully!")
                
    except Exception as e:
        messages.error(request, f"Status Update Failed: {str(e)}")
        # FIX: Agar error aaye toh safe exit ke liye seedha userinfo_dashboard par redirect karein
        return redirect('licensing:userinfo_dashboard')
        
    # FIX: Redirection links ko 'dashboard' se badal kar 'userinfo_dashboard' kiya gaya hai
    if current_search:
        return redirect(f"/licensing/userinfo/?search_id={current_search}")
    return redirect('licensing:userinfo_dashboard')


# =====================================================================
# 📊 NEW LOGIC: NCL DATABASE (tblPacsErp) FUNCTIONS
# =====================================================================


def _erp_queryset_for_user(user):
    queryset = tblPacsErp.objects.all()
    if user.is_superuser:
        return queryset
    return queryset.filter(
        models.Q(expiry_date__lt=timezone.localdate())
        | models.Q(accepte_by__iexact=user.username)
    ).exclude(erp_id__iendswith=' Expired')


@login_required(login_url='accounts:login')
def pacserp_dashboard(request):
    search_query = request.GET.get('search_id', '').strip()
    partial_results = request.GET.get('partial') == '1'

    try:
        erp_records = _erp_queryset_for_user(request.user)
        if search_query:
            if search_query.isdigit():
                erp_records = erp_records.filter(operator_mobile=int(search_query))
            else:
                erp_records = erp_records.filter(
                    models.Q(pacs_name__icontains=search_query)
                    | models.Q(erp_id__icontains=search_query)
                    | models.Q(remark__icontains=search_query)
                    | models.Q(system_id__icontains=search_query)
                )
        current_month_start = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        requested_month = request.GET.get('report_month', '').strip()
        month_start = current_month_start
        if requested_month:
            try:
                parsed_month = datetime.strptime(requested_month, '%Y-%m')
                month_start = timezone.make_aware(parsed_month, timezone.get_current_timezone())
                if month_start > current_month_start:
                    month_start = current_month_start
            except ValueError:
                month_start = current_month_start
        next_month = (
            month_start.replace(year=month_start.year + 1, month=1)
            if month_start.month == 12
            else month_start.replace(month=month_start.month + 1)
        )
        previous_month = (
            month_start.replace(year=month_start.year - 1, month=12)
            if month_start.month == 1
            else month_start.replace(month=month_start.month - 1)
        )
        report_user = request.GET.get('report_user', '').strip() if request.user.is_superuser else ''
        if report_user:
            erp_records = erp_records.filter(
                accepte_by__iexact=report_user,
                activation_date__gte=month_start,
                activation_date__lt=next_month,
            )
        erp_records = Paginator(erp_records.order_by('-id'), 10).get_page(request.GET.get('page'))

        monthly_records = tblPacsErp.objects.filter(
            is_active=1,
            activation_date__gte=month_start,
            activation_date__lt=next_month,
        ).exclude(accepte_by__isnull=True).exclude(accepte_by__exact='')
        if not request.user.is_superuser:
            monthly_records = monthly_records.none()
        monthly_activation_report = list(
            monthly_records.values('accepte_by')
            .annotate(activation_count=Count('id'), payment_total=Sum('payment_status'))
            .order_by('-activation_count', 'accepte_by')
        )
        monthly_activation_count = sum(item['activation_count'] for item in monthly_activation_report)
        monthly_payment_total = sum((item['payment_total'] or 0) for item in monthly_activation_report)
        report_month = month_start.strftime('%B %Y')
        report_month_value = month_start.strftime('%Y-%m')
        previous_month_value = previous_month.strftime('%Y-%m')
        next_month_value = next_month.strftime('%Y-%m') if next_month <= current_month_start else ''
    except Exception as error:
        messages.error(request, f'NCL Database Fetch Error: {error}')
        erp_records = []
        monthly_activation_report = []
        monthly_activation_count = 0
        monthly_payment_total = 0
        report_month = timezone.localdate().strftime('%B %Y')
        report_month_value = timezone.localdate().strftime('%Y-%m')
        previous_month_value = ''
        next_month_value = ''
        report_user = ''

    return render(request, 'licensing/pacserp_dashboard.html', {
        'erp_records': erp_records,
        'search_query': search_query,
        'erp_form': None if (partial_results or not request.user.is_superuser) else PacsErpForm(),
        'partial_results': partial_results,
        'monthly_activation_report': monthly_activation_report,
        'monthly_activation_count': monthly_activation_count,
        'monthly_payment_total': monthly_payment_total,
        'report_month': report_month,
        'report_month_value': report_month_value,
        'previous_month_value': previous_month_value,
        'next_month_value': next_month_value,
        'report_user': report_user,
    })

@login_required(login_url='accounts:login')
@require_POST
@userinfo_ajax_action
def toggle_erp_activation(request, pk):
    current_search = request.GET.get('search_id', '').strip()
    action = request.POST.get('action', 'activate').strip().lower()
    try:
        if action not in {'activate', 'deactivate'}:
            raise ValueError('Invalid ERP action.')
        if action == 'deactivate' and not request.user.is_superuser:
            messages.error(request, 'Only superuser can deactivate ERP records.')
            return redirect('licensing:pacserp_dashboard')

        allowed_records = _erp_queryset_for_user(request.user)
        record = get_object_or_404(allowed_records, pk=pk)

        if action == 'deactivate':
            record.payment_status = 4000
            record.amount = 0
            record.is_active = 0
            record.accepte_by = ''
            record.expiry_date = (
                record.expiry_date - timedelta(days=365)
                if record.expiry_date
                else timezone.localdate() - timedelta(days=1)
            )
            record.save()
            messages.warning(request, f'ERP Pacs ID {record.erp_id} Deactivated successfully!')
        else:
            input_amount = request.POST.get('amount', '0').strip()
            input_utr_number = request.POST.get('utr_number', '').strip()
            input_remark = request.POST.get('remark', '').strip()
            if not input_amount.isdigit():
                input_amount = '0'
            activation_amount = int(input_amount)

            if not request.user.is_superuser:
                if activation_amount <= 0:
                    raise ValueError('Activation amount zero se bada hona chahiye.')
                if not input_utr_number:
                    raise ValueError('UTR / Transaction Number required hai.')
                duplicate_utr = tblPacsErp.objects.filter(
                    utr_number__iexact=input_utr_number
                ).exists()
                if duplicate_utr:
                    raise ValueError('Ye UTR / Transaction Number pehle use ho chuka hai.')
                currently_active = (
                    int(record.is_active or 0) == 1
                    and record.expiry_date
                    and record.expiry_date >= timezone.localdate()
                )
                if currently_active:
                    raise ValueError('Active ERP record ko non-superuser renew nahi kar sakta.')

            logged_in_user = request.user.username
            activation_time = timezone.now()
            activation_day = timezone.localdate()
            try:
                expiry_date = activation_day.replace(year=activation_day.year + 1)
            except ValueError:
                expiry_date = activation_day.replace(year=activation_day.year + 1, day=28)

            with transaction.atomic():
                locked_records = _erp_queryset_for_user(request.user).select_for_update()
                record = locked_records.get(pk=pk)
                old_amount = int(record.amount or 0)
                old_payment_status = int(record.payment_status or 0)
                create_renewal_copy = (
                    old_amount > 0
                    and old_payment_status > 0
                    and old_amount == old_payment_status
                )

                if create_renewal_copy:
                    original_erp_id = (record.erp_id or '').strip()
                    if not original_erp_id:
                        raise ValueError('Blank ERP ID ko renew nahi kiya ja sakta.')
                    if original_erp_id.lower().endswith(' expired'):
                        raise ValueError('Expired ERP history record ko dobara activate nahi kiya ja sakta.')

                    record.erp_id = f'{original_erp_id} Expired'
                    record.is_active = 0
                    record.save(update_fields=['erp_id', 'is_active'])
                    source_record = record
                    record = tblPacsErp.objects.create(
                        amount=activation_amount,
                        brach=source_record.brach,
                        dist=source_record.dist,
                        erp_id=original_erp_id,
                        expiry_date=expiry_date,
                        is_active=1,
                        last_login=source_record.last_login,
                        operator_mobile=source_record.operator_mobile,
                        pacs_name=source_record.pacs_name,
                        payment_status=activation_amount,
                        remark=f'Activated by {logged_in_user}. {input_remark}'.strip(),
                        state=source_record.state,
                        system_id=source_record.system_id,
                        utr_number=input_utr_number,
                        version_info=source_record.version_info,
                        accepte_by=logged_in_user,
                        activation_date=activation_time,
                        razorpay_payment_link_id=None,
                        razorpay_payment_id=None,
                        razorpay_reference_id=None,
                        razorpay_payment_status=None,
                    )
                    success_message = f'ERP ID {original_erp_id} renewed successfully; old record Expired history me safe hai.'
                else:
                    record.amount = activation_amount
                    record.payment_status = activation_amount
                    record.utr_number = input_utr_number
                    record.remark = f'Activated by {logged_in_user}. {input_remark}'.strip()
                    record.is_active = 1
                    record.accepte_by = logged_in_user
                    record.activation_date = activation_time
                    record.expiry_date = expiry_date
                    record.save()
                    success_message = f'ERP Pacs ID {record.erp_id} Activated successfully!'

            messages.success(request, success_message)
    except Exception as error:
        messages.error(request, f'ERP Status Update Failed: {error}')
        return redirect('licensing:pacserp_dashboard')

    if current_search:
        return redirect(f'/licensing/pacserp/?search_id={current_search}')
    return redirect('licensing:pacserp_dashboard')

@login_required
def generate_invoice(request, pk):
    """
    ROUTING VIEW: Handle karega sirf database call aur response file dispatching.
    """
    # ON ERROR HANDLING: Request validation safety rule
    try:
        client = get_object_or_404(UserInfoData, pk=pk)
        custom_amount_raw = request.GET.get('customAmount', '0')
        # print(customAmount)
        # UTILS EXECUTION: Nayi file ke code ko data object pass karke stream li
        pdf_buffer = generate_pacs_invoice_pdf(request, client,custom_amount_raw)
        
        return FileResponse(pdf_buffer, as_attachment=False, content_type='application/pdf')
        
    except Exception as e:
        messages.error(request, f"Invoice Engine Execution Failed: {str(e)}")
        return redirect('licensing:userinfo_dashboard')
    
@login_required
def generate_erp_invoice(request, pk):
    """
    NCL INVOICE ROUTER: Dispatches generated binary PDF streams for tblPacsErp.
    """
    # ON ERROR HANDLING: Safe database lookup pattern
    try:
        record = get_object_or_404(_erp_queryset_for_user(request.user), pk=pk)
        
        # Call explicit separate engine file logic
        pdf_buffer = generate_erp_invoice_pdf(request, record)
        
        return FileResponse(pdf_buffer, as_attachment=False, content_type='application/pdf')
        
    except Exception as e:
        messages.error(request, f"NCL ERP Invoice Engine Mismatch: {str(e)}")
        return redirect('licensing:pacserp_dashboard')
    


@login_required
@userinfo_ajax_action
def create_userinfo(request):
    if request.method == 'POST':
        form = UserInfoForm(request.POST)
        # On Error GoTo style: Execution error ko safe rakhne ke liye try-except block
        try:
            if form.is_valid():
                pacs_name = form.cleaned_data.get('pacs_name')
                mobile = form.cleaned_data.get('mobile')
                f_year = form.cleaned_data.get('f_year')
                for_whys = form.cleaned_data.get('for_whys')
                
                # Sahi Duplicate Check logic: Ab yeh charo chizein match hongi tabhi error dega
                if UserInfoData.objects.filter(
                    pacs_name=pacs_name, 
                    mobile=mobile, 
                    f_year=f_year, 
                    for_whys=for_whys
                ).exists():
                    messages.error(request, f"Duplicate Entry: ({mobile}) '{pacs_name}' ka record '{for_whys}' ({f_year}) ({mobile}) ke liye pehle se mojud hai!")
                    return render(request, 'licensing/create_userinfo.html', {'form': form})
                new_record = form.save(commit=False)
                new_record.payment_status = 0
                new_record.amount = 2000
                new_record.date_time =timezone.now()
                new_record.last_login = timezone.now()
                new_record.system_id = 'Crated By Admin'
                new_record.branch_approve = 0
                new_record.is_animal = 0
                new_record.is_active = 1
                new_record.entry_count = 0
                new_record.save()
                messages.success(request, f"Success: PACS '{pacs_name}' Safely Save Ho Gaya.")
                return redirect('licensing:userinfo_dashboard')
            else:
                messages.error(request, "Validation Error: Kripya saare fields ko sahi se bharein.")
        except Exception as e:
            messages.error(request, f"System Operational Error: {str(e)}")
    else:
        # Copy Row Data Fetch Logic
        copy_id = request.GET.get('copy_id')
        initial_data = {}
        
        if copy_id:
            try:
                old_record = UserInfoData.objects.get(pk=copy_id)
                initial_data = {
                    'mobile': old_record.mobile,
                    'pacs_name': old_record.pacs_name,
                    'brach': old_record.brach,
                    'dist': old_record.dist,
                    'operator_mobile': old_record.operator_mobile,
                    'amount': old_record.amount,
                    'for_whys': old_record.for_whys,
                    'f_year': old_record.f_year,
                    'is_pri': old_record.is_pri,
                    'entry_count': 0,
                    'is_active': old_record.is_active,
                    'limit_of_entrys': old_record.limit_of_entrys,
                }
            except Exception:
                pass 
                
        form = UserInfoForm(initial=initial_data)
        
    return render(request, 'licensing/create_userinfo.html', {'form': form})

@login_required
@userinfo_ajax_action
def create_pacserp(request):
    if not request.user.is_superuser:
        messages.error(request, 'Only superuser can add ERP records.')
        return redirect('licensing:pacserp_dashboard')
    """
    Form view to insert new records into TblPacsErp table.
    ON ERROR HANDLING: Default isActive=1 force inject kiya hai save karne se pehle.
    """
    if request.method == 'POST':
        form = PacsErpForm(request.POST)
        try:
            if form.is_valid():
                erp_id = form.cleaned_data.get('erp_id')
                pacs_name = form.cleaned_data.get('pacs_name')
                
                # DUPLICATE CHECK LOGIC: System ID unique honi chahiye ERP portal par
                if erp_id and tblPacsErp.objects.filter(erp_id=erp_id).exists():
                    messages.error(request, f"Duplicate Entry Check: ERP ID '{erp_id}' ke sath ek record pehle se active hai!")
                    return render(request, 'licensing/create_pacserp.html', {'form': form})
                
                # SAFE COMMIT FALSE: Pehle data ko memory me hold kiya, direct database me nahi bheja
                new_record = form.save(commit=False)
                
                # FORCE INJECT VALUES: database model class names ke mutabik isActive ko 1 kiya
                new_record.is_active = 1  # <-- Ye line automatic default 1 set karegi
                new_record.last_login = timezone.now()
                new_record.accepte_by = request.user.username
                new_record.activation_date = timezone.now()
                
                # Final database save layer
                new_record.save()
                
                messages.success(request, f"Success: ERP Record '{pacs_name}' successfully create aur automatic ACTIVE ho gaya.")
                return redirect('licensing:pacserp_dashboard')
            else:
                messages.error(request, "Validation Error: Input parameters completely format match nahi kar rahe.")
        except Exception as e:
            messages.error(request, f"System Operational Error: {str(e)}")
    else:
        form = PacsErpForm()
        
    return render(request, 'licensing/create_pacserp.html', {'form': form})



@login_required
@require_POST
@userinfo_ajax_action
def delete_record_view(request, record_id):
    """
    Is view se record delete hota hai, par sirf tabhi jab logged-in user Admin ho.
    """
    # 1. Error Handling: Pehle check karenge ki record exist karta hai ya nahi
    try:
        record = get_object_or_404(tblPacsErp, id=record_id)
        
        # 2. Safety Check: Sirf Admin/Superuser hi delete kar sakta hai
        if not request.user.is_superuser:
            # Agar user admin nahi hai, toh request block karein aur warning dein
            messages.error(request, "Error: Aapke paas is record ko delete karne ki permission nahi hai!")
            return redirect('licensing:pacserp_dashboard') # Apne dashboard ya list view par redirect karein

        # 3. Execution: Agar admin hai, toh record delete karein
        record.delete()
        messages.success(request, f"Success: Record {record_id} kamyabi se delete kar diya gaya hai.")
        
    except Exception as e:
        # On Error GoTo block jaisa behavior handle karne ke liye
        messages.error(request, f"System Error: Record delete nahi ho paya. Details: {str(e)}")
        
    return redirect('licensing:pacserp_dashboard')


@login_required
@userinfo_ajax_action
def delete_userinfo_view(request, user_id):
    """
    UserInfoData ke kisi specific user ko delete karne ka secure backend view.
    Sirf Admin/Superuser hi is action ko execute kar sakta hai.
    """
    # Error Handling (On Error GoTo equivalent logic)
    try:
        # 1. Safety Check: Pehle dhoondho ki user exist karta hai ya nahi, nahi toh 404 error
        user_record = get_object_or_404(UserInfoData, id=user_id)
        
        # 2. Permission Check: Agar login karne wala banda admin (superuser) nahi hai
        if not request.user.is_superuser:
            messages.error(request, "Security Alert: Aapke paas kisi user ka profile delete karne ki permission nahi hai!")
            return redirect('licensing:userinfo_dashboard')  # Dashboard par wapas bhej dein

        # 3. Execution: Agar saari conditions sahi hain, toh record delete karein
        username_for_msg = user_record.pacs_name  # Message me naam dikhane ke liye store kiya
        user_record.delete()
        
        # Success response push karna jo SweetAlert Toast me dikhega
        messages.success(request, f"Success: User '{username_for_msg}' ka record database se permanent delete kar diya gaya hai.")
        
    except Exception as e:
        # Database fallback check agar delete operation me koi constraint issue aaye
        messages.error(request, f"Database Error: Deletion fail ho gaya. Details: {str(e)}")
        
    # Action complete hone ke baad dashboard page par wapas redirect karein
    return redirect('licensing:userinfo_dashboard')


@login_required
@userinfo_ajax_action
def update_userinfo_view(request, client_id):
    """
    UserInfoData / Farmer record ko safe update karne ka backend view.
    On Error Goto/Try-Except aur Duplicate check logic pehle se implemented hai.
    """
    # 1. Fetch Record: Pehle check karo ki record database me hai ya nahi
    client_record = get_object_or_404(UserInfoData, id=client_id)
    
    if request.method == 'POST':
        # 2. Form Binding: POST data aur purane record ko ek sath bind karna
        form = UserInfoForm(request.POST, instance=client_record)
        
        try:
            if form.is_valid():
                # 3. Duplicate Check / Constraint validation check pehle se lagana
                # Agar save karte waqt koi backend validation fail hoti hai
                form.save()
                
                # Success Message push karna jo SweetAlert Toast me dikhega
                messages.success(request, f"Success: User ID '{client_record.mobile} {client_record.pacs_name} ' ka data successfully update kar diya gaya hai.")
                return redirect('licensing:userinfo_dashboard') # Dashboard par wapas bhej dein
            else:
                messages.error(request, "Validation Error: Form me di gayi jaankari sahi nahi hai. Kripya check karein.")
        
        except Exception as e:
            # Operational Error Handling block
            messages.error(request, f"Database Error: Record update karne me samasya aayi. Details: {str(e)}")
            
    else:
        # GET request hone par purana data automatic fields me load ho jayega (instance ki wajah se)
        form = UserInfoForm(instance=client_record)
        
    # Aapki upload ki hui HTML file ko reuse karenge, bas context me title badal denge
    context = {
        'form': form,
        'is_update': True  # Template ko batane ke liye ki ye Edit mode hai
    }
    return render(request, 'licensing/create_userinfo.html', context)


@login_required
@userinfo_ajax_action
def update_pacserp_view(request, record_id):
    if not request.user.is_superuser:
        messages.error(request, 'Only superuser can update ERP records.')
        return redirect('licensing:pacserp_dashboard')
    """
    TblPacsErp master record ko safe update karne ka backend view.
    On Error Goto/Try-Except aur Duplicate check logic pehle se implemented hai.
    """
    # 1. Fetch Record: Database se primary key (id) ke hisab se record nikalna
    erp_record = get_object_or_404(tblPacsErp, id=record_id)
    
    if request.method == 'POST':
        # 2. Form Binding: Incoming POST data ko purane instance ke sath link karna
        form = PacsErpForm(request.POST, instance=erp_record)
        
        try:
            if form.is_valid():
                # 3. Duplicate/Constraint Validation Check pehle hi execute hoga
                form.save()
                
                # Success notification push karna jo SweetAlert Toast me chalega
                messages.success(request, f"Success: ERP Record ID #{erp_record.id} successfully update ho gaya hai.")
                return redirect('licensing:pacserp_dashboard')  # ERP Dashboard par wapas redirect karein
            else:
                messages.error(request, "Validation Error: Form validation fail ho gayi hai. Kripya details check karein.")
        
        except Exception as e:
            # Error Handling Block (System crash hone se bachaega)
            messages.error(request, f"Database Error: Record update karne me samasya aayi. Details: {str(e)}")
            
    else:
        # GET Request aane par purana data form fields me pre-fill (auto-populate) ho jayega
        form = PacsErpForm(instance=erp_record)
        
    # Aapki upload ki hui HTML file ko target karenge aur dynamic context bhejenge
    context = {
        'form': form,
        'is_update': True  # Template ko batane ke liye ki ye Edit mode chal raha hai
    }
    return render(request, 'licensing/create_pacserp.html', context)
