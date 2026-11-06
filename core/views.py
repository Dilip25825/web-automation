from django.contrib.auth.decorators import login_required
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce, TruncDate
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from khata.access import menu_permissions, request_operator_settings
from khata.models import Transaction
from licensing.activation_ledger import search_only_operator
from licensing.models import UserInfoData, tblPacsErp


SOLUTIONS = {
    'excel-work-automation': {
        'title': 'Excel Work Automation', 'eyebrow': 'Smarter spreadsheets', 'icon': 'fa-file-excel',
        'summary': 'Repetitive Excel work, reports aur data processing ko fast, accurate aur repeatable workflows mein badlein.',
        'description': 'Hum aapke existing Excel process ko samajhkar data cleaning, report generation, file consolidation aur routine entries ko automate karne mein madad karte hain.',
        'features': ['Multiple Excel files ko merge aur clean karna', 'Repeat hone wali reports automatically banana', 'Data validation aur formatting errors kam karna', 'Custom workflow ke hisab se automation'],
        'best_for': 'Teams aur operators jo roz ek jaise Excel steps manually repeat karte hain.',
    },
    'krp-automation': {
        'title': 'KRP Automation', 'eyebrow': 'Faster KRP operations', 'icon': 'fa-gears',
        'summary': 'KRP ke structured data aur routine operational steps ko simple aur time-saving banayein.',
        'description': 'Loan application, IS PRI aur rollover jaise KRP workflows ke liye practical automation support, jisse manual effort aur avoidable mistakes kam hon.',
        'features': ['Loan application workflow support', 'IS PRI process automation', 'Rollover process support', 'Structured data handling aur review'],
        'best_for': 'KRP operators aur organisations jinhe consistent, repeatable processing chahiye.',
    },
    'erp-automation': {
        'title': 'ERP Automation', 'eyebrow': 'Reliable ERP workflows', 'icon': 'fa-building-columns',
        'summary': 'ERP-related records, setup aur routine operations ko cleaner automated process se manage karein.',
        'description': 'New ERP setup aur renewal workflows ke liye organised support, record tracking aur repetitive operational work mein automation.',
        'features': ['New ERP workflow support', 'ERP renewal process', 'Record organisation aur tracking', 'Routine steps mein manual effort kam'],
        'best_for': 'PACS aur ERP operators jo records aur regular operational tasks ko streamline karna chahte hain.',
    },
    'pmfby-automation': {
        'title': 'PMFBY Automation', 'eyebrow': 'Organised insurance workflows', 'icon': 'fa-wheat-awn',
        'summary': 'PMFBY information, tracking aur repetitive processing ko organised automation ke saath handle karein.',
        'description': 'Kharif aur Opt-out workflows ke liye data handling aur process support, taaki seasonal workload ko zyada efficiently manage kiya ja sake.',
        'features': ['Kharif workflow support', 'PMFBY Opt-out automation', 'Organised information processing', 'Tracking aur repetitive work mein time saving'],
        'best_for': 'PMFBY process se jude operators aur teams jinke paas seasonal high-volume work hota hai.',
    },
}


def home(request):
    return render(request, 'core/home.html')


def pricing(request):
    return render(request, 'core/pricing.html')


def solution_detail(request, slug):
    solution = SOLUTIONS.get(slug)
    if solution is None:
        raise Http404('Solution not found')
    template_name = 'core/solution_detail.html'
    steps = []
    guide = None
    if slug == 'pmfby-automation':
        template_name = 'core/pmfby_automation.html'
        steps = [(1, 'Data taiyar karein', 'Columns, format aur duplicates check karein.'), (2, 'Portal login karein', 'Authorized login se sahi season select karein.'), (3, 'Automation Entry kholein', 'Menu se upload option par jaayein.'), (4, 'File upload karein', 'Sahi file upload karke processing complete hone dein.'), (5, 'Errors resolve karein', 'Validation errors sudhar kar dobara upload karein.'), (6, 'Verify aur submit karein', 'Record count match karke submit aur status save karein.')]
    elif slug == 'krp-automation':
        template_name = 'core/krp_automation.html'
        steps = [(1, 'Application data taiyar karein', 'Member, loan, crop aur required details verify karein.'), (2, 'Portal login karein', 'Authorized login se sahi organisation aur workflow select karein.'), (3, 'Loan Application option kholein', 'Kisan Loan Application upload section par jaayein.'), (4, 'File ya data upload karein', 'Sahi file select karke portal processing complete hone dein.'), (5, 'Validation errors sudharein', 'Error report ke records correct karke dobara upload karein.'), (6, 'Verify aur final submit karein', 'Record count aur details check karke status/reference save karein.')]
    elif slug == 'erp-automation':
        template_name = 'core/workflow_guide.html'
        guide = {
            'page_title': 'ERP Loan Collection Entry Automation Guide',
            'eyebrow': 'ERP Public Guide',
            'heading': 'ERP mein Loan Collection Entry Excel se automate kaise karein?',
            'summary': 'Excel data ko prepare karke sahi Activity Type ke saath ERP loan collection entries ko accurate aur repeatable workflow mein process karein.',
            'video_label': 'ERP Step-by-step video',
            'media_type': 'video',
            'icon': 'fa-building-columns',
            'checklist': ['Authorized ERP login taiyar rakhein.', 'Loan aur collection Excel data verify karein.', 'Sahi Activity Type aur transaction date confirm karein.', 'Stable internet aur original data backup rakhein.'],
            'workflow_label': 'ERP workflow',
            'workflow_title': 'Loan Collection Entry automation process',
            'workflow_note': 'ERP version ke anusaar field names badal sakte hain. Final posting se pehle preview aur totals verify karein.',
            'steps': [(1, 'Excel data taiyar karein', 'Member, loan account, date aur amount columns clean karein.'), (2, 'Activity Type samjhein', 'Collection ke liye sahi activity aur transaction category select karein.'), (3, 'ERP login aur screen kholein', 'Authorized login se Loan Collection Entry section par jaayein.'), (4, 'Automation run karein', 'Verified Excel file select karke controlled entry process shuru karein.'), (5, 'Errors aur totals check karein', 'Skipped rows, invalid accounts aur total amount verify karein.'), (6, 'Final post aur report save karein', 'Correct entries post karke reference/report ka backup rakhein.')],
            'problems_title': 'ERP entry mein kya check karein?',
            'problems': [('Wrong Activity Type', 'Loan collection ke liye mapped activity dobara check karein.'), ('Account not found', 'Member aur loan account number ERP record se match karein.'), ('Amount mismatch', 'Excel total aur ERP preview total compare karein.'), ('Duplicate entry', 'Date, reference aur already-posted collection verify karein.')],
            'cta_title': 'ERP entry workload ko simple banayein',
            'cta_text': 'High-volume collection entry, ERP setup aur renewal workflows ke liye suitable automation discuss karein.',
            'whatsapp_text': 'Namaste, mujhe ERP Loan Collection Automation ke baare mein jankari chahiye.',
        }
    elif slug == 'excel-work-automation':
        template_name = 'core/workflow_guide.html'
        guide = {
            'page_title': 'Excel Work Automation Guide',
            'eyebrow': 'Excel Automation Guide',
            'heading': 'Repetitive Excel work ko automation mein kaise badlein?',
            'summary': 'ERP Loan Collection Entry jaise repeat hone wale data-entry work ko clean Excel data, validation aur controlled automation se fast aur reliable banayein.',
            'video_label': 'Excel Automation Visual',
            'media_type': 'image',
            'icon': 'fa-file-excel',
            'checklist': ['Original Excel file ka backup rakhein.', 'Column names aur data format standard rakhein.', 'Blank, duplicate aur invalid rows identify karein.', 'Chhote sample data par pehle test karein.'],
            'workflow_label': 'Excel automation workflow',
            'workflow_title': 'Manual Excel process ko automate karne ke steps',
            'workflow_note': 'Automation se pehle business rules aur expected output ko clearly define karna sabse zaroori hai.',
            'steps': [(1, 'Manual process identify karein', 'Roz repeat hone wale clicks, calculations aur entries list karein.'), (2, 'Input format standard karein', 'Fixed columns, data types aur mandatory fields define karein.'), (3, 'Validation rules banayein', 'Blank, duplicate, invalid date aur amount errors detect karein.'), (4, 'Automation workflow run karein', 'Verified data ko target report ya software process mein use karein.'), (5, 'Exception report review karein', 'Failed rows ko reason ke saath alag karke correct karein.'), (6, 'Output reconcile karein', 'Source totals aur final output compare karke audit copy save karein.')],
            'problems_title': 'Excel automation fail ho to',
            'problems': [('Changed columns', 'Template headings aur column order standard format se match karein.'), ('Mixed data types', 'Date, number aur text values ko consistent format dein.'), ('Blank or duplicate rows', 'Validation aur unique reference se bad data filter karein.'), ('Unexpected output', 'Small sample par rules aur totals dobara verify karein.')],
            'cta_title': 'Apna Excel workflow automate karein',
            'cta_text': 'File merging, data cleaning, reports aur repetitive software entry ke liye custom automation discuss karein.',
            'whatsapp_text': 'Namaste, mujhe Excel Work Automation ke baare mein jankari chahiye.',
        }
    return render(request, template_name, {'solution': solution, 'steps': steps, 'guide': guide})


def contact(request):
    return render(request, 'core/contact.html')


@login_required
def dashboard(request):
    permissions = getattr(request, 'menu_permissions', menu_permissions(request.user))
    operator_settings = request_operator_settings(request)
    today = timezone.localdate()
    dashboard_metrics = []
    activity_points = []
    recent_licenses = []
    report_insights = []
    report_links = []
    month_start = today.replace(day=1)

    userinfo_records = UserInfoData.objects.none()
    if permissions.get('user_licenses'):
        userinfo_records = UserInfoData.objects.all()
        if not request.user.is_superuser:
            userinfo_records = userinfo_records.filter(
                Q(accepte_by__icontains=request.user.username)
                | Q(accepte_by__isnull=True)
                | Q(accepte_by__exact='')
            )
        if search_only_operator(request.user, operator_settings):
            userinfo_records = userinfo_records.none()
        userinfo_totals = userinfo_records.aggregate(total=Count('pk'))
        dashboard_metrics.append({
            'label': 'Total User Licences',
            'value': userinfo_totals['total'],
            'icon': 'fa-users',
            'tone': 'indigo',
            'url': reverse('licensing:userinfo_dashboard'),
        })
        # Financial totals are intentionally restricted to the superuser dashboard.
        if request.user.is_superuser:
            financial_totals = userinfo_records.aggregate(
                amount=Coalesce(Sum('amount'), 0),
                received=Coalesce(Sum('payment_status'), 0),
            )
            dashboard_metrics.extend([
                {'label': 'Total Licence Amount', 'value': financial_totals['amount'], 'currency': True, 'icon': 'fa-indian-rupee-sign', 'tone': 'violet', 'url': reverse('licensing:userinfo_dashboard')},
                {'label': 'Received Amount', 'value': financial_totals['received'], 'currency': True, 'icon': 'fa-circle-check', 'tone': 'emerald', 'url': reverse('licensing:userinfo_dashboard')},
            ])
            report_insights.extend([
                {'label': 'This Month Activations', 'value': userinfo_records.filter(date_time__date__gte=month_start).count(), 'detail': month_start.strftime('%B %Y'), 'icon': 'fa-calendar-check', 'tone': 'indigo'},
                {'label': 'Pending Collection', 'value': max(0, (financial_totals['amount'] or 0) - (financial_totals['received'] or 0)), 'detail': 'Licence amount not received', 'currency': True, 'icon': 'fa-wallet', 'tone': 'rose'},
            ])
        report_links.append({'label': 'User Activation Report', 'detail': 'Date-wise licences and collection', 'icon': 'fa-chart-column', 'url': reverse('licensing:userinfo_activation_report'), 'tone': 'indigo'})

        start_date = today - timedelta(days=29)
        activity_by_day = dict(
            userinfo_records.filter(date_time__date__gte=start_date)
            .annotate(day=TruncDate('date_time'))
            .values('day').annotate(total=Count('pk')).values_list('day', 'total')
        )
        activity_points = [
            {'label': (start_date + timedelta(days=offset)).strftime('%d %b'), 'total': activity_by_day.get(start_date + timedelta(days=offset), 0)}
            for offset in range(30)
        ]

    erp_records = tblPacsErp.objects.none()
    if permissions.get('erp_licenses'):
        erp_records = tblPacsErp.objects.all()
        if not request.user.is_superuser:
            erp_records = erp_records.filter(
                Q(expiry_date__lt=today) | Q(accepte_by__iexact=request.user.username)
            ).exclude(erp_id__iendswith=' Expired')
        if search_only_operator(request.user, operator_settings):
            erp_records = erp_records.none()
        erp_totals = erp_records.aggregate(total=Count('pk'), active=Count('pk', filter=Q(is_active=1)))
        dashboard_metrics.append({'label': 'ERP Licences', 'value': erp_totals['total'], 'detail': f"{erp_totals['active']} active", 'icon': 'fa-building-columns', 'tone': 'sky', 'url': reverse('licensing:pacserp_dashboard')})
        if request.user.is_superuser:
            report_insights.append({'label': 'ERP Renewals Due', 'value': erp_records.filter(expiry_date__gte=today, expiry_date__lte=today + timedelta(days=30)).count(), 'detail': 'Next 30 days', 'icon': 'fa-calendar-days', 'tone': 'amber'})
        report_links.append({'label': 'ERP Activation Report', 'detail': 'ERP activations and collection', 'icon': 'fa-file-chart-column', 'url': reverse('licensing:erp_activation_report'), 'tone': 'sky'})

    if permissions.get('khata'):
        khata_today = Transaction.objects.filter(customer__user=request.user, date=today).aggregate(
            total=Count('pk'),
            given=Coalesce(
                Sum('amount', filter=Q(trans_type='GIVEN')),
                Value(Decimal('0'), output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
            received=Coalesce(
                Sum('amount', filter=Q(trans_type='GOT')),
                Value(Decimal('0'), output_field=DecimalField(max_digits=10, decimal_places=2)),
            ),
        )
        dashboard_metrics.append({'label': "Today's Khata Transactions", 'value': khata_today['total'], 'detail': f"₹{khata_today['given']} given · ₹{khata_today['received']} received", 'icon': 'fa-book-open', 'tone': 'amber', 'url': reverse('khata:dashboard')})
        report_links.append({'label': 'Khata Report', 'detail': 'Ledger and transaction summary', 'icon': 'fa-book-open', 'url': reverse('khata:report_page'), 'tone': 'emerald'})

    for record in userinfo_records.order_by('-date_time')[:5]:
        recent_licenses.append(SimpleNamespace(
            label=record.hero_pacs_name,
            kind='User Licence',
            amount=record.amount or 0,
            status='Active' if record.is_active else 'Inactive',
            status_tone='active' if record.is_active else 'inactive',
            date_value=record.date_time,
            url=reverse('licensing:userinfo_dashboard'),
        ))
    for record in erp_records.order_by('-date_time')[:5]:
        recent_licenses.append(SimpleNamespace(
            label=record.hero_pacs_name,
            kind='ERP Licence',
            amount=record.current_amount or record.amount or 0,
            status='Active' if record.is_active else 'Inactive',
            status_tone='active' if record.is_active else 'inactive',
            date_value=record.date_time,
            url=reverse('licensing:pacserp_dashboard'),
        ))
    recent_licenses.sort(key=lambda item: item.date_value or timezone.now(), reverse=True)

    max_activity = max((point['total'] for point in activity_points), default=0) or 1
    for point in activity_points:
        point['height'] = max(5, round((point['total'] / max_activity) * 100))

    return render(request, 'core/dashboard.html', {
        'dashboard_metrics': dashboard_metrics,
        'activity_points': activity_points,
        'recent_licenses': recent_licenses[:6],
        'report_insights': report_insights,
        'report_links': report_links,
    })


def documentation(request):
    return render(request, 'core/documentation.html')


def client_guide(request):
    return render(request, 'core/client_guide.html')


def erp_guide(request):
    return render(request, 'core/erp_guide.html')


def terms_and_conditions(request):
    return render(request, 'core/terms_and_conditions.html')


def refund_policy(request):
    return render(request, 'core/refund_policy.html')


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


def ads_txt(request):
    return HttpResponse(
        'google.com, pub-6094868873003811, DIRECT, f08c47fec0942fa0\n',
        content_type='text/plain; charset=utf-8',
    )
