from django.contrib import admin

from .models import (Package, RescheduleRequest, Review, Session, SessionEvaluation, SessionReport, Subscription,
                     TeacherAvailability, TrialRequest, WeeklySlot)


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    list_display = ["name", "subject", "sessions_count", "session_duration", "price", "is_active", "order"]
    list_editable = ["is_active", "order"]


class WeeklySlotInline(admin.TabularInline):
    model = WeeklySlot
    extra = 0


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ["id", "student", "teacher", "subject", "status", "sessions_used", "sessions_total", "end_date"]
    list_filter = ["status", "subject"]
    search_fields = ["student__full_name", "student__phone", "teacher__full_name"]
    inlines = [WeeklySlotInline]
    raw_id_fields = ["student", "teacher", "preferred_teacher"]


class ReportInline(admin.StackedInline):
    model = SessionReport
    extra = 0


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ["id", "subject", "teacher", "student", "scheduled_at", "status", "counted"]
    list_filter = ["status", "is_trial", "subject"]
    search_fields = ["teacher__full_name", "student__full_name"]
    date_hierarchy = "scheduled_at"
    raw_id_fields = ["teacher", "student", "subscription"]
    inlines = [ReportInline]


admin.site.register(TeacherAvailability)
admin.site.register(SessionEvaluation)
admin.site.register(RescheduleRequest)
admin.site.register(TrialRequest)
admin.site.register(Review)
