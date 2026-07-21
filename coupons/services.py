import secrets
import string

from .models import Coupon


COUPON_ALPHABET = string.ascii_uppercase + string.digits


def generate_coupon_code(discount_amount):
    amount = int(discount_amount)
    if amount <= 0:
        raise ValueError('Discount amount must be greater than zero.')
    for _ in range(25):
        first = ''.join(secrets.choice(COUPON_ALPHABET) for _ in range(5))
        second = ''.join(secrets.choice(COUPON_ALPHABET) for _ in range(5))
        code = f'SAVE{amount}-{first}-{second}'
        if not Coupon.objects.filter(coupon_code=code).exists():
            return code
    raise RuntimeError('Could not generate a unique coupon code. Please try again.')



def generate_coupon_codes(discount_amount, quantity):
    amount = int(discount_amount)
    count = int(quantity)
    if amount <= 0:
        raise ValueError('Discount amount must be greater than zero.')
    if count <= 0 or count > 500:
        raise ValueError('Quantity must be between 1 and 500.')
    existing = set(Coupon.objects.filter(coupon_code__startswith=f'SAVE{amount}-').values_list('coupon_code', flat=True))
    generated = set()
    attempts = 0
    while len(generated) < count and attempts < count * 25:
        attempts += 1
        first = ''.join(secrets.choice(COUPON_ALPHABET) for _ in range(5))
        second = ''.join(secrets.choice(COUPON_ALPHABET) for _ in range(5))
        code = f'SAVE{amount}-{first}-{second}'
        if code not in existing:
            generated.add(code)
    if len(generated) != count:
        raise RuntimeError('Could not generate enough unique coupon codes. Please try again.')
    return list(generated)