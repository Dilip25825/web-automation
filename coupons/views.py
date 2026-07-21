from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from .forms import CouponForm
from .models import Coupon
from .services import generate_coupon_code, generate_coupon_codes


def superuser_required(view_func):
    @login_required(login_url='accounts:login')
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Superuser access is required.'}, status=403)
            return HttpResponseForbidden('Superuser access is required.')
        return view_func(request, *args, **kwargs)
    return wrapped


def _coupon_queryset(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'active').strip().lower() or 'active'
    coupons = Coupon.objects.all()
    if status_filter == 'inactive':
        coupons = coupons.filter(status=False)
    else:
        status_filter = 'active'
        coupons = coupons.filter(status=True)
    if query:
        filters = Q(coupon_code__icontains=query) | Q(used_by__icontains=query) | Q(remark__icontains=query)
        if query.isdigit():
            filters |= Q(id=int(query)) | Q(discount_amount=int(query))
        coupons = coupons.filter(filters)
    return coupons.order_by('id'), query, status_filter


@superuser_required
def dashboard(request):
    coupons, query, status_filter = _coupon_queryset(request)
    paginator = Paginator(coupons, 10)
    page = paginator.get_page(request.GET.get('page'))
    page_range = paginator.get_elided_page_range(page.number, on_each_side=2, on_ends=1)
    context = {'coupons': page, 'page_range': page_range, 'query': query, 'status_filter': status_filter, 'coupon_form': CouponForm()}
    template = 'coupons/_results.html' if request.GET.get('partial') == '1' else 'coupons/dashboard.html'
    return render(request, template, context)


@superuser_required
@require_GET
def generate_code(request):
    amount = request.GET.get('amount', '').strip()
    if not amount.isdigit() or int(amount) <= 0:
        return JsonResponse({'success': False, 'message': 'Enter a valid discount amount first.'}, status=400)
    return JsonResponse({'success': True, 'coupon_code': generate_coupon_code(int(amount))})


@superuser_required
@require_POST
def create_coupon(request):
    data = request.POST.copy()
    if not data.get('coupon_code') and data.get('discount_amount', '').isdigit():
        data['coupon_code'] = generate_coupon_code(int(data['discount_amount']))
    form = CouponForm(data)
    if form.is_valid():
        coupon = form.save()
        return JsonResponse({'success': True, 'message': f'Coupon {coupon.coupon_code} created successfully.'})
    return JsonResponse({'success': False, 'message': 'Please correct the highlighted fields.', 'errors': form.errors.get_json_data()}, status=400)


@superuser_required
@require_POST
def bulk_create_coupons(request):
    amount = request.POST.get('discount_amount', '').strip()
    quantity = request.POST.get('quantity', '').strip()
    if not amount.isdigit() or int(amount) <= 0:
        return JsonResponse({'success': False, 'message': 'Enter a valid discount amount.'}, status=400)
    if not quantity.isdigit() or not 1 <= int(quantity) <= 500:
        return JsonResponse({'success': False, 'message': 'Quantity must be between 1 and 500.'}, status=400)
    codes = generate_coupon_codes(int(amount), int(quantity))
    status = request.POST.get('status') == 'on'
    remark = request.POST.get('remark', '').strip() or None
    with transaction.atomic():
        Coupon.objects.bulk_create([
            Coupon(coupon_code=code, discount_amount=int(amount), status=status, remark=remark)
            for code in codes
        ])
    return JsonResponse({'success': True, 'message': f'{len(codes)} unique coupons generated successfully.'})

@superuser_required
@require_POST
def update_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    form = CouponForm(request.POST, instance=coupon)
    if form.is_valid():
        coupon = form.save()
        return JsonResponse({'success': True, 'message': f'Coupon {coupon.coupon_code} updated successfully.'})
    return JsonResponse({'success': False, 'message': 'Please correct the highlighted fields.', 'errors': form.errors.get_json_data()}, status=400)


@superuser_required
@require_POST
def delete_coupon(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    code = coupon.coupon_code
    coupon.delete()
    return JsonResponse({'success': True, 'message': f'Coupon {code} deleted successfully.'})

