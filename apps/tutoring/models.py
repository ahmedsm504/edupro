import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel

User = settings.AUTH_USER_MODEL
WEEKDAYS = [(0, "الاثنين"), (1, "الثلاثاء"), (2, "الأربعاء"), (3, "الخميس"), (4, "الجمعة"), (5, "السبت"), (6, "الأحد")]


class Package(TimeStampedModel):
    """باقة الحصص: مثال 8 حصص شهرياً × 60 دقيقة بـ 800 جنيه."""
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    subject = models.ForeignKey("catalog.Subject", null=True, blank=True, on_delete=models.SET_NULL,
                                related_name="packages", help_text="فاضي = تصلح لأي مادة")
    sessions_count = models.PositiveIntegerField(help_text="عدد الحصص في الباقة")
    session_duration = models.PositiveIntegerField(default=60, help_text="مدة الحصة بالدقائق")
    duration_days = models.PositiveIntegerField(default=30, help_text="صلاحية الباقة بالأيام")
    price = models.DecimalField(max_digits=10, decimal_places=2)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EGP")
    is_trial = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "price"]

    def __str__(self):
        return self.name


class TeacherAvailability(TimeStampedModel):
    """مواعيد المدرس المتاحة أسبوعياً (بتوقيت المدرس user.timezone)."""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="availability")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]


class Subscription(TimeStampedModel):
    STATUS = [
        ("pending_payment", "في انتظار الدفع"),
        ("pending_assignment", "في انتظار تعيين المدرس والمواعيد"),
        ("active", "نشط"),
        ("paused", "متوقف مؤقتاً"),
        ("expired", "منتهي"),
        ("cancelled", "ملغي"),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    teacher = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="teaching_subscriptions")
    preferred_teacher = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT, related_name="subscriptions")
    package = models.ForeignKey(Package, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=20, choices=STATUS, default="pending_payment", db_index=True)
    sessions_total = models.PositiveIntegerField(default=0)
    sessions_used = models.PositiveIntegerField(default=0)
    session_duration = models.PositiveIntegerField(default=60)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    preferred_times = models.TextField(blank=True, help_text="المواعيد اللي الطالب يفضلها (نص حر)")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def sessions_remaining(self):
        return max(self.sessions_total - self.sessions_used, 0)

    def __str__(self):
        return f"#{self.id} {self.student} - {self.subject}"


class WeeklySlot(models.Model):
    """جدول الطالب الثابت داخل الاشتراك (بتوقيت المدرس)."""
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="slots")
    weekday = models.PositiveSmallIntegerField(choices=WEEKDAYS)
    start_time = models.TimeField()

    class Meta:
        ordering = ["weekday", "start_time"]


def _room():
    return f"{settings.JITSI_ROOM_PREFIX}-{uuid.uuid4().hex[:16]}"


class Session(TimeStampedModel):
    """الحصة اللايف."""
    STATUS = [
        ("scheduled", "مجدولة"),
        ("live", "جارية الآن"),
        ("completed", "تمت"),
        ("cancelled", "ملغاة"),
        ("student_absent", "غياب الطالب"),
        ("teacher_absent", "غياب المدرس"),
    ]
    subscription = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL, related_name="sessions")
    teacher = models.ForeignKey(User, on_delete=models.PROTECT, related_name="teacher_sessions")
    student = models.ForeignKey(User, on_delete=models.PROTECT, related_name="student_sessions")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT, related_name="sessions")
    title = models.CharField(max_length=200, blank=True)
    scheduled_at = models.DateTimeField(db_index=True)
    duration = models.PositiveIntegerField(default=60, help_text="بالدقائق")
    status = models.CharField(max_length=20, choices=STATUS, default="scheduled", db_index=True)
    is_trial = models.BooleanField(default=False)
    room_name = models.CharField(max_length=80, unique=True, default=_room)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    teacher_joined_at = models.DateTimeField(null=True, blank=True)
    student_joined_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cancel_reason = models.TextField(blank=True)
    counted = models.BooleanField(default=False, help_text="اتخصمت من رصيد الاشتراك")
    recording_url = models.URLField(blank=True)
    reminder_sent = models.BooleanField(default=False)

    class Meta:
        ordering = ["scheduled_at"]

    @property
    def ends_at(self):
        return self.scheduled_at + timezone.timedelta(minutes=self.duration)

    def __str__(self):
        return f"{self.subject} | {self.teacher} → {self.student} @ {self.scheduled_at:%Y-%m-%d %H:%M}"


class SessionReport(TimeStampedModel):
    """تقرير المدرس بعد الحصة — بيظهر للطالب (ما عدا private_notes)."""
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="report")
    attendance = models.CharField(max_length=10, choices=[("present", "حاضر"), ("late", "متأخر"), ("absent", "غائب")], default="present")
    topics = models.TextField(help_text="اللي اتشرح في الحصة")
    homework = models.TextField(blank=True)
    performance = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    behavior = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)], default=3)
    notes_for_student = models.TextField(blank=True, help_text="ملاحظات ونصايح للطالب")
    private_notes = models.TextField(blank=True, help_text="للمشرف والإدارة فقط")


class SessionEvaluation(TimeStampedModel):
    """تقييم المشرف لجودة الحصة."""
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="evaluation")
    supervisor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="+")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(10)])
    notes = models.TextField(blank=True)


class RescheduleRequest(TimeStampedModel):
    STATUS = [("pending", "قيد المراجعة"), ("approved", "مقبول"), ("rejected", "مرفوض")]
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name="reschedule_requests")
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    proposed_time = models.DateTimeField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    handled_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at"]


class TrialRequest(TimeStampedModel):
    """طلب حصة تجريبية مجانية."""
    STATUS = [("pending", "جديد"), ("scheduled", "تم التحديد"), ("done", "تمت"), ("cancelled", "ملغي")]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="trial_requests")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT)
    preferred_teacher = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    preferred_times = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS, default="pending")
    session = models.OneToOneField(Session, null=True, blank=True, on_delete=models.SET_NULL, related_name="trial_request")

    class Meta:
        ordering = ["-created_at"]


class Review(TimeStampedModel):
    """تقييم الطالب للمدرس (مرة لكل طالب/مدرس وبيتحدث)."""
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_received")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews_given")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        unique_together = [("teacher", "student")]
        ordering = ["-created_at"]


class SessionFeedback(TimeStampedModel):
    """تقييم الطالب للحصة نفسها (جودة الصوت والصورة والشرح) — بيوصل للمشرف لو التقييم ضعيف."""
    ISSUES = [("audio", "الصوت"), ("video", "الصورة"), ("connection", "النت/الاتصال"), ("late", "المدرس اتأخر"),
              ("unclear", "الشرح مش واضح"), ("short", "الحصة اتقصرت")]
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name="feedback")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    issues = models.JSONField(default=list, blank=True)
    comment = models.TextField(blank=True, max_length=1000)
