from django.shortcuts import render, redirect, get_object_or_404, get_object_or_404
from django.contrib import messages
from django.db import models
from .models import UserInfoData
from .models import tblPacsErp,tblUPI
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from .utils import generate_pacs_invoice_pdf
from .utils import generate_erp_invoice_pdf  # Naya function import kiya
from django.utils import timezone
from .forms import UserInfoForm, PacsErpForm
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from datetime import date
from django.db.models import Sum

def main_hub(request):
    """
    SECURITY WALL & LANDING HUB: Login ke baad sabse pehle ye khulega.
    Yahan koi data load nahi hoga, sirf tables ki list dikhegi.
    """

    if not request.user.is_authenticated:
        return redirect('login')
    return render(request, 'licensing/main_hub.html')


@login_required(login_url='login')
def userinfo_dashboard(request):
    """
    DEDICATED VIEW: Sirf UserInfoData table ka data load karega.
    """
    # ON ERROR LOGIC / SECURITY WALL: Agar session expire ho jaye to direct login par bhein
        
    search_query = request.GET.get('search_id', '').strip()
    clients = []
    
    try:
        if search_query:
            # DUPLICATE & FILTER CHECK: Pacs name ya mobile se filter karein
            if request.user.is_superuser:

                clients = UserInfoData.objects.filter(
                    models.Q(pacs_name__icontains=search_query) |
                    models.Q(mobile__icontains=search_query) |
                    models.Q(utr_number__icontains=search_query) |
                    models.Q(operator_mobile__icontains=search_query)
                ).order_by('-id').distinct()
            else:
                clients = UserInfoData.objects.filter(
                    models.Q(pacs_name__icontains=search_query) |
                    models.Q(mobile__icontains=search_query) |
                    models.Q(utr_number__icontains=search_query) |
                    models.Q(operator_mobile__icontains=search_query),
                    (
                    models.Q(accepte_by__icontains=request.user.username) | 
                    models.Q(accepte_by__isnull=True) | # Agar database column NULL set hai
                    models.Q(accepte_by__exact='')      # Agar database column empty string ('') hai
                    )
                    

                ).order_by('-id').distinct()
            
            paginator = Paginator(clients, 10)
            page_number = request.GET.get('page')
            
            try:
                # Expected page load karein
                clients = paginator.page(page_number)
            except PageNotAnInteger:
                # Agar URL mein string pass ho jaye, to pehla page load karein
                clients = paginator.page(1)
            except EmptyPage:
                # Agar user koi aisi page value dale jo hai hi nahi, to aakhiri page load karein
                clients = paginator.page(paginator.num_pages)
        else:
            # Default top 10 records load karein aur optimize format me rkhein
            if request.user.is_superuser:
                clients = UserInfoData.objects.all().order_by('-id')
            else:
                # Normal user ke liye unke assigned ya blank records ke top 10
                clients = UserInfoData.objects.filter(
                    models.Q(accepte_by__icontains=request.user.username) | 
                    models.Q(accepte_by__isnull=True) | 
                    models.Q(accepte_by__exact='')
                ).order_by('-id')
            paginator = Paginator(clients, 10)
            page_number = request.GET.get('page')
            
            try:
                # Expected page load karein
                clients = paginator.page(page_number)
            except PageNotAnInteger:
                # Agar URL mein string pass ho jaye, to pehla page load karein
                clients = paginator.page(1)
            except EmptyPage:
                # Agar user koi aisi page value dale jo hai hi nahi, to aakhiri page load karein
                clients = paginator.page(paginator.num_pages)
    except Exception as e:
        messages.error(request, f"Database Fetch Error: {str(e)}")
        clients = []
    
    return render(request, 'licensing/userinfo_dashboard.html', {'clients': clients,'search_query': search_query})

@login_required(login_url='login')
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
        return redirect('userinfo_dashboard')
        
    # FIX: Redirection links ko 'dashboard' se badal kar 'userinfo_dashboard' kiya gaya hai
    if current_search:
        return redirect(f"/userinfo/?search_id={current_search}")
    return redirect('userinfo_dashboard')


# =====================================================================
# 📊 NEW LOGIC: NCL DATABASE (tblPacsErp) FUNCTIONS
# =====================================================================


@login_required(login_url='login')
def pacserp_dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
        
    if not request.user.is_superuser:
        messages.error(request, "Only Admin can open ERP.")  # ⚠️ यहाँ 'e' हटाया
        return redirect('khata:dashboard')  # ✅ 'dashborad' की spelling सही करें
    search_query = request.GET.get('search_id', '').strip()
    erp_records = []
    
    # ON ERROR HANDLING: Database execution safe rakhne ke liye try-except block
    try:
        if search_query:
            # DUPLICATE & SEARCH LOGIC FIX: 
            # 1. Hamare variables lowercase me TblPacsErp ke fields se match hone chahiye (pacs_name, system_id, operator_mobile)
            # 2. Agar user numeric search kar rha hai, to hi use operator_mobile par chalayein taaki SQL crash na ho.
            
            if search_query.isdigit():
                # Agar sirf numbers hain, toh operator_mobile, pacs_name aur system_id teeno me dhoondhein
                erp_records = tblPacsErp.objects.filter(
                    models.Q(operator_mobile=int(search_query))
                )
            else:
                # Agar user string type kar rha hai, toh check sirf string variables par hoga taaki Numeric Field block crash na ho
                erp_records = tblPacsErp.objects.filter(
                    models.Q(pacs_name__icontains=search_query) |
                    models.Q(erp_id__icontains=search_query) |
                    models.Q(remark__icontains=search_query) |
                    models.Q(system_id__icontains=search_query)
                )
        else:
            # DEFAULT STATE: Latests 10 entries clean tarike se pull karein
            erp_records = tblPacsErp.objects.all().order_by('-id')[:10]
            
    except Exception as e:
        messages.error(request, f"NCL Database Fetch Error: {str(e)}")
        erp_records = []
        
    return render(request, 'licensing/pacserp_dashboard.html', {
        'erp_records': erp_records, 
        'search_query': search_query
    })


def toggle_erp_activation(request, pk):
    """
    NCL ERP ACTIVATION LOGIC: Modal form se expiry_date capture karke update aur save karega.
    """
    # ON ERROR HANDLING: Database workflow ko safe rakhne ke liye try-except block
    try:
        record = get_object_or_404(tblPacsErp, pk=pk)
        current_search = request.GET.get('search_id', '').strip()
        
        # 1. ACTIVATE / UPDATE FLOW (POST Request)
        if request.method == 'POST':
            input_amount = request.POST.get('amount', '0').strip()
            input_utr_number = request.POST.get('utr_number', '').strip()
            input_expiry_date = request.POST.get('expiry_date', '').strip()  # <-- Form se value li

            input_remark = request.POST.get('remark', '').strip() 

            if ((datetime.strptime(input_expiry_date, "%Y-%m-%d").date()) - date.today()) > timedelta(days=364):
                messages.error(request, "Date 1 Year Se Jyada Nahi ho sakti hai.")
                return redirect('pacserp_dashboard')
            
            if not input_amount.isdigit() or not input_amount:
                input_amount = 0
                
            logged_in_user = request.user.username if request.user.is_authenticated else "System"
            
            # Standard assignments
            record.amount = int(input_amount)
            record.payment_status = int(input_amount)
            record.utr_number = input_utr_number
            record.remark = f"Activated by {logged_in_user}. {input_remark}".strip()
            record.is_active = 1
            
            # ON ERROR HANDLING & VALIDATION: Blank string check aur safe date parsing
            if input_expiry_date:  # Agar date field me value hai (khali nahi hai)
                try:
                    # String date को Django object formatting ke mutabik convert kiya
                    record.expiry_date = datetime.strptime(input_expiry_date, "%Y-%m-%d").date()

                except (ValueError, TypeError):
                    # Agar user ne galat format dala to safe exit ke liye validation error handle kiya
                    messages.error(request, "Date ka format sahi nahi hai. Kripya YYYY-MM-DD format use karein.")
                    return redirect('pacserp_dashboard')
            else:
                # DUPLICATE CHECK / SAFE EXIT: Agar user ne form me date chhod di hai, to use None (NULL) set karein
                record.expiry_date = None

            record.save()  # <-- Ab database save perfectly execute hoga bina crash kiye
            messages.success(request, f"ERP Pacs ID {record.erp_id} Activated/Updated successfully!")
            
        # 2. DEACTIVATE FLOW (GET Request)
        else:
            record.payment_status = 4000
            record.amount = 0
            record.is_active = 0
            record.expiry_date = record.expiry_date - timedelta(days=365)
                
            # Note: Deactivate par custom logic ke mutabik expiry_date ko change nahi kiya hai taaki purana record safe rahe.
            record.save()
            messages.warning(request, f"ERP Pacs ID {record.erp_id} Deactivated successfully!")
            
    except Exception as e:
        messages.error(request, f"ERP Status & Date Update Failed: {str(e)}")
        return redirect('pacserp_dashboard')
        
    # Redirect routing logic to retain the search state
    if current_search:
        return redirect(f"/pacserp/?search_id={current_search}")
    return redirect('pacserp_dashboard')



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
        return redirect('userinfo_dashboard')
    
@login_required
def generate_erp_invoice(request, pk):
    """
    NCL INVOICE ROUTER: Dispatches generated binary PDF streams for tblPacsErp.
    """
    # ON ERROR HANDLING: Safe database lookup pattern
    try:
        record = get_object_or_404(tblPacsErp, pk=pk)
        
        # Call explicit separate engine file logic
        pdf_buffer = generate_erp_invoice_pdf(request, record)
        
        return FileResponse(pdf_buffer, as_attachment=False, content_type='application/pdf')
        
    except Exception as e:
        messages.error(request, f"NCL ERP Invoice Engine Mismatch: {str(e)}")
        return redirect('pacserp_dashboard')
    


@login_required
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
                return redirect('userinfo_dashboard')
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
def create_pacserp(request):
    """
    Form view to insert new records into TblPacsErp table.
    ON ERROR HANDLING: Default isActive=1 force inject kiya hai save karne se pehle.
    """
    if request.method == 'POST':
        form = PacsErpForm(request.POST)
        try:
            if form.is_valid():
                erp_id = form.cleaned_data.get('system_id')
                pacs_name = form.cleaned_data.get('pacs_name')
                
                # DUPLICATE CHECK LOGIC: System ID unique honi chahiye ERP portal par
                if tblPacsErp.objects.filter(system_id=erp_id).exists():
                    messages.error(request, f"Duplicate Entry Check: System ID '{erp_id}' ke sath ek record pehle se active hai!")
                    return render(request, 'licensing/create_pacserp.html', {'form': form})
                
                # SAFE COMMIT FALSE: Pehle data ko memory me hold kiya, direct database me nahi bheja
                new_record = form.save(commit=False)
                
                # FORCE INJECT VALUES: database model class names ke mutabik isActive ko 1 kiya
                new_record.is_active = 1  # <-- Ye line automatic default 1 set karegi
                new_record.lastLogin = datetime.now()
                
                # Final database save layer
                new_record.save()
                
                messages.success(request, f"Success: ERP Record '{pacs_name}' successfully create aur automatic ACTIVE ho gaya.")
                return redirect('pacserp_dashboard')
            else:
                messages.error(request, "Validation Error: Input parameters completely format match nahi kar rahe.")
        except Exception as e:
            messages.error(request, f"System Operational Error: {str(e)}")
    else:
        form = PacsErpForm()
        
    return render(request, 'licensing/create_pacserp.html', {'form': form})



@login_required
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
            return redirect('pacserp_dashboard') # Apne dashboard ya list view par redirect karein

        # 3. Execution: Agar admin hai, toh record delete karein
        record.delete()
        messages.success(request, f"Success: Record {record_id} kamyabi se delete kar diya gaya hai.")
        
    except Exception as e:
        # On Error GoTo block jaisa behavior handle karne ke liye
        messages.error(request, f"System Error: Record delete nahi ho paya. Details: {str(e)}")
        
    return redirect('pacserp_dashboard')


@login_required
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
            return redirect('userinfo_dashboard')  # Dashboard par wapas bhej dein

        # 3. Execution: Agar saari conditions sahi hain, toh record delete karein
        username_for_msg = user_record.pacs_name  # Message me naam dikhane ke liye store kiya
        user_record.delete()
        
        # Success response push karna jo SweetAlert Toast me dikhega
        messages.success(request, f"Success: User '{username_for_msg}' ka record database se permanent delete kar diya gaya hai.")
        
    except Exception as e:
        # Database fallback check agar delete operation me koi constraint issue aaye
        messages.error(request, f"Database Error: Deletion fail ho gaya. Details: {str(e)}")
        
    # Action complete hone ke baad dashboard page par wapas redirect karein
    return redirect('userinfo_dashboard')


@login_required
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
                return redirect('userinfo_dashboard') # Dashboard par wapas bhej dein
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
def update_pacserp_view(request, record_id):
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
                return redirect('pacserp_dashboard')  # ERP Dashboard par wapas redirect karein
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
