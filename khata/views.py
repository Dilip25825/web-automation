from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Customer, Transaction
import base64
from django.db.models.functions import Coalesce
from django.utils.dateparse import parse_date
from django.db.models import Q,F, Sum, DecimalField, Case, When,Value
from django.utils import timezone
import urllib.parse
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
from .models import ShopProfile
from django.core.paginator import Paginator #
from django.views.decorators.http import require_POST
# @login_required
# def dashboard(request):
#     try:
#         # Base list
#         customers = Customer.objects.filter(user=request.user).order_by('name')
        
#         search_query = request.GET.get('search', '').strip()
#         filter_type = request.GET.get('filter', 'all')
        
#         if search_query:
#             customers = customers.filter(
#                 Q(name__icontains=search_query) | Q(phone__icontains=search_query)
#             ).order_by('name')
        
#         # 1. Total Calculations (Poore customers par, pagination se pehle)
#         total_lene_hain = 0  
#         total_dene_hain = 0  
        
#         for cust in customers:
#             trans = Transaction.objects.filter(customer=cust)
#             net = sum(t.amount for t in trans if t.trans_type == 'GIVEN') - sum(t.amount for t in trans if t.trans_type == 'GOT')
#             if net > 0: total_lene_hain += net
#             elif net < 0: total_dene_hain += abs(net)

#         # 2. Filter logic (Dashboard ke cards ke liye)
#         final_list = []
#         for cust in customers:
#             trans = Transaction.objects.filter(customer=cust)
#             net = sum(t.amount for t in trans if t.trans_type == 'GIVEN') - sum(t.amount for t in trans if t.trans_type == 'GOT')
            
#             if filter_type == 'lene' and net <= 0: continue
#             if filter_type == 'dene' and net >= 0: continue
            
#             cust.balance = net
#             cust.abs_balance = abs(net)
#             cust.b64_id = base64.b64encode(str(cust.id).encode('utf-8')).decode('utf-8')
#             final_list.append(cust)

#         # 3. Pagination (Limit 15 per page)
#         paginator = Paginator(final_list, 10)
#         page_number = request.GET.get('page')
#         page_obj = paginator.get_page(page_number)
        
#         context = {
#             'customers': page_obj, 
#             'total_lene_hain': total_lene_hain,
#             'total_dene_hain': total_dene_hain,
#             'current_filter': filter_type,
#             'search_query': search_query,
#         }
#         return render(request, 'khata/dashboard.html', context)
        
#     except Exception as e:
#         messages.error(request, f"Dashboard load karne me error: {str(e)}")
#         return render(request, 'khata/error.html')


@login_required
def dashboard(request):
    try:
        customers_qs = Customer.objects.filter(user=request.user)
        
        # ---------- SEARCH ----------
        search_query = request.GET.get('search', '').strip()
        if search_query:
            customers_qs = customers_qs.filter(
                Q(name__icontains=search_query) | Q(phone__icontains=search_query)
            )
        
        # ---------- ANNOTATE: Total Given & Got (Single query) ----------
        customers_qs = customers_qs.annotate(
            total_given=Coalesce(
                Sum('transaction__amount', filter=Q(transaction__trans_type='GIVEN')),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))
            ),
            total_got=Coalesce(
                Sum('transaction__amount', filter=Q(transaction__trans_type='GOT')),
                Value(0, output_field=DecimalField(max_digits=10, decimal_places=2))
            )
        ).annotate(
            net_balance=F('total_given') - F('total_got')
        )
        
        # ---------- FILTER (lene / dene) ----------
        filter_type = request.GET.get('filter', 'all')
        if filter_type == 'lene':
            customers_qs = customers_qs.filter(net_balance__gt=0)
        elif filter_type == 'dene':
            customers_qs = customers_qs.filter(net_balance__lt=0)
        
        # ---------- ORDER ----------
        customers_qs = customers_qs.order_by('name')
        
        # ---------- TOTAL LENE / DENE (using separate filter sums, no Case/When) ----------
        total_lene_hain = customers_qs.filter(net_balance__gt=0).aggregate(
            total=Sum('net_balance')
        )['total'] or 0
        
        total_dene_hain = customers_qs.filter(net_balance__lt=0).aggregate(
            total=Sum('net_balance')
        )['total'] or 0
        total_dene_hain = abs(total_dene_hain)   # Convert negative to positive
        
        # ---------- PAGINATION (10 per page) ----------
        paginator = Paginator(customers_qs, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # ---------- EXTRA FIELDS FOR TEMPLATE ----------
        for cust in page_obj:
            cust.b64_id = base64.b64encode(str(cust.id).encode('utf-8')).decode('utf-8')
            cust.balance = cust.net_balance 
            cust.abs_balance = abs(cust.net_balance)
        
        context = {
            'customers': page_obj,
            'total_lene_hain': total_lene_hain,
            'total_dene_hain': total_dene_hain,
            'current_filter': filter_type,
            'search_query': search_query,
        }
        return render(request, 'khata/dashboard.html', context)
        
    except Exception as e:
        messages.error(request, f"Dashboard load karne me error: {str(e)}")
        return render(request, 'khata/error.html')

@login_required
def add_customer(request):
    if request.method == 'POST':
        try:
            name = request.POST.get('name')
            phone = request.POST.get('phone')
            
            # Duplicate Check: Check karein ki is user ne is phone number se pehle hi customer add toh nahi kiya
            if Customer.objects.filter(user=request.user, phone=phone).exists():
                messages.warning(request, "Yeh number pehle se hi list me maujood hai!")
                return redirect('khata:dashboard')
            
            # Agar duplicate nahi hai, toh naya customer save karein
            new_customer = Customer(user=request.user, name=name, phone=phone)
            new_customer.save()
            messages.success(request, "Naya grahak safaltapoorvak add ho gaya!")
            return redirect('khata:dashboard')
            
        except Exception as e:
            # Error aane par handle karein
            messages.error(request, f"Grahak jodne me samasya: {str(e)}")
            return redirect('khata:dashboard')
            
    return render(request, 'khata/add_customer.html')


@login_required
@require_POST
def update_customer(request, b64_id):
    """Update a customer from the dashboard modal."""
    try:
        actual_id = int(base64.b64decode(b64_id).decode('utf-8'))
        customer = get_object_or_404(Customer, id=actual_id, user=request.user)
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()

        if Customer.objects.filter(user=request.user, phone=phone).exclude(id=customer.id).exists():
            messages.warning(request, "Yeh phone number pehle se hi kisi aur grahak ke naam par darj hai!")
            return redirect('khata:dashboard')

        customer.name = name
        customer.phone = phone
        customer.save()
        messages.success(request, "Grahak ki jankari safaltapoorvak update ho gayi!")
        return redirect('khata:dashboard')
    except Exception as e:
        messages.error(request, f"Grahak edit karne me error aayi: {str(e)}")
        return redirect('khata:dashboard')
@login_required
def delete_customer(request, customer_id):
    # Error Handling ke liye try block (App crash hone se rokne ke liye)
    try:
        # Check karna ki grahak isi user ka hai ya nahi
        customer = get_object_or_404(Customer, id=customer_id, user=request.user)
        
        # Pehle grahak ke saare len-den (transactions) nikalna balance check karne ke liye
        transactions = Transaction.objects.filter(customer=customer)
        
        total_given = sum(t.amount for t in transactions if t.trans_type == 'GIVEN')
        total_got = sum(t.amount for t in transactions if t.trans_type == 'GOT')
        net_balance = total_given - total_got
        
        # PRE-CHECK LOGIC: Agar balance 0 nahi hai (yani lena ya dena baki hai)
        if net_balance != 0:
            # SweetAlert is warning ko automatically pakad lega aur dikha dega
            messages.warning(
                request, 
                f"Is Customers ko delete nahi kiya ja sakta! Abhi ₹{abs(net_balance):.2f} ka hisaab baki hai."
            )
            return redirect('khata:dashboard')
            
        # Agar balance ekdum 0 hai, tabhi delete ki ijazat milegi
        customer.delete()
        messages.success(request, "Grahak ka khata safaltapoorvak hata diya gaya hai.")
        return redirect('khata:dashboard')
        
    except Exception as e:
        # Kisi bhi unexpected dikkat ko handle karne ke liye
        messages.error(request, f"Grahak hatane mein error aayi: {str(e)}")
        return redirect('khata:dashboard')


@login_required
def customer_detail(request, customer_id):
    try:
        customer = get_object_or_404(Customer, id=customer_id, user=request.user)
        
        # 1. Date filter lena
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # 2. Transactions fetch karna (Order by date)
        transactions = Transaction.objects.filter(customer=customer).order_by('date', 'id')
        
        # 3. Filter apply karna (Ab ye sahi jagah par hai)
        if start_date and end_date:
            transactions = transactions.filter(date__range=[start_date, end_date])
        
        # 4. Running Balance aur Totals ka calculation (Filtered transactions par)
        running_balance = 0
        total_given = 0
        total_got = 0
        
        for t in transactions:
            # Base64 ID for security
            t.b64_id = base64.b64encode(str(t.id).encode('utf-8')).decode('utf-8')
            
            # Balance Calculation
            if t.trans_type == 'GIVEN':
                running_balance += t.amount
                total_given += t.amount
            else:
                running_balance -= t.amount
                total_got += t.amount
            
            t.running_balance = running_balance

        # Net balance calculation
        net_balance = total_given - total_got

        # 5. POST Request handle karna (New Transaction)
        if request.method == 'POST':
            # ... (Aapka existing POST logic waisa hi rahega) ...
            amount = request.POST.get('amount')
            trans_type = request.POST.get('trans_type')
            remarks = request.POST.get('remarks')
            date_str = request.POST.get('date')
            trans_date = parse_date(date_str)
            
            new_trans = Transaction(customer=customer, amount=amount, trans_type=trans_type, remarks=remarks, date=trans_date)
            new_trans.save()
            return redirect('khata:customer_detail', customer_id=customer_id)

        # 6. Interest/Auto-months calculation
        auto_months = 0
        if transactions.exists():
            last_trans = transactions.last() 
            last_date = last_trans.date
            if hasattr(last_date, 'date'): last_date = last_date.date()
            days_passed = (timezone.now().date() - last_date).days
            if days_passed > 0:
                auto_months = round(days_passed / 30.0, 1)

        # 7. WhatsApp Logic
        whatsapp_url = ""
        if net_balance > 0:
            message = f"नमस्ते {customer.name} जी, आपका बकाया उधार ₹{net_balance:.2f} बाकी है, कृपया समय पर भुगतान करे.\nधन्यवाद!"
            encoded_message = urllib.parse.quote(message)
            phone_number = ''.join(filter(str.isdigit, customer.phone))
            if len(phone_number) == 10: phone_number = "91" + phone_number
            whatsapp_url = f"https://wa.me/{phone_number}?text={encoded_message}"
            
        context = {
            'customer': customer,
            'transactions': transactions,
            'net_balance': net_balance,
            'encoded_id': base64.b64encode(str(customer.id).encode('utf-8')).decode('utf-8'),
            'auto_months': auto_months,
            'whatsapp_url': whatsapp_url,
            'total_given': total_given,
            'total_got': total_got,
            'start_date': start_date,
            'end_date': end_date,
        }
        return render(request, 'khata/customer_detail.html', context)
        
    except Exception as e:
        messages.error(request, f"Hisaab kholne mein samasya aayi: {str(e)}")
        return redirect('khata:dashboard')

@login_required
@require_POST
def update_transaction(request, b64_trans_id):
    """Update a transaction from the customer-detail modal."""
    try:
        actual_trans_id = int(base64.b64decode(b64_trans_id).decode('utf-8'))
        trans = get_object_or_404(Transaction, id=actual_trans_id, customer__user=request.user)
        trans.amount = request.POST.get('amount')
        trans.trans_type = request.POST.get('trans_type')
        trans.remarks = request.POST.get('remarks', '').strip()
        trans.date = parse_date(request.POST.get('date'))
        trans.save()
        messages.success(request, "Len-den ki entry update ho gayi!")
        return redirect('khata:customer_detail', customer_id=trans.customer.id)
    except Exception as e:
        messages.error(request, f"Entry edit karne me samasya: {str(e)}")
        return redirect('khata:dashboard')
@login_required
def delete_transaction(request, b64_trans_id):
    # Try block error aane se rokne ke liye
    try:
        # Base64 string ko decode karke actual transaction ID nikalna
        actual_trans_id = int(base64.b64decode(b64_trans_id).decode('utf-8'))
        
        # Check karein ki ye transaction isi user ke customer ka hai
        trans = get_object_or_404(Transaction, id=actual_trans_id, customer__user=request.user)
        customer_id = trans.customer.id
        
        trans.delete()
        messages.success(request, "Len-den ki entry delete kar di gayi hai.")
        return redirect('khata:customer_detail', customer_id=customer_id)
        
    except Exception as e:
        messages.error(request, f"Entry delete karne mein samasya: {str(e)}")
        return redirect('khata:dashboard')
    

@login_required
def add_interest(request, b64_id):
    # Error Handling ke liye try block (On Error GoTo logic)
    try:
        # Base64 string se actual customer ID decode karna
        actual_id = int(base64.b64decode(b64_id).decode('utf-8'))
        customer = get_object_or_404(Customer, id=actual_id, user=request.user)

        if request.method == 'POST':
            interest_amount = request.POST.get('interest_amount')
            rate = request.POST.get('rate')
            months = request.POST.get('months')
            date_str = request.POST.get('date')
            
            trans_date = parse_date(date_str)
            
            # Custom remarks banayein taaki samajh aaye ki ye entry Byaaj ki hai
            remarks = f"Byaaj (Interest): {rate}% dar se {months} mahine ka"

            # Duplicate Check: Check karein ki same date pe same Byaaj pehle toh nahi joda gaya
            if Transaction.objects.filter(customer=customer, amount=interest_amount, trans_type='GIVEN', date=trans_date, remarks=remarks).exists():
                messages.warning(request, "Byaaj ki yeh entry is tareekh par pehle se lag chuki hai! (Duplicate Error)")
                return redirect('khata:customer_detail', customer_id=customer.id)

            # Agar duplicate nahi hai, toh nayi entry save karein
            new_trans = Transaction(
                customer=customer,
                amount=interest_amount,
                trans_type='GIVEN',  # Byaaj udhaar mein judta hai, isliye 'GIVEN'
                remarks=remarks,
                date=trans_date
            )
            new_trans.save()
            messages.success(request, f"₹{interest_amount} ka Byaaj khate mein safaltapoorvak jod diya gaya!")
            
        return redirect('khata:customer_detail', customer_id=customer.id)
        
    except Exception as e:
        # Error aane par handle karein aur dashboard par wapas bhej dein
        messages.error(request, f"Byaaj jodne mein samasya aayi: {str(e)}")
        return redirect('khata:dashboard')
    
@login_required
def download_ledger_pdf(request, b64_id):
    try:
        # Decode base64 ID
        decoded_id_str = base64.b64decode(b64_id).decode('utf-8')
        actual_customer_id = int(decoded_id_str)
        
        # Date filters URL se uthayein
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        customer = get_object_or_404(Customer, id=actual_customer_id, user=request.user)
        
        # Transactions ko filter ke sath fetch karein
        transactions = Transaction.objects.filter(customer=customer).order_by('date')
        
        if start_date and end_date:
            transactions = transactions.filter(date__range=[start_date, end_date])
            
        # Running Balance aur Totals calculation
        running_balance = 0
        total_given = 0
        total_got = 0
        
        for t in transactions:
            if t.trans_type == 'GIVEN':
                running_balance += t.amount
                total_given += t.amount
            else:
                running_balance -= t.amount
                total_got += t.amount
            t.running_balance = running_balance
            
        net_balance = total_given - total_got
        
        # Template Context
        context = {
            'customer': customer,
            'transactions': transactions,
            'net_balance': net_balance,
            'total_given': total_given,
            'total_got': total_got,
            'start_date': start_date,
            'end_date': end_date,
        }
        
        # PDF Generate Logic
        template_path = 'khata/pdf_template.html'
        template = get_template(template_path)
        html = template.render(context)
        
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Hisaab_{customer.name}.pdf"'
        
        pisa_status = pisa.CreatePDF(html, dest=response)
        
        if pisa_status.err:
            messages.error(request, "PDF generate karne mein error aayi.")
            return redirect('khata:customer_detail', customer_id=customer.id)
            
        return response
        
    except Exception as e:
        messages.error(request, f"PDF report nikalne me samasya: {str(e)}")
        return redirect('khata:dashboard')

@login_required
def shop_profile(request):
    # Error Handling start: Code me koi gadbad ho to app safe rahe
    try:
        # Existence Check: User ka profile nikalna, nahi hai toh naya bana dena
        profile, created = ShopProfile.objects.get_or_create(user=request.user)

        if request.method == 'POST':
            shop_name = request.POST.get('shop_name')
            address = request.POST.get('address')
            phone = request.POST.get('phone')

            # Data update karke save karna
            profile.shop_name = shop_name
            profile.address = address
            profile.phone = phone
            profile.save()
            
            messages.success(request, "Dukaan ka profile safaltapoorvak update ho gaya!")
            return redirect('khata:dashboard')

        context = {
            'profile': profile
        }
        return render(request, 'khata/shop_profile.html', context)

    except Exception as e:
        # Kuch dikkat aane par error message show karein
        messages.error(request, f"Profile kholne mein samasya aayi: {str(e)}")
        return redirect('khata:dashboard')


@login_required
def report_page(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # 1. Base transactions
    transactions = Transaction.objects.filter(customer__user=request.user).order_by('-date')
    
    # 2. Date wise filter (pehle filter karein)
    if start_date and end_date:
        transactions = transactions.filter(date__range=[start_date, end_date])
    
    # 3. Pagination (limit 10 ya 20)
    paginator = Paginator(transactions, 15) 
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # 4. Loop sirf page_obj par chalayein (taaki sirf dikhne wale data par kaam ho)
    for trans in page_obj:
        # Customer ID ko secure karke encode karein
        trans.customer.b64_id = base64.b64encode(str(trans.customer.id).encode('utf-8')).decode('utf-8')
    
    context = {
        'transactions': page_obj,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'khata/report.html', context)
