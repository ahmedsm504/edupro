from django.contrib import admin

from .models import Curriculum, Grade, Stage, Subject


class GradeInline(admin.TabularInline):
    model = Grade
    extra = 0


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0


@admin.register(Curriculum)
class CurriculumAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "order", "is_active"]
    inlines = [StageInline]


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ["name", "curriculum", "order"]
    inlines = [GradeInline]


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "is_active", "is_featured", "order"]
    list_editable = ["is_active", "is_featured", "order"]
    filter_horizontal = ["grades"]
    search_fields = ["name", "name_en"]


admin.site.register(Grade)
