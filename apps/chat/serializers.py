from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer

from .models import ContactViolation, Conversation, Message


class MessageSerializer(serializers.ModelSerializer):
    sender = UserMiniSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ["id", "conversation", "sender", "type", "text", "attachment", "duration_seconds", "reply_to",
                  "is_flagged", "is_deleted", "created_at"]

    def to_representation(self, inst):
        data = super().to_representation(inst)
        if inst.is_deleted:
            data["text"], data["attachment"] = "تم حذف الرسالة", None
        if self.context.get("for_staff"):
            data["original_text"] = inst.original_text
            data["flag_reasons"] = inst.flag_reasons
        return data


class ConversationSerializer(serializers.ModelSerializer):
    other_members = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ["id", "type", "other_members", "last_message", "unread_count", "last_message_at", "is_locked", "created_at"]

    def _user(self):
        return self.context["request"].user

    @extend_schema_field(UserMiniSerializer(many=True))
    def get_other_members(self, obj):
        users = [p.user for p in obj.members.select_related("user") if p.user_id != self._user().id]
        return UserMiniSerializer(users, many=True, context=self.context).data

    @extend_schema_field(MessageSerializer(allow_null=True))
    def get_last_message(self, obj):
        m = obj.messages.select_related("sender").first()
        return MessageSerializer(m, context=self.context).data if m else None

    def get_unread_count(self, obj) -> int:
        p = obj.members.filter(user=self._user()).first()
        qs = obj.messages.exclude(sender=self._user())
        if p and p.last_read_at:
            qs = qs.filter(created_at__gt=p.last_read_at)
        return qs.count() if p else 0


class StartConversationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()


class SendMessageSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=["text", "image", "file", "voice"], default="text")
    text = serializers.CharField(required=False, allow_blank=True, default="")
    attachment = serializers.FileField(required=False, allow_null=True)
    duration_seconds = serializers.IntegerField(required=False, allow_null=True)
    reply_to = serializers.IntegerField(required=False, allow_null=True)


class ContactViolationSerializer(serializers.ModelSerializer):
    user = UserMiniSerializer(read_only=True)
    message = MessageSerializer(read_only=True)
    original_text = serializers.CharField(source="message.original_text", read_only=True)

    class Meta:
        model = ContactViolation
        fields = ["id", "user", "message", "original_text", "reasons", "reviewed", "action_taken", "created_at"]
        read_only_fields = ["user", "message", "reasons"]
