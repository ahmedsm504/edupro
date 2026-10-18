from django.contrib import admin

from .models import Answer, Attempt, Choice, Question, Quiz, QuizAssignment


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 0


class QuestionInline(admin.StackedInline):
    model = Question
    extra = 0


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ["title", "kind", "owner", "subject", "is_published", "is_public"]
    list_filter = ["kind", "is_published", "subject"]
    inlines = [QuestionInline]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["text", "quiz", "type", "points"]
    inlines = [ChoiceInline]


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):
    list_display = ["quiz", "student", "status", "score", "max_score", "submitted_at"]
    list_filter = ["status"]


admin.site.register(QuizAssignment)
admin.site.register(Answer)
