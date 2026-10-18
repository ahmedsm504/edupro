import logging
import threading

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.core.permissions import Roles

from .models import Device, Notification

logger = logging.getLogger(__name__)


def user_group(user_id):
    return f"user_{user_id}"


def ws_send(user_id, event: str, payload: dict):
    """إرسال حدث لحظي لكل اتصالات WebSocket بتاعة المستخدم."""
    layer = get_channel_layer()
    if not layer:
        return
    try:
        async_to_sync(layer.group_send)(user_group(user_id), {"type": "push.event", "event": event, "data": payload})
    except Exception as e:  # لا نوقف الطلب بسبب الـ realtime
        logger.warning("ws_send failed: %s", e)


def _push_async(user_ids, title, body, data):
    from .fcm import send_push
    tokens = list(Device.objects.filter(user_id__in=user_ids).values_list("token", flat=True))
    invalid = send_push(tokens, title, body, data)
    if invalid:
        Device.objects.filter(token__in=invalid).delete()


def notify(user, type, title, body="", data=None, push=True):
    data = data or {}
    n = Notification.objects.create(user=user, type=type, title=title, body=body, data=data)
    payload = {"id": n.id, "type": type, "title": title, "body": body, "data": data,
               "is_read": False, "created_at": n.created_at.isoformat()}

    def _after():
        ws_send(user.id, "notification.new", payload)
        if push:
            threading.Thread(target=_push_async, args=([user.id], title, body, {**data, "type": type}), daemon=True).start()

    transaction.on_commit(_after)
    return n


def notify_many(users, type, title, body="", data=None):
    for u in users:
        notify(u, type, title, body, data)


def notify_staff(type, title, body="", data=None, admins_only=False, supervisor=None):
    from apps.accounts.models import User
    roles = [Roles.ADMIN] if admins_only else list(Roles.STAFF)
    users = list(User.objects.filter(role__in=roles, is_active=True))
    if supervisor and supervisor not in users:
        users.append(supervisor)
    notify_many(users, type, title, body, data)
