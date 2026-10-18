from django.db import models

from apps.core.models import TimeStampedModel, unique_slug


class Curriculum(TimeStampedModel):
    """المنهج/النظام: مصري عام، أزهري، سعودي، IGCSE، أمريكي، عام (لغات/قرآن/مهارات)..."""
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True, allow_unicode=True, blank=True)
    country = models.CharField(max_length=60, blank=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "name"]

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.name)
        super().save(*a, **kw)

    def __str__(self):
        return self.name


class Stage(TimeStampedModel):
    """المرحلة: ابتدائي، إعدادي، ثانوي، جامعي، كبار..."""
    curriculum = models.ForeignKey(Curriculum, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["curriculum", "order"]

    def __str__(self):
        return f"{self.curriculum} - {self.name}"


class Grade(TimeStampedModel):
    """الصف: الصف الأول الثانوي..."""
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name="grades")
    name = models.CharField(max_length=120)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["stage", "order"]

    def __str__(self):
        return f"{self.stage} - {self.name}"


class Subject(TimeStampedModel):
    """المادة: رياضيات، فيزياء، قرآن كريم، إنجليزي، برمجة..."""
    name = models.CharField(max_length=120)
    name_en = models.CharField(max_length=120, blank=True)
    slug = models.SlugField(max_length=140, unique=True, allow_unicode=True, blank=True)
    icon = models.ImageField(upload_to="subjects/icons/", blank=True, null=True)
    color = models.CharField(max_length=9, blank=True, help_text="#RRGGBB للتطبيق")
    description = models.TextField(blank=True)
    grades = models.ManyToManyField(Grade, blank=True, related_name="subjects")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    # SEO
    meta_title = models.CharField(max_length=160, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["order", "name"]

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.name_en or self.name)
        super().save(*a, **kw)

    def get_absolute_url(self):
        return f"/subjects/{self.slug}/"

    def __str__(self):
        return self.name
