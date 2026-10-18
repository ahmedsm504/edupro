import logging

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.notifications.services import notify

from .models import Coupon, Order, Transaction

logger = logging.getLogger(__name__)


def apply_coupon(code, kind, amount):
    if not code:
        return None, 0
    c = Coupon.objects.filter(code=code.strip().upper()).first()
    if not c or not c.is_valid_for(kind):
        raise BusinessError("كود الخصم غير صالح.", code="invalid_coupon")
    return c, c.discount_for(amount)


@transaction.atomic
def fulfill(order_id, method=None, gateway_payload=None):
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status == "paid":
        return order
    order.status = "paid"
    order.paid_at = timezone.now()
    if method:
        order.method = method
    order.save()
    if order.coupon_id:
        Coupon.objects.filter(pk=order.coupon_id).update(used_count=F("used_count") + 1)
    if order.kind == "subscription" and order.subscription:
        from apps.tutoring.services import mark_subscription_paid
        mark_subscription_paid(order.subscription, amount=order.total)
    elif order.kind == "course" and order.course:
        from apps.courses.services import enroll
        enroll(order.student, order.course, source="purchase" if order.total > 0 else "free")
    if order.user_id != order.student_id:
        notify(order.user, "payment_success", "تم الدفع بنجاح ✅", order.title, {"screen": "order", "id": order.id})
    return order


def handle_paymob_transaction(obj: dict):
    """obj = payload['obj'] من webhook بتاع Paymob."""
    ref = obj.get("order", {}).get("merchant_order_id") or obj.get("special_reference") or ""
    pm_order_id = str(obj.get("order", {}).get("id", ""))
    order = None
    if ref:
        order = Order.objects.filter(reference=ref).first() if len(ref) == 36 else None
    if not order and pm_order_id:
        order = Order.objects.filter(paymob_order_id=pm_order_id).first()
    if not order:
        extras = (obj.get("payment_key_claims") or {}).get("extra") or {}
        if extras.get("order_id"):
            order = Order.objects.filter(pk=extras["order_id"]).first()
    if not order:
        logger.warning("Paymob webhook: order not found ref=%s pm=%s", ref, pm_order_id)
        return None
    if pm_order_id and not order.paymob_order_id:
        order.paymob_order_id = pm_order_id
        order.save(update_fields=["paymob_order_id"])
    success = obj.get("success") is True and not obj.get("pending") and not obj.get("is_voided") and not obj.get("is_refunded")
    Transaction.objects.create(order=order, gateway_id=str(obj.get("id")), success=success,
                               amount_cents=obj.get("amount_cents") or 0,
                               source_type=(obj.get("source_data") or {}).get("type", ""), raw=obj)
    if success:
        if int(obj.get("amount_cents") or 0) < int(order.total * 100):
            logger.error("Paymob amount mismatch for order %s", order.id)
            return order
        return fulfill(order.id, method="paymob")
    if obj.get("is_refunded"):
        order.status = "refunded"
        order.save(update_fields=["status"])
    elif order.status == "pending" and not obj.get("pending"):
        order.status = "failed"
        order.save(update_fields=["status"])
        notify(order.user, "payment_failed", "فشلت عملية الدفع", "جرّب تاني أو استخدم وسيلة دفع مختلفة.",
               {"screen": "order", "id": order.id})
    return order
