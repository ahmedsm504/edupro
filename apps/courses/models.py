from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.models import TimeStampedModel, unique_slug

from .video import VIDEO_EXTS, embed_url, parse_video_url, private_storage, thumbnail_url

User = settings.AUTH_USER_MODEL


class Course(TimeStampedModel):
    STATUS = [("draft", "مسودة"), ("pending_review", "قيد المراجعة"), ("published", "منشور"), ("rejected", "مرفوض")]
    LEVELS = [("beginner", "مبتدئ"), ("intermediate", "متوسط"), ("advanced", "متقدم"), ("all", "كل المستويات")]

    instructor = models.ForeignKey(User, on_delete=models.PROTECT, related_name="courses")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT, related_name="courses")
    grade = models.ForeignKey("catalog.Grade", null=True, blank=True, on_delete=models.SET_NULL, related_name="courses")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True, blank=True)
    short_description = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to="courses/thumbs/", blank=True, null=True)
    promo_video_url = models.URLField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default="EGP")
    level = models.CharField(max_length=20, choices=LEVELS, default="all")
    language = models.CharField(max_length=5, default="ar")
    what_you_learn = models.JSONField(default=list, blank=True, help_text='["نقطة 1", "نقطة 2"]')
    requirements = models.JSONField(default=list, blank=True)
    access_days = models.PositiveIntegerField(null=True, blank=True, help_text="فاضي = وصول مدى الحياة")
    status = models.CharField(max_length=20, choices=STATUS, default="draft", db_index=True)
    rejection_reason = models.TextField(blank=True)
    is_featured = models.BooleanField(default=False)
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    students_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    included_in_subscription = models.BooleanField(
        default=False, help_text="الكورس يتفتح ببلاش لأي طالب عنده اشتراك حصص لايف شغال مع نفس المدرس")
    certificate_enabled = models.BooleanField(default=True, help_text="الطالب ياخد شهادة إتمام لما يخلص الكورس")
    sequential = models.BooleanField(
        default=True, help_text="بالترتيب: الطالب لازم ينجح في كويز الدرس عشان يفتح اللي بعده، وفي امتحان الوحدة عشان يفتح الوحدة اللي بعدها")

    class Meta:
        ordering = ["-published_at", "-created_at"]

    @property
    def is_free(self):
        return self.price == 0

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.title)
        super().save(*a, **kw)

    def get_absolute_url(self):
        return f"/courses/{self.slug}/"

    def __str__(self):
        return self.title


class Section(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=200)
    order = models.PositiveIntegerField(default=0)
    exam = models.ForeignKey("assessments.Quiz", null=True, blank=True, on_delete=models.SET_NULL, related_name="unit_sections",
                             help_text="امتحان الوحدة — بيتفتح لما الطالب يخلّص كل دروس الوحدة")
    exam_required = models.BooleanField(default=True, help_text="لازم ينجح في امتحان الوحدة عشان الوحدة اللي بعدها تتفتح")

    class Meta:
        ordering = ["order", "id"]


def _video_ext(f):
    from django.core.exceptions import ValidationError
    if f and not f.name.lower().endswith(VIDEO_EXTS):
        raise ValidationError("صيغة الفيديو لازم تكون mp4 أو webm أو mov.")
    max_mb = settings.VIDEO_MAX_UPLOAD_MB
    if f and getattr(f, "size", 0) > max_mb * 1024 * 1024:
        raise ValidationError(f"الفيديو أكبر من {max_mb} ميجا.")


class Lesson(TimeStampedModel):
    TYPES = [("video", "فيديو"), ("pdf", "ملف PDF"), ("text", "نص"), ("quiz", "اختبار")]
    PROVIDERS = [("youtube", "YouTube"), ("vimeo", "Vimeo"), ("bunny", "Bunny Stream"), ("upload", "رفع مباشر"),
                 ("direct", "رابط ملف مباشر"), ("other", "رابط آخر")]
    ACCESS = [("free", "مجاني للكل"), ("members", "مجاني للمسجلين"), ("paid", "بعد الدفع")]

    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name="lessons")
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=10, choices=TYPES, default="video")
    video_provider = models.CharField(max_length=10, choices=PROVIDERS, blank=True)
    video_url = models.URLField(blank=True, help_text="رابط يوتيوب/فيميو/Bunny بأي شكل — بيتفهم تلقائي")
    video_id = models.CharField(max_length=120, blank=True, editable=False)
    video_file = models.FileField(upload_to="videos/%Y/%m/", storage=private_storage, blank=True, null=True,
                                  validators=[_video_ext], help_text="فيديو مرفوع مباشرة (محمي — مش بيتعرض برابط عام)")
    attachment = models.FileField(upload_to="attachments/%Y/%m/", storage=private_storage, blank=True, null=True,
                                  help_text="ملف مرفق (ملخص/تمارين) — محمي زي الفيديو")
    content = models.TextField(blank=True, help_text="نص الدرس أو ملاحظات تحت الفيديو")
    quiz = models.ForeignKey("assessments.Quiz", null=True, blank=True, on_delete=models.SET_NULL, related_name="lessons",
                             help_text="كويز بعد الدرس")
    quiz_required = models.BooleanField(default=True, help_text="الدرس ميتعلّمش إنه خلص غير لما الطالب ينجح في الكويز")
    duration_seconds = models.PositiveIntegerField(default=0)
    access = models.CharField(max_length=10, choices=ACCESS, default="paid", db_index=True,
                              help_text="مين يقدر يشوف الدرس: الكل / المسجلين / اللي دفع بس")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    @property
    def is_preview(self) -> bool:
        """توافق مع الإصدار القديم من الـ API: الدرس متاح من غير دفع."""
        return self.access != "paid"

    @property
    def embed_url(self) -> str:
        return embed_url(self.video_provider, self.video_id, self.video_url)

    @property
    def thumbnail(self) -> str:
        return thumbnail_url(self.video_provider, self.video_id)

    def save(self, *a, **kw):
        if self.video_file and not self.video_url:
            self.video_provider, self.video_id = "upload", ""
        elif self.video_url:
            self.video_provider, self.video_id = parse_video_url(self.video_url)
        else:
            self.video_provider, self.video_id = ("upload" if self.video_file else ""), ""
        super().save(*a, **kw)

    def __str__(self):
        return self.title


class Enrollment(TimeStampedModel):
    SOURCES = [("purchase", "شراء"), ("free", "مجاني"), ("admin", "إضافة من الإدارة"), ("subscription", "ضمن اشتراك الحصص")]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="enrollments")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    source = models.CharField(max_length=12, choices=SOURCES, default="purchase")
    expires_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.PositiveSmallIntegerField(default=0)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_lesson = models.ForeignKey(Lesson, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        unique_together = [("student", "course")]
        ordering = ["-created_at"]


class LessonProgress(TimeStampedModel):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="+")
    completed = models.BooleanField(default=False)
    position_seconds = models.PositiveIntegerField(default=0, help_text="آخر ثانية وصلها في الفيديو (للاستكمال)")

    class Meta:
        unique_together = [("enrollment", "lesson")]


class CourseReview(TimeStampedModel):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reviews")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="course_reviews")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        unique_together = [("course", "student")]
        ordering = ["-created_at"]


class LessonNote(TimeStampedModel):
    """ملاحظات الطالب الخاصة على الدرس — مربوطة بثانية في الفيديو عشان يرجعلها بضغطة."""
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="lesson_notes")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="notes")
    position_seconds = models.PositiveIntegerField(default=0)
    text = models.TextField(max_length=2000)

    class Meta:
        ordering = ["position_seconds", "id"]


def _cert_code():
    import secrets
    return "EP-" + secrets.token_hex(4).upper()


class Certificate(TimeStampedModel):
    """شهادة إتمام كورس — ليها صفحة عامة للتحقق /certificates/<code>/."""
    code = models.CharField(max_length=20, unique=True, default=_cert_code)
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="certificates")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="certificates")
    student_name = models.CharField(max_length=150)
    course_title = models.CharField(max_length=200)
    instructor_name = models.CharField(max_length=150)
    hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)

    class Meta:
        unique_together = [("student", "course")]
        ordering = ["-created_at"]

    def get_absolute_url(self):
        return f"/certificates/{self.code}/"
