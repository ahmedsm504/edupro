"""منطق العمل الخاص بالحصص والاشتراكات — كل التغييرات المهمة بتعدي من هنا."""
import datetime as dt
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db import transaction
from django.db.models import Avg, Count, F
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.core.permissions import Roles
from apps.notifications.services import notify, notify_staff, ws_send

from .jitsi import build_join_payload
from .models import Review, Session, Subscription

CANCEL_FREE_HOURS = 2       # الطالب يلغي قبلها بساعتين وإلا الحصة تتحسب
ABSENT_AFTER_MINUTES = 15   # المدرس يقدر يسجل غياب الطالب بعد ربع ساعة


# ------------------------------------------------------------------ visibility
def sessions_visible_to(user):
    qs = Session.objects.select_related("teacher", "student", "subject", "subscription")
    if user.role == Roles.ADMIN or user.is_superuser:
        return qs
    if user.role == Roles.SUPERVISOR:
        return qs.filter(teacher__teacher_profile__supervisor=user)
    if user.role == Roles.TEACHER:
        return qs.filter(teacher=user)
    if user.role == Roles.STUDENT:
        return qs.filter(student=user)
    return qs.none()


def subscriptions_visible_to(user):
    qs = Subscription.objects.select_related("student", "teacher", "subject", "package").prefetch_related("slots")
    if user.role == Roles.ADMIN or user.is_superuser:
        return qs
    if user.role == Roles.SUPERVISOR:
        return qs.filter(teacher__teacher_profile__supervisor=user) | qs.filter(status__in=["pending_assignment", "pending_payment"])
    if user.role == Roles.TEACHER:
        return qs.filter(teacher=user)
    if user.role == Roles.STUDENT:
        return qs.filter(student=user)
    return qs.none()


def can_manage(user, session):
    return user.role == Roles.ADMIN or user.is_superuser or (
        user.role == Roles.SUPERVISOR and getattr(session.teacher.teacher_profile, "supervisor_id", None) == user.id
    )


# ------------------------------------------------------------------ subscriptions
@transaction.atomic
def mark_subscription_paid(sub: Subscription, amount=None):
    """بعد نجاح الدفع: لو فيه مدرس ومواعيد → نشط وتتولد الحصص، غير كده → في انتظار التعيين."""
    sub.price_paid = amount if amount is not None else sub.package.price
    sub.sessions_total = sub.package.sessions_count
    sub.session_duration = sub.package.session_duration
    if sub.teacher_id and sub.slots.exists():
        activate_subscription(sub)
    else:
        sub.status = "pending_assignment"
        sub.save()
        notify_staff("subscription_needs_assignment", "اشتراك جديد محتاج تعيين مدرس",
                     f"{sub.student.full_name} - {sub.subject}", {"screen": "subscription", "id": sub.id})
    notify(sub.student, "subscription_paid", "تم استلام الدفع ✅",
           "اشتراكك اتسجل وهنحدد لك المدرس والمواعيد قريباً." if sub.status != "active" else "اشتراكك نشط دلوقتي.",
           {"screen": "subscription", "id": sub.id})
    return sub


@transaction.atomic
def activate_subscription(sub: Subscription, start_date=None):
    if not sub.teacher_id:
        raise BusinessError("لازم تحدد المدرس الأول.", code="teacher_required")
    if not sub.slots.exists():
        raise BusinessError("لازم تحدد مواعيد الحصص الأسبوعية.", code="slots_required")
    sub.status = "active"
    sub.sessions_total = sub.sessions_total or sub.package.sessions_count
    sub.session_duration = sub.session_duration or sub.package.session_duration
    sub.start_date = start_date or sub.start_date or timezone.localdate()
    sub.end_date = sub.start_date + dt.timedelta(days=sub.package.duration_days)
    sub.save()
    created = generate_sessions(sub)
    notify(sub.student, "subscription_activated", "اشتراكك اتفعل 🎉",
           f"مع أ/ {sub.teacher.full_name} — {created} حصة في جدولك.", {"screen": "subscription", "id": sub.id})
    notify(sub.teacher, "new_student", "طالب جديد", f"{sub.student.full_name} - {sub.subject}",
           {"screen": "subscription", "id": sub.id})
    return created


def generate_sessions(sub: Subscription):
    """يولّد الحصص من الجدول الأسبوعي لحد ما يخلص عدد الحصص أو تاريخ الانتهاء. آمن للتكرار."""
    tz = ZoneInfo(sub.teacher.timezone or settings.TIME_ZONE)
    existing = sub.sessions.exclude(status="cancelled").count()
    needed = sub.sessions_total - existing
    if needed <= 0:
        return 0
    slots = list(sub.slots.all())
    day = max(sub.start_date, timezone.localdate())
    now = timezone.now()
    created = 0
    taken = set(sub.sessions.values_list("scheduled_at", flat=True))
    while created < needed and day <= sub.end_date:
        for slot in slots:
            if slot.weekday != day.weekday() or created >= needed:
                continue
            at = dt.datetime.combine(day, slot.start_time, tzinfo=tz)
            if at <= now or at in taken:
                continue
            Session.objects.create(subscription=sub, teacher=sub.teacher, student=sub.student, subject=sub.subject,
                                   scheduled_at=at, duration=sub.session_duration)
            created += 1
        day += dt.timedelta(days=1)
    return created


def _consume(session: Session):
    if session.counted or not session.subscription_id:
        return
    session.counted = True
    Subscription.objects.filter(pk=session.subscription_id).update(sessions_used=F("sessions_used") + 1)
    sub = Subscription.objects.get(pk=session.subscription_id)
    if sub.sessions_used >= sub.sessions_total and sub.status == "active":
        sub.status = "expired"
        sub.save(update_fields=["status"])
        notify(sub.student, "subscription_finished", "خلصت حصص الباقة",
               "جدد اشتراكك عشان تكمل مع مدرسك.", {"screen": "subscription", "id": sub.id})
    elif sub.sessions_remaining == 1:
        notify(sub.student, "subscription_low", "فاضل حصة واحدة في باقتك", "جدد بدري عشان مواعيدك تفضل محجوزة.",
               {"screen": "subscription", "id": sub.id})


# ------------------------------------------------------------------ session lifecycle
def _broadcast(session, event):
    data = {"session_id": session.id, "status": session.status}
    for uid in (session.teacher_id, session.student_id):
        ws_send(uid, event, data)


def join_session(session: Session, user):
    now = timezone.now()
    is_teacher = user.id == session.teacher_id
    is_student = user.id == session.student_id
    staff = can_manage(user, session)
    if not (is_teacher or is_student or staff):
        raise BusinessError("مش مسموح لك تدخل الحصة دي.", code="not_participant", status_code=403)
    if session.status in ("cancelled", "completed", "student_absent", "teacher_absent"):
        raise BusinessError("الحصة دي انتهت أو اتلغت.", code="session_closed")
    early = dt.timedelta(minutes=settings.SESSION_JOIN_EARLY_MINUTES)
    if not staff and now < session.scheduled_at - early:
        raise BusinessError(f"تقدر تدخل قبل الميعاد بـ {settings.SESSION_JOIN_EARLY_MINUTES} دقايق بس.",
                            code="session_not_started")
    if not staff and now > session.ends_at + dt.timedelta(minutes=30):
        raise BusinessError("وقت الحصة خلص.", code="session_expired")

    fields = []
    if is_teacher and not session.teacher_joined_at:
        session.teacher_joined_at = now
        fields.append("teacher_joined_at")
    if is_student and not session.student_joined_at:
        session.student_joined_at = now
        fields.append("student_joined_at")
    if is_teacher and session.status == "scheduled":
        session.status = "live"
        session.started_at = now
        fields += ["status", "started_at"]
    if fields:
        session.save(update_fields=fields)
    if is_teacher and "status" in fields:
        notify(session.student, "session_started", "الحصة بدأت 🔴", f"أ/ {session.teacher.full_name} في انتظارك",
               {"screen": "session", "id": session.id})
        _broadcast(session, "session.updated")
    if is_teacher or is_student:
        # الطرف التاني يعرف لحظياً إن صاحبه دخل الغرفة (شاشة الانتظار بتتحدث)
        other = session.student_id if is_teacher else session.teacher_id
        ws_send(other, "session.presence", {"session_id": session.id, "who": "teacher" if is_teacher else "student",
                                            "name": user.full_name, "status": session.status})
    return build_join_payload(session, user, is_moderator=is_teacher or staff)


def end_session(session: Session, user):
    if not (user.id == session.teacher_id or can_manage(user, session)):
        raise BusinessError("المدرس بس اللي ينهي الحصة.", code="forbidden", status_code=403)
    if session.status not in ("live", "scheduled"):
        raise BusinessError("الحصة مش جارية.", code="invalid_status")
    if not session.teacher_joined_at and not can_manage(user, session):
        raise BusinessError("لازم تدخل الحصة الأول.", code="not_joined")
    session.status = "completed"
    session.ended_at = timezone.now()
    session.started_at = session.started_at or session.ended_at
    _consume(session)
    session.save()
    notify(session.student, "session_completed", "الحصة خلصت", "قيّم مدرسك وشوف تقرير الحصة لما يتكتب.",
           {"screen": "session", "id": session.id})
    _broadcast(session, "session.updated")
    return session


def cancel_session(session: Session, user, reason=""):
    if session.status not in ("scheduled",):
        raise BusinessError("مينفعش تلغي الحصة دي.", code="invalid_status")
    staff = can_manage(user, session)
    if user.id not in (session.teacher_id, session.student_id) and not staff:
        raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
    session.status = "cancelled"
    session.cancelled_by = user
    session.cancel_reason = reason
    late = session.scheduled_at - timezone.now() < dt.timedelta(hours=CANCEL_FREE_HOURS)
    if user.id == session.student_id and late:
        _consume(session)  # إلغاء متأخر من الطالب = الحصة بتتحسب
    session.save()
    other = session.teacher if user.id == session.student_id else session.student
    notify(other, "session_cancelled", "تم إلغاء حصة", f"{session.scheduled_at:%Y-%m-%d %H:%M} — {reason}",
           {"screen": "session", "id": session.id})
    if user.id == session.teacher_id:
        notify_staff("teacher_cancelled", "مدرس ألغى حصة", f"{session.teacher.full_name}: {reason}",
                     {"screen": "session", "id": session.id}, supervisor=session.teacher.teacher_profile.supervisor)
    # نعوّض الحصة الملغاة (لو مش محسوبة) بحصة في آخر الجدول
    if session.subscription_id and not session.counted and session.subscription.status == "active":
        generate_sessions(session.subscription)
    _broadcast(session, "session.updated")
    return session


def mark_absent(session: Session, user, who: str):
    now = timezone.now()
    if session.status not in ("scheduled", "live"):
        raise BusinessError("الحالة الحالية لا تسمح.", code="invalid_status")
    if who == "student":
        if user.id != session.teacher_id and not can_manage(user, session):
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        if now < session.scheduled_at + dt.timedelta(minutes=ABSENT_AFTER_MINUTES) and not can_manage(user, session):
            raise BusinessError(f"استنى {ABSENT_AFTER_MINUTES} دقيقة من بداية الحصة.", code="too_early")
        session.status = "student_absent"
        _consume(session)
        notify(session.student, "student_absent", "تم تسجيل غيابك", str(session.subject), {"screen": "session", "id": session.id})
    elif who == "teacher":
        if not can_manage(user, session) and user.id != session.student_id:
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        if user.id == session.student_id and now < session.scheduled_at + dt.timedelta(minutes=ABSENT_AFTER_MINUTES):
            raise BusinessError(f"استنى {ABSENT_AFTER_MINUTES} دقيقة من بداية الحصة.", code="too_early")
        session.status = "teacher_absent"
        notify_staff("teacher_absent", "غياب مدرس", f"{session.teacher.full_name} - حصة #{session.id}",
                     {"screen": "session", "id": session.id}, supervisor=session.teacher.teacher_profile.supervisor)
        if session.subscription_id and session.subscription.status == "active":
            session.save()
            generate_sessions(session.subscription)
    else:
        raise BusinessError("who لازم student أو teacher", code="validation_error")
    session.ended_at = now
    session.save()
    _broadcast(session, "session.updated")
    return session


def reschedule(session: Session, new_time):
    if session.status != "scheduled":
        raise BusinessError("مينفعش تغيّر ميعاد الحصة دي.", code="invalid_status")
    if new_time <= timezone.now():
        raise BusinessError("الميعاد الجديد لازم يكون في المستقبل.", code="invalid_time")
    session.scheduled_at = new_time
    session.reminder_sent = False
    session.save(update_fields=["scheduled_at", "reminder_sent", "updated_at"])
    for u in (session.teacher, session.student):
        notify(u, "session_rescheduled", "تم تغيير ميعاد حصة", f"الميعاد الجديد: {timezone.localtime(new_time):%Y-%m-%d %H:%M}",
               {"screen": "session", "id": session.id})
    return session


def check_conflict(teacher, start, duration, exclude_id=None):
    end = start + dt.timedelta(minutes=duration)
    qs = Session.objects.filter(teacher=teacher, status__in=["scheduled", "live"],
                                scheduled_at__lt=end, scheduled_at__gte=start - dt.timedelta(hours=4))
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    for s in qs:
        if s.ends_at > start:
            return s
    return None


def refresh_teacher_rating(teacher):
    agg = Review.objects.filter(teacher=teacher, is_visible=True).aggregate(a=Avg("rating"), c=Count("id"))
    tp = teacher.teacher_profile
    tp.rating_avg = round(agg["a"] or 0, 2)
    tp.rating_count = agg["c"]
    tp.save(update_fields=["rating_avg", "rating_count"])
