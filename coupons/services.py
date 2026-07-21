import base64
import secrets

from .models import Coupon


def _new_128_bit_code():
    token = base64.b32encode(secrets.token_bytes(16)).decode("ascii").rstrip("=")
    groups = (token[:5], token[5:10], token[10:15], token[15:20], token[20:])
    return "CPN-" + "-".join(groups)


def generate_coupon_code(discount_amount):
    amount = int(discount_amount)
    if amount <= 0:
        raise ValueError("Discount amount must be greater than zero.")
    for _ in range(25):
        code = _new_128_bit_code()
        if not Coupon.objects.filter(coupon_code=code).exists():
            return code
    raise RuntimeError("Could not generate a unique coupon code. Please try again.")


def generate_coupon_codes(discount_amount, quantity):
    amount = int(discount_amount)
    count = int(quantity)
    if amount <= 0:
        raise ValueError("Discount amount must be greater than zero.")
    if count <= 0 or count > 500:
        raise ValueError("Quantity must be between 1 and 500.")
    generated = set()
    attempts = 0
    while len(generated) < count and attempts < count * 25:
        attempts += 1
        generated.add(_new_128_bit_code())
    if len(generated) != count:
        raise RuntimeError("Could not generate enough unique coupon codes. Please try again.")
    return list(generated)
