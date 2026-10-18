from django.contrib import admin

from .models import Answer, Question, Vote


class AnswerInline(admin.StackedInline):
    model = Answer
    extra = 0
    raw_id_fields = ["author"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["title", "subject", "author", "answers_count", "score", "moderation", "created_at"]
    list_filter = ["moderation", "subject", "is_closed"]
    search_fields = ["title", "body"]
    raw_id_fields = ["author", "accepted_answer"]
    filter_horizontal = ["tags"]
    inlines = [AnswerInline]


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ["question", "author", "score", "moderation", "created_at"]
    list_filter = ["moderation"]
    raw_id_fields = ["author", "question"]


admin.site.register(Vote)
