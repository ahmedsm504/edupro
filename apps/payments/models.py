import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

User = settings.AUTH_USER_MODEL


class Coupon(TimeStampedModel):
    APPLIES = [("all", "الكل"), ("subscription", "اشتراكات الحصص"), ("course", "الكورسات")]
    code = models.CharField(max_length=40, unique=True)
    percent_off = models.PositiveSmallIntegerField(null=True, blank=True)
    amount_off = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    applies_to = models.CharField(max_length=15, choices=APPLIES, default="all")
    max_uses = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def is_valid_for(self, kind):
        now = timezone.now()
        return (self.is_active and (self.applies_to in ("all", kind))
                and (not self.max_uses or self.used_count < self.max_uses)
                and (not self.valid_from or self.valid_from <= now)
                and (not self.valid_until or now <= self.valid_until))

    def discount_for(self, amount: Decimal) -> Decimal:
        d = Decimal(0)
        if self.percent_off:
            d = (amount * Decimal(self.percent_off) / 100).quantize(Decimal("0.01"))
        elif self.amount_off:
            d = self.amount_off
        return min(d, amount)

    def save(self, *a, **kw):
        self.code = self.code.strip().upper()
        super().save(*a, **kw)


class Order(TimeStampedModel):
    KINDS = [("subscription", "اشتراك حصص"), ("course", "كورس")]
    STATUS = [("pending", "في انتظار الدفع"), ("paid", "مدفوع"), ("failed", "فشل"), ("cancelled", "ملغي"), ("refunded", "مسترد")]
    METHODS = [("paymob", "Paymob"), ("manual", "يدوي/كاش"), ("free", "مجاني")]

    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders", help_text="اللي دفع (طالب أو ولي أمر)")
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+", help_text="المستفيد")
    kind = models.CharField(max_length=15, choices=KINDS)
    subscription = models.ForeignKey("tutoring.Subscription", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    course = models.ForeignKey("courses.Course", null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="EGP")
    coupon = models.ForeignKey(Coupon, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, choices=STATUS, default="pending", db_index=True)
    method = models.CharField(max_length=10, choices=METHODS, default="paymob")
    paymob_intention_id = models.CharField(max_length=100, blank=True)
    paymob_order_id = models.CharField(max_length=100, blank=True, db_index=True)
    client_secret = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def title(self):
        if self.kind == "course" and self.course:
            return self.course.title
        if self.subscription:
            return f"{self.subscription.package.name} - {self.subscription.subject}"
        return self.get_kind_display()


class Transaction(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="transactions")
    gateway_id = models.CharField(max_length=100, db_index=True)
    success = models.BooleanField(default=False)
    amount_cents = models.BigIntegerField(default=0)
    source_type = models.CharField(max_length=40, blank=True, help_text="card / wallet / kiosk ...")
    raw = models.JSONField(default=dict)
