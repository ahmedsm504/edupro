"""Sitemap index مقسم لأقسام: /sitemap.xml ← sitemap-teachers.xml، sitemap-questions.xml ..."""
from django.contrib.sitemaps import Sitemap
from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.models import TeacherProfile
from apps.catalog.models import Subject
from apps.courses.models import Course
from apps.qa.models import Question

from .models import Article, BlogCategory, Page


class StaticSitemap(Sitemap):
    priority, changefreq = 1.0, "daily"

    def items(self):
        return ["/", "/subjects/", "/teachers/", "/courses/", "/blog/", "/questions/"]

    def location(self, item):
        return item


class SubjectSitemap(Sitemap):
    priority, changefreq = 0.9, "weekly"

    def items(self):
        return Subject.objects.filter(is_active=True).order_by("order", "id")

    def lastmod(self, o):
        return o.updated_at


class QuestionHubSitemap(Sitemap):
    """صفحة أسئلة لكل مادة (فيها أسئلة متجاوبة)."""
    priority, changefreq = 0.7, "daily"

    def items(self):
        return Subject.objects.filter(is_active=True).annotate(
            n=Count("questions", filter=Q(questions__moderation="approved", questions__answers_count__gt=0))).filter(n__gt=0).order_by("id")

    def location(self, o):
        return f"/questions/subject/{o.slug}/"


class TeacherSitemap(Sitemap):
    priority, changefreq = 0.8, "weekly"

    def items(self):
        return TeacherProfile.objects.filter(approval_status="approved", user__is_active=True).order_by("id")

    def lastmod(self, o):
        return o.updated_at


class CourseSitemap(Sitemap):
    priority, changefreq = 0.8, "weekly"

    def items(self):
        return Course.objects.filter(status="published").order_by("id")

    def lastmod(self, o):
        return o.updated_at


class ArticleSitemap(Sitemap):
    priority, changefreq = 0.8, "weekly"

    def items(self):
        return Article.objects.filter(status="published", noindex=False, published_at__lte=timezone.now())

    def lastmod(self, o):
        return o.updated_at


class BlogCategorySitemap(Sitemap):
    priority, changefreq = 0.6, "weekly"

    def items(self):
        return BlogCategory.objects.annotate(n=Count("articles", filter=Q(articles__status="published"))).filter(n__gt=0).order_by("order")


class QuestionSitemap(Sitemap):
    """الأسئلة المتجاوبة بس (اللي من غير إجابة noindex)."""
    priority, changefreq, limit = 0.7, "daily", 5000

    def items(self):
        return Question.objects.filter(moderation="approved", answers_count__gt=0).order_by("-last_activity_at")

    def lastmod(self, o):
        return o.last_activity_at


class PageSitemap(Sitemap):
    priority = 0.3

    def items(self):
        return Page.objects.filter(is_published=True).order_by("id")


sitemaps = {"static": StaticSitemap, "subjects": SubjectSitemap, "teachers": TeacherSitemap, "courses": CourseSitemap,
            "blog": ArticleSitemap, "blog-categories": BlogCategorySitemap, "questions": QuestionSitemap,
            "question-hubs": QuestionHubSitemap, "pages": PageSitemap}
