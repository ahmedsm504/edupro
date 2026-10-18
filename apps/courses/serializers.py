from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.serializers import UserMiniSerializer
from apps.catalog.serializers import SubjectMiniSerializer

from .models import _video_ext  # noqa: E402
from .models import Certificate, Course, CourseReview, Enrollment, Lesson, LessonNote, LessonProgress, Section


class LessonOutlineSerializer(serializers.ModelSerializer):
    """في صفحة الكورس: من غير المحتوى نفسه. locked + lock_reason (login | payment)."""
    locked = serializers.SerializerMethodField()
    lock_reason = serializers.SerializerMethodField()
    completed = serializers.SerializerMethodField()
    is_preview = serializers.BooleanField(read_only=True)
    has_attachment = serializers.SerializerMethodField()

    quiz = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ["id", "title", "type", "duration_seconds", "access", "is_preview", "order", "locked", "lock_reason",
                  "completed", "has_attachment", "thumbnail", "quiz"]

    def _lock(self, obj):
        """login | payment | sequence (لازم ينجح في كويز اللي قبله) | None"""
        access = self.context.get("access") or {"full": False}
        user = self.context["request"].user if self.context.get("request") else None
        from .services import lesson_lock
        from django.contrib.auth.models import AnonymousUser
        r = lesson_lock(user or AnonymousUser(), obj, access)
        if r:
            return r
        p = (self.context.get("path") or {}).get("lessons", {}).get(obj.id) or {}
        return "sequence" if p.get("seq_locked") else None

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_quiz(self, obj):
        """كويز بعد الدرس: {id, title, questions_count, pass_percent, passed, best_percent, attempts, required, locked} أو null"""
        return ((self.context.get("path") or {}).get("lessons", {}).get(obj.id) or {}).get("quiz")

    def get_locked(self, obj) -> bool:
        return self._lock(obj) is not None

    def get_lock_reason(self, obj) -> str | None:
        return self._lock(obj)

    def get_completed(self, obj) -> bool:
        return obj.id in self.context.get("completed_ids", set())

    def get_has_attachment(self, obj) -> bool:
        return bool(obj.attachment)


class SectionOutlineSerializer(serializers.ModelSerializer):
    lessons = LessonOutlineSerializer(many=True, read_only=True)
    exam = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ["id", "title", "order", "lessons", "exam"]

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_exam(self, obj):
        """امتحان الوحدة: {..., locked, lock_reason: unit (خلّص الدروس) | sequence (الوحدة اللي قبلها)} أو null"""
        return ((self.context.get("path") or {}).get("sections", {}).get(obj.id) or {}).get("exam")


class CourseListSerializer(serializers.ModelSerializer):
    instructor = UserMiniSerializer(read_only=True)
    subject = SubjectMiniSerializer(read_only=True)
    is_free = serializers.BooleanField(read_only=True)
    lessons_count = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ["id", "title", "slug", "short_description", "thumbnail", "instructor", "subject", "grade", "price",
                  "old_price", "currency", "is_free", "level", "rating_avg", "rating_count", "students_count",
                  "lessons_count", "is_featured", "published_at", "included_in_subscription", "status"]


    def get_lessons_count(self, obj) -> int:
        n = getattr(obj, "lessons_count", None)
        return n if n is not None else Lesson.objects.filter(section__course=obj).count()


class CourseDetailSerializer(CourseListSerializer):
    sections = serializers.SerializerMethodField()
    is_enrolled = serializers.SerializerMethodField()
    progress_percent = serializers.SerializerMethodField()
    total_duration_seconds = serializers.SerializerMethodField()

    class Meta(CourseListSerializer.Meta):
        fields = CourseListSerializer.Meta.fields + [
            "description", "promo_video_url", "what_you_learn", "requirements", "language", "access_days",
            "meta_description", "sections", "is_enrolled", "progress_percent", "total_duration_seconds",
            "included_in_subscription", "certificate_enabled", "access", "free_lessons_count", "certificate_code", "sequential"]

    @extend_schema_field(SectionOutlineSerializer(many=True))
    def get_sections(self, obj):
        return SectionOutlineSerializer(obj.sections.prefetch_related("lessons"), many=True, context=self.context).data

    access = serializers.SerializerMethodField()
    free_lessons_count = serializers.SerializerMethodField()
    certificate_code = serializers.SerializerMethodField()

    def get_access(self, obj) -> dict:
        """full: كل الدروس مفتوحة — via: owner | enrollment | subscription | null"""
        a = self.context.get("access") or {}
        return {"full": bool(a.get("full")), "via": a.get("via")}

    def get_free_lessons_count(self, obj) -> int:
        return sum(1 for sec in obj.sections.all() for l in sec.lessons.all() if l.access != "paid")

    def get_certificate_code(self, obj) -> str | None:
        req = self.context.get("request")
        if not (req and req.user.is_authenticated):
            return None
        c = obj.certificates.filter(student=req.user).first()
        return c.code if c else None

    def get_is_enrolled(self, obj) -> bool:
        return bool(self.context.get("enrollment"))

    def get_progress_percent(self, obj) -> int:
        e = self.context.get("enrollment")
        return e.progress_percent if e else 0

    def get_total_duration_seconds(self, obj) -> int:
        return sum(l.duration_seconds for s in obj.sections.all() for l in s.lessons.all())


class LessonContentSerializer(serializers.ModelSerializer):
    """
    محتوى الدرس للي عنده صلاحية:
    - يوتيوب/فيميو/Bunny → embed_url (اعرضه في WebView/iframe)
    - فيديو مرفوع → stream_url (رابط موقّع مؤقت، بيدعم Range — شغّله بـ video_player)
    - watermark: اسم الطالب يتعرض فوق الفيديو (حماية من تصوير الشاشة)
    """
    is_preview = serializers.BooleanField(read_only=True)
    embed_url = serializers.CharField(read_only=True)
    stream_url = serializers.SerializerMethodField()
    external_url = serializers.SerializerMethodField()
    attachment_url = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    content_html = serializers.SerializerMethodField()
    position_seconds = serializers.SerializerMethodField()
    completed = serializers.SerializerMethodField()
    watermark = serializers.SerializerMethodField()

    class Meta:
        model = Lesson
        fields = ["id", "title", "type", "video_provider", "video_id", "embed_url", "stream_url", "external_url",
                  "thumbnail", "attachment_url", "attachment_name", "content", "content_html", "quiz",
                  "duration_seconds", "access", "is_preview", "position_seconds", "completed", "watermark"]

    def _signed(self, obj, kind):
        from django.urls import reverse
        from .video import make_stream_token
        req = self.context["request"]
        uid = req.user.id if req.user.is_authenticated else 0
        url = reverse("course-media", args=[make_stream_token(obj.id, uid)]) + f"?k={kind}"
        return req.build_absolute_uri(url)

    def get_stream_url(self, obj) -> str | None:
        return self._signed(obj, "v") if obj.video_file else None

    def get_external_url(self, obj) -> str | None:
        if obj.video_provider in ("direct", "other") and obj.video_url:
            return obj.video_url
        return None

    def get_attachment_url(self, obj) -> str | None:
        return self._signed(obj, "a") if obj.attachment else None

    def get_attachment_name(self, obj) -> str | None:
        import os
        return os.path.basename(obj.attachment.name) if obj.attachment else None

    def get_content_html(self, obj) -> str:
        from apps.core.richtext import text_to_html
        return text_to_html(obj.content)

    def get_position_seconds(self, obj) -> int:
        return self.context.get("position", 0)

    def get_completed(self, obj) -> bool:
        return bool(self.context.get("completed"))

    def get_watermark(self, obj) -> str | None:
        u = self.context["request"].user
        if not u.is_authenticated:
            return None
        return f"{u.full_name} · {u.username or u.phone or u.id}"


class LessonNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LessonNote
        fields = ["id", "lesson", "position_seconds", "text", "created_at"]
        read_only_fields = ["lesson"]


class CertificateSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    course_slug = serializers.CharField(source="course.slug", read_only=True)

    class Meta:
        model = Certificate
        fields = ["code", "student_name", "course_title", "course_slug", "instructor_name", "hours", "created_at", "url"]

    def get_url(self, obj) -> str:
        req = self.context.get("request")
        return req.build_absolute_uri(obj.get_absolute_url()) if req else obj.get_absolute_url()


class ProgressSerializer(serializers.Serializer):
    position_seconds = serializers.IntegerField(min_value=0, required=False, default=0)
    completed = serializers.BooleanField(required=False, default=False)
    duration_seconds = serializers.IntegerField(min_value=0, required=False,
                                                help_text="مدة الفيديو الفعلية من المشغل — بتتحفظ لو المدرس مكتبهاش")


class EnrollmentSerializer(serializers.ModelSerializer):
    course = CourseListSerializer(read_only=True)

    class Meta:
        model = Enrollment
        fields = ["id", "course", "source", "progress_percent", "completed_at", "expires_at", "last_lesson", "created_at"]


class CourseReviewSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)

    class Meta:
        model = CourseReview
        fields = ["id", "student", "rating", "comment", "created_at"]


# ---------- Instructor management ----------
class InstructorCourseSerializer(serializers.ModelSerializer):
    sections_count = serializers.IntegerField(read_only=True, default=0)
    lessons_count = serializers.IntegerField(read_only=True, default=0)
    instructor = UserMiniSerializer(read_only=True)
    checklist = serializers.SerializerMethodField()

    class Meta:
        model = Course
        fields = ["id", "title", "slug", "subject", "grade", "short_description", "description", "thumbnail",
                  "promo_video_url", "price", "old_price", "currency", "level", "language", "what_you_learn",
                  "requirements", "access_days", "included_in_subscription", "certificate_enabled", "sequential", "status",
                  "rejection_reason", "students_count", "rating_avg", "meta_description", "created_at", "published_at",
                  "instructor", "sections_count", "lessons_count", "checklist"]
        read_only_fields = ["slug", "status", "rejection_reason", "students_count", "rating_avg", "published_at"]

    def get_checklist(self, obj) -> list:
        """خطوات تجهيز الكورس قبل النشر — [{key, label, done, required}]"""
        lessons = list(Lesson.objects.filter(section__course=obj).values("access", "type"))
        return [
            {"key": "title", "label": "اسم واضح للكورس", "done": len(obj.title) >= 10, "required": True},
            {"key": "description", "label": "وصف الكورس (اللي هيتعلمه الطالب)", "done": len(obj.description or "") >= 80, "required": False},
            {"key": "thumbnail", "label": "صورة غلاف", "done": bool(obj.thumbnail), "required": False},
            {"key": "lessons", "label": "3 دروس على الأقل", "done": len(lessons) >= 3, "required": True},
            {"key": "free", "label": "درس مجاني واحد على الأقل يشجع الطالب", "done": any(l["access"] != "paid" for l in lessons), "required": False},
        ]


def _quiz_brief(q):
    if not q:
        return None
    return {"id": q.id, "title": q.title, "kind": q.kind, "questions_count": q.questions.count(),
            "is_published": q.is_published, "pass_percent": q.pass_percent, "max_attempts": q.max_attempts}


class InstructorSectionSerializer(serializers.ModelSerializer):
    exam_info = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ["id", "course", "title", "order", "exam", "exam_required", "exam_info"]
        read_only_fields = ["exam"]

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_exam_info(self, obj):
        return _quiz_brief(obj.exam)


class InstructorLessonSerializer(serializers.ModelSerializer):
    """
    فيديو الدرس بطريقتين:
    1) video_url: أي رابط يوتيوب (عادي/مختصر/shorts) أو فيميو أو Bunny — بيتفهم تلقائي.
       ⚠️ خلّي فيديو اليوتيوب «غير مدرج Unlisted» عشان ما يظهرش في البحث.
    2) video_file: رفع مباشر (multipart) — بيتخزن محمي ويتعرض للطالب برابط موقّع مؤقت بس.
    """
    video_file = serializers.FileField(write_only=True, required=False, allow_null=True, validators=[_video_ext],
                                       help_text="mp4/webm/mov — حد أقصى VIDEO_MAX_UPLOAD_MB")
    attachment = serializers.FileField(write_only=True, required=False, allow_null=True)
    has_video_file = serializers.SerializerMethodField()
    video_file_name = serializers.SerializerMethodField()
    attachment_name = serializers.SerializerMethodField()
    embed_url = serializers.CharField(read_only=True)
    is_preview = serializers.BooleanField(read_only=True)
    remove_attachment = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = Lesson
        fields = ["id", "section", "title", "type", "video_provider", "video_url", "video_id", "embed_url", "thumbnail",
                  "video_file", "has_video_file", "video_file_name", "attachment", "attachment_name", "remove_attachment",
                  "content", "quiz", "quiz_required", "quiz_info", "duration_seconds", "access", "is_preview", "order"]
        read_only_fields = ["video_provider", "video_id", "quiz"]

    quiz_info = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_quiz_info(self, obj):
        return _quiz_brief(obj.quiz)

    def get_has_video_file(self, obj) -> bool:
        return bool(obj.video_file)

    def get_video_file_name(self, obj) -> str | None:
        import os
        return os.path.basename(obj.video_file.name) if obj.video_file else None

    def get_attachment_name(self, obj) -> str | None:
        import os
        return os.path.basename(obj.attachment.name) if obj.attachment else None

    def validate_access(self, v):
        from django.conf import settings
        req = self.context.get("request")
        if v != "paid" and req and req.user.role == "teacher" and not settings.TEACHER_CAN_SET_FREE_LESSONS:
            raise serializers.ValidationError("الإدارة بس اللي تقدر تفتح دروس مجاناً.")
        return v

    def validate_video_url(self, v):
        from .video import parse_video_url
        if v and parse_video_url(v)[0] == "other" and ("youtu" in v or "vimeo" in v):
            raise serializers.ValidationError("رابط الفيديو مش مفهوم — انسخ الرابط من زرار «مشاركة» في يوتيوب.")
        return v

    def validate(self, attrs):
        inst = self.instance
        typ = attrs.get("type", inst.type if inst else "video")
        url = attrs.get("video_url", inst.video_url if inst else "")
        has_file = attrs.get("video_file") or (inst and inst.video_file and "video_url" not in attrs)
        if typ == "video" and not url and not has_file:
            raise serializers.ValidationError({"video_url": "حط رابط الفيديو أو ارفع الفيديو."})
        return attrs

    def _apply_files(self, inst, attrs):
        if attrs.pop("remove_attachment", False) and inst and inst.attachment:
            inst.attachment.delete(save=False)
        new_file = attrs.get("video_file")
        if new_file:
            attrs["video_url"] = ""           # رفع فيديو جديد بيلغي الرابط
            if inst and inst.video_file:
                inst.video_file.delete(save=False)
        elif attrs.get("video_url") and inst and inst.video_file:
            inst.video_file.delete(save=False)  # التحويل من ملف مرفوع لرابط بيمسح الملف القديم
            attrs["video_file"] = None
        return attrs

    def create(self, validated):
        return super().create(self._apply_files(None, validated))

    def update(self, inst, validated):
        return super().update(inst, self._apply_files(inst, validated))


class ReorderSerializer(serializers.Serializer):
    sections = serializers.ListField(child=serializers.IntegerField(), required=False,
                                     help_text="ترتيب الوحدات: [id, id, ...]")
    lessons = serializers.DictField(child=serializers.ListField(child=serializers.IntegerField()), required=False,
                                    help_text='ترتيب الدروس جوه كل وحدة (وممكن تنقل درس لوحدة تانية): {"<section_id>": [lesson ids]}')


class BulkAccessSerializer(serializers.Serializer):
    lesson_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)
    access = serializers.ChoiceField(choices=Lesson.ACCESS)


class CourseReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True)
