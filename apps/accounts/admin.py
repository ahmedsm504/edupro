from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StudentProfile, TeacherDocument, TeacherProfile, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["-date_joined"]
    list_display = ["full_name", "phone", "email", "role", "is_active", "date_joined"]
    list_filter = ["role", "is_active", "is_phone_verified"]
    search_fields = ["full_name", "phone", "email"]
    fieldsets = (
        (None, {"fields": ("phone", "password")}),
        ("البيانات", {"fields": ("full_name", "email", "role", "avatar", "gender", "country", "timezone", "language", "is_phone_verified")}),
        ("الصلاحيات", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("phone", "full_name", "role", "password1", "password2")}),)


class TeacherDocumentInline(admin.TabularInline):
    model = TeacherDocument
    extra = 0


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "approval_status", "supervisor", "rating_avg", "is_featured"]
    list_filter = ["approval_status", "is_featured", "subjects"]
    search_fields = ["user__full_name", "user__phone"]
    filter_horizontal = ["subjects", "grades"]
    inlines = [TeacherDocumentInline]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "grade", "school"]
    search_fields = ["user__full_name", "user__phone"]

