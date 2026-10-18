from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

from apps.core.contact_filter import scan
from apps.core.exceptions import BusinessError
from apps.core.permissions import Roles
from apps.notifications.services import notify, notify_staff, ws_send

from .models import ContactViolation, Conversation, Message, Participant


def allowed_contacts(user):
    """IDs اللي المستخدم مسموح يكلمهم. الإدارة: الكل."""
    from apps.accounts.models import User
    from apps.tutoring.models import Session, Subscription
    if user.role in Roles.STAFF or user.is_superuser:
        return None  # الكل
    staff = set(User.objects.filter(role__in=Roles.STAFF, is_active=True).values_list("id", flat=True))
    ids = set()
    live = ["active", "paused", "pending_assignment"]
    if user.role == Roles.STUDENT:
        ids |= set(Subscription.objects.filter(student=user, status__in=live, teacher__isnull=False).values_list("teacher_id", flat=True))
        ids |= set(Session.objects.filter(student=user, is_trial=True).values_list("teacher_id", flat=True))
    elif user.role == Roles.TEACHER:
        students = set(Subscription.objects.filter(teacher=user, status__in=live).values_list("student_id", flat=True))
        students |= set(Session.objects.filter(teacher=user, is_trial=True).values_list("student_id", flat=True))
        ids |= students
    return ids | staff


def can_chat(user, other):
    allowed = allowed_contacts(user)
    return allowed is None or other.id in allowed


def get_or_create_direct(user, other):
    if user.id == other.id:
        raise BusinessError("مينفعش تكلم نفسك 🙂", code="invalid_target")
    if not can_chat(user, other):
        raise BusinessError("مسموح تكلم مدرسينك/طلابك والإدارة بس.", code="chat_not_allowed", status_code=403)
    conv = (Conversation.objects.filter(type="direct", members__user=user).filter(members__user=other)
            .annotate(n=Count("members")).filter(n=2).first())
    if conv:
        return conv, False
    with transaction.atomic():
        conv = Conversation.objects.create(type="direct")
        Participant.objects.bulk_create([Participant(conversation=conv, user=user), Participant(conversation=conv, user=other)])
    return conv, True


def get_support_conversation(user):
    from apps.accounts.models import User
    conv = Conversation.objects.filter(type="support", members__user=user).first()
    if conv:
        return conv
    conv = Conversation.objects.create(type="support")
    Participant.objects.create(conversation=conv, user=user)
    for admin in User.objects.filter(role=Roles.ADMIN, is_active=True):
        Participant.objects.get_or_create(conversation=conv, user=admin)
    return conv


def conversations_for(user, oversight=False):
    if oversight and (user.role in Roles.STAFF or user.is_superuser):
        qs = Conversation.objects.all()
        if user.role == Roles.SUPERVISOR:
            qs = qs.filter(members__user__teacher_profile__supervisor=user)
        return qs.distinct()
    return Conversation.objects.filter(members__user=user)


def is_member(user, conv):
    return conv.members.filter(user=user).exists()


def can_view(user, conv):
    if is_member(user, conv):
        return True
    if user.role == Roles.ADMIN or user.is_superuser:
        return True
    if user.role == Roles.SUPERVISOR:
        return conv.members.filter(user__teacher_profile__supervisor=user).exists()
    return False


def serialize_message(m, for_staff=False, request=None):
    from .serializers import MessageSerializer
    return MessageSerializer(m, context={"for_staff": for_staff, "request": request}).data


def send_message(user, conv, text="", type="text", attachment=None, duration=None, reply_to=None, request=None):
    if conv.is_locked:
        raise BusinessError("المحادثة مقفولة من الإدارة.", code="conversation_locked", status_code=403)
    if not is_member(user, conv):
        if user.role in Roles.STAFF:
            Participant.objects.get_or_create(conversation=conv, user=user)
        else:
            raise BusinessError("مش عضو في المحادثة.", code="forbidden", status_code=403)
    if not text and not attachment:
        raise BusinessError("الرسالة فاضية.", code="empty_message")

    clean, reasons = (text, [])
    if user.role not in Roles.STAFF and text:
        clean, reasons = scan(text)
    msg = Message.objects.create(
        conversation=conv, sender=user, type=type, text=clean, original_text=text if reasons else "",
        attachment=attachment, duration_seconds=duration, reply_to=reply_to,
        is_flagged=bool(reasons), flag_reasons=reasons,
    )
    now = timezone.now()
    conv.last_message_at = now
    conv.save(update_fields=["last_message_at"])
    Participant.objects.filter(conversation=conv, user=user).update(last_read_at=now)

    if reasons:
        ContactViolation.objects.create(message=msg, user=user, reasons=reasons)
        sup = getattr(getattr(user, "teacher_profile", None), "supervisor", None)
        notify_staff("contact_violation", "⚠️ محاولة تواصل خارج المنصة", f"{user.full_name}: {', '.join(reasons)}",
                     {"screen": "violation", "message_id": msg.id}, supervisor=sup)

    payload = serialize_message(msg, request=request)
    staff_payload = serialize_message(msg, for_staff=True, request=request)
    for p in conv.members.select_related("user"):
        is_staff = p.user.role in Roles.STAFF
        ws_send(p.user_id, "message.new", {"conversation_id": conv.id, "message": staff_payload if is_staff else payload})
        if p.user_id != user.id and not p.muted:
            preview = clean if type == "text" else {"image": "📷 صورة", "file": "📎 ملف", "voice": "🎤 رسالة صوتية"}.get(type, "")
            notify(p.user, "new_message", user.full_name, preview[:120],
                   {"screen": "chat", "conversation_id": conv.id}, push=True)
    return msg


def mark_read(user, conv):
    now = timezone.now()
    Participant.objects.filter(conversation=conv, user=user).update(last_read_at=now)
    for p in conv.members.exclude(user=user):
        ws_send(p.user_id, "message.read", {"conversation_id": conv.id, "user_id": user.id, "read_at": now.isoformat()})
    # نعلّم إشعارات الشات دي كمقروءة
    from apps.notifications.models import Notification
    Notification.objects.filter(user=user, type="new_message", is_read=False, data__conversation_id=conv.id).update(is_read=True)


def typing(user, conv, is_typing=True):
    for p in conv.members.exclude(user=user):
        ws_send(p.user_id, "typing", {"conversation_id": conv.id, "user_id": user.id, "is_typing": is_typing})
