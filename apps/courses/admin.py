from django.contrib import admin

from .models import Course, CourseReview, Enrollment, Lesson, Section


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["title", "instructor", "subject", "price", "status", "students_count", "is_featured"]
    list_filter = ["status", "subject", "is_featured"]
    search_fields = ["title", "instructor__full_name"]
    inlines = [SectionInline]


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["title", "course", "order"]
    inlines = [LessonInline]


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["student", "course", "source", "progress_percent", "created_at"]
    raw_id_fields = ["student", "course"]


admin.site.register(CourseReview)
