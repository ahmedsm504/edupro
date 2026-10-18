from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, unique_slug


class BlogCategory(TimeStampedModel):
    """تصنيف المدونة (صفحة مستقلة لكل تصنيف = Hub page للسيو)."""
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, allow_unicode=True, blank=True)
    description = models.TextField(blank=True, help_text="بتظهر أعلى صفحة التصنيف وفي الـ meta description")
    subject = models.ForeignKey("catalog.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="blog_categories")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name_plural = "Blog categories"

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*a, **kw)

    def get_absolute_url(self):
        return f"/blog/category/{self.slug}/"

    def __str__(self):
        return self.name


class Tag(TimeStampedModel):
    """وسوم مشتركة بين المقالات والأسئلة."""
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, allow_unicode=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*a, **kw)

    def get_absolute_url(self):
        return f"/blog/tag/{self.slug}/"

    def __str__(self):
        return self.name


class Article(TimeStampedModel):
    """مقال في المدونة. المدرسين بيكتبوا ويبعتوا للمراجعة، والإدارة بتنشر."""
    STATUS = [("draft", "مسودة"), ("pending_review", "قيد المراجعة"), ("published", "منشور"), ("rejected", "مرفوض")]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True, blank=True)
    category = models.ForeignKey(BlogCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="articles")
    subject = models.ForeignKey("catalog.Subject", null=True, blank=True, on_delete=models.SET_NULL, related_name="articles")
    tags = models.ManyToManyField(Tag, blank=True, related_name="articles")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="articles")
    excerpt = models.CharField(max_length=300, blank=True, help_text="ملخص بيظهر في القوائم (لو فاضي بيتاخد من أول المقال)")
    body = models.TextField(help_text="HTML — العناوين h2/h3 بتعمل فهرس تلقائي")
    cover = models.ImageField(upload_to="blog/", blank=True, null=True)
    cover_alt = models.CharField(max_length=200, blank=True)
    faq = models.JSONField(default=list, blank=True, help_text='أسئلة شائعة في آخر المقال: [{"q": "...", "a": "..."}] — بتطلع في جوجل')
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    focus_keyword = models.CharField(max_length=120, blank=True, help_text="الكلمة المفتاحية الأساسية (للمراجعة الداخلية)")
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)
    rejection_reason = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    noindex = models.BooleanField(default=False, help_text="متتعرضش في جوجل")
    views_count = models.PositiveIntegerField(default=0)
    reading_minutes = models.PositiveSmallIntegerField(default=1)
    word_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_at", "-created_at"]

    @property
    def is_published(self):
        return self.status == "published"

    def save(self, *a, **kw):
        from apps.core.richtext import excerpt, reading_minutes, sanitize_html, word_count
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        self.body = sanitize_html(self.body)
        self.word_count = word_count(self.body)
        self.reading_minutes = reading_minutes(self.body)
        if not self.excerpt:
            self.excerpt = excerpt(self.body, 280)
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*a, **kw)

    def get_absolute_url(self):
        return f"/blog/{self.slug}/"

    def __str__(self):
        return self.title


class Page(TimeStampedModel):
    """صفحات ثابتة: من نحن، الشروط، الخصوصية..."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=120, unique=True, allow_unicode=True)
    body = models.TextField()
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=True)

    def get_absolute_url(self):
        return f"/p/{self.slug}/"


class FAQ(TimeStampedModel):
    question = models.CharField(max_length=300)
    answer = models.TextField()
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order"]


class Testimonial(TimeStampedModel):
    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120, blank=True, help_text="طالب ثانوي / خريج...")
    text = models.TextField()
    rating = models.PositiveSmallIntegerField(default=5)
    is_active = models.BooleanField(default=True)
