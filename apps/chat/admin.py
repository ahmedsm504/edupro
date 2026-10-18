from django.contrib import admin

from .models import ContactViolation, Conversation, Message, Participant


class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0
    raw_id_fields = ["user"]


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "last_message_at", "is_locked"]
    inlines = [ParticipantInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ["id", "conversation", "sender", "type", "text", "is_flagged", "created_at"]
    list_filter = ["is_flagged", "type"]
    search_fields = ["text", "original_text", "sender__full_name"]


@admin.register(ContactViolation)
class ContactViolationAdmin(admin.ModelAdmin):
    list_display = ["user", "reasons", "reviewed", "created_at"]
    list_filter = ["reviewed"]
