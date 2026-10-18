from django.contrib import admin

from .models import FAQ, Article, BlogCategory, Page, Tag, Testimonial


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "author", "status", "is_featured", "views_count", "published_at"]
    list_filter = ["status", "category", "subject", "is_featured"]
    list_editable = ["status", "is_featured"]
    search_fields = ["title", "body"]
    filter_horizontal = ["tags"]
    raw_id_fields = ["author"]
    readonly_fields = ["reading_minutes", "word_count", "views_count"]
    fieldsets = (
        (None, {"fields": ("title", "slug", "status", "rejection_reason", "author", "category", "subject", "tags", "is_featured")}),
        ("المحتوى", {"fields": ("excerpt", "body", "cover", "cover_alt", "faq")}),
        ("السيو", {"fields": ("meta_title", "meta_description", "focus_keyword", "noindex", "published_at")}),
        ("إحصائيات", {"fields": ("reading_minutes", "word_count", "views_count")}),
    )


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "subject", "order"]
    list_editable = ["order"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    search_fields = ["name"]


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published"]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "order", "is_active"]
    list_editable = ["order", "is_active"]


admin.site.register(Testimonial)
