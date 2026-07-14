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
    return render(request, 'core/solution_detail.html', {'solution': solution})


def contact(request):
    return render(request, 'core/contact.html')


@login_required
def dashboard(request):
    return render(request, 'core/dashboard.html')