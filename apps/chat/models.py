from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

User = settings.AUTH_USER_MODEL


class Conversation(TimeStampedModel):
    """
    محادثة بين طرفين (مدرس↔طالب، مدرس↔ولي أمر، أي حد↔الدعم).
    كل المحادثات مرئية للإدارة والمشرف المسؤول — عشان التواصل يفضل جوه المنصة.
    """
    TYPES = [("direct", "مباشرة"), ("support", "الدعم الفني")]
    type = models.CharField(max_length=10, choices=TYPES, default="direct")
    participants = models.ManyToManyField(User, through="Participant", related_name="conversations")
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)
    is_locked = models.BooleanField(default=False, help_text="الإدارة تقفل المحادثة")

    class Meta:
        ordering = ["-last_message_at", "-created_at"]


class Participant(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="chat_memberships")
    last_read_at = models.DateTimeField(null=True, blank=True)
    muted = models.BooleanField(default=False)

    class Meta:
        unique_together = [("conversation", "user")]


class Message(TimeStampedModel):
    TYPES = [("text", "نص"), ("image", "صورة"), ("file", "ملف"), ("voice", "رسالة صوتية"), ("system", "نظام")]
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, null=True, on_delete=models.SET_NULL, related_name="sent_messages")
    type = models.CharField(max_length=10, choices=TYPES, default="text")
    text = models.TextField(blank=True)
    original_text = models.TextField(blank=True, help_text="النص الأصلي قبل الفلترة (للإدارة فقط)")
    attachment = models.FileField(upload_to="chat/%Y/%m/", blank=True, null=True)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True, help_text="للرسائل الصوتية")
    reply_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL)
    is_flagged = models.BooleanField(default=False, db_index=True)
    flag_reasons = models.JSONField(default=list, blank=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]


class ContactViolation(TimeStampedModel):
    """سجل محاولات التواصل خارج المنصة."""
    message = models.OneToOneField(Message, on_delete=models.CASCADE, related_name="violation")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="contact_violations")
    reasons = models.JSONField(default=list)
    reviewed = models.BooleanField(default=False)
    action_taken = models.CharField(max_length=200, blank=True)
