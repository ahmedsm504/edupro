from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Notification(TimeStampedModel):
    """
    type أمثلة: session_reminder, session_started, session_cancelled, session_report, new_message,
    subscription_activated, payment_success, homework_assigned, quiz_graded, teacher_status, contact_violation ...
    data: payload للتطبيق عشان يفتح الشاشة الصح (مثلاً {"screen": "session", "id": 15})
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    type = models.CharField(max_length=50, db_index=True)
    title = models.CharField(max_length=200)
    body = models.TextField(blank=True)
    data = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class Device(TimeStampedModel):
    """توكن FCM لكل جهاز (موبايل/ويب)."""
    PLATFORMS = [("android", "Android"), ("ios", "iOS"), ("web", "Web")]
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORMS)
    app_version = models.CharField(max_length=20, blank=True)
