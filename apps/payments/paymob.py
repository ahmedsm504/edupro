"""
Paymob Unified Checkout (Intention API).
التدفق:
 1) السيرفر يعمل intention → يرجع client_secret.
 2) التطبيق يفتح checkout_url في WebView (أو Paymob Flutter SDK بالـ public_key + client_secret).
 3) Paymob يبعت webhook (Transaction processed callback) على /api/v1/payments/paymob/webhook/ → نتحقق من HMAC ونفعّل.
 4) بعد الدفع Paymob يحوّل لـ redirection_url → صفحة نجاح/فشل. التطبيق يراقب الـ URL ده في الـ WebView ويقفل.
"""
import hashlib
import hmac
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

HMAC_FIELDS = [
    "amount_cents", "created_at", "currency", "error_occured", "has_parent_transaction", "id", "integration_id",
    "is_3d_secure", "is_auth", "is_capture", "is_refunded", "is_standalone_payment", "is_voided", "order.id", "owner",
    "pending", "source_data.pan", "source_data.sub_type", "source_data.type", "success",
]


class PaymobError(Exception):
    pass


def create_intention(order, billing):
    if not settings.PAYMOB_SECRET_KEY:
        raise PaymobError("Paymob غير مفعّل (PAYMOB_SECRET_KEY).")
    cents = int(order.total * 100)
    body = {
        "amount": cents,
        "currency": order.currency,
        "payment_methods": settings.PAYMOB_INTEGRATION_IDS,
        "items": [{"name": order.title[:50], "amount": cents, "description": order.get_kind_display(), "quantity": 1}],
        "billing_data": billing,
        "special_reference": str(order.reference),
        "notification_url": f"{settings.SITE_URL}/api/v1/payments/paymob/webhook/",
        "redirection_url": f"{settings.SITE_URL}/payments/result/",
        "extras": {"order_id": order.id},
    }
    r = requests.post(f"{settings.PAYMOB_BASE_URL}/v1/intention/", json=body,
                      headers={"Authorization": f"Token {settings.PAYMOB_SECRET_KEY}"}, timeout=20)
    if r.status_code >= 300:
        logger.error("Paymob intention failed %s %s", r.status_code, r.text)
        raise PaymobError("تعذر إنشاء عملية الدفع، حاول تاني.")
    return r.json()


def checkout_url(client_secret):
    return f"{settings.PAYMOB_BASE_URL}/unifiedcheckout/?publicKey={settings.PAYMOB_PUBLIC_KEY}&clientSecret={client_secret}"


def _get(obj, dotted):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict):
            return ""
        cur = cur.get(part, "")
    return cur


def _fmt(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    return "" if v is None else str(v)


def verify_hmac_webhook(obj: dict, received: str) -> bool:
    msg = "".join(_fmt(_get(obj, f)) for f in HMAC_FIELDS)
    calc = hmac.new(settings.PAYMOB_HMAC_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return hmac.compare_digest(calc, (received or "").lower())


def verify_hmac_redirect(params: dict) -> bool:
    """في الـ redirect (GET) الحقول جاية flat: order بدل order.id و source_data.pan كما هي."""
    keys = [("order" if f == "order.id" else f) for f in HMAC_FIELDS]
    msg = "".join(params.get(k, "") for k in keys)
    calc = hmac.new(settings.PAYMOB_HMAC_SECRET.encode(), msg.encode(), hashlib.sha512).hexdigest()
    return hmac.compare_digest(calc, (params.get("hmac") or "").lower())
