from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render


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
    return render(request, 'core/dashboard.html')


@login_required
def documentation(request):
    return render(request, 'core/documentation.html')
