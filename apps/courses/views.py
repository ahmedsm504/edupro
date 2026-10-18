from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsStaffRole, IsTeacherOrStaff, Roles
from apps.notifications.services import notify, notify_staff

from . import serializers as s
from . import services
from .models import Certificate, Course, CourseReview, Enrollment, Lesson, LessonNote, LessonProgress, Section


@extend_schema_view(
    list=extend_schema(summary="الكورسات المنشورة",
                       description="فلاتر: ?subject=&grade=&instructor=&level=&is_featured=true&free=true&search=&ordering=-students_count\n"
                                   "for_me=true: الكورسات المفتوحة لي (مشترك فيها أو ضمن اشتراك الحصص مع المدرس)"),
    retrieve=extend_schema(summary="صفحة الكورس + المنهج (الدروس المقفولة locked=true)"),
)
@extend_schema(tags=["Courses"])
class CourseViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_fields = ["subject", "grade", "instructor", "level", "is_featured", "subject__slug"]
    search_fields = ["title", "short_description", "instructor__full_name"]
    ordering_fields = ["published_at", "price", "rating_avg", "students_count"]

    def get_queryset(self):
        u = self.request.user
        base = Course.objects.all()
        visible = Q(status="published")
        if self.action != "list" and u.is_authenticated:
            # المدرس والإدارة يقدروا يعاينوا الكورس قبل النشر
            if u.role in Roles.STAFF:
                visible = Q(pk__isnull=False)
            elif u.role == Roles.TEACHER:
                visible |= Q(instructor=u)
        qs = (base.filter(visible).select_related("instructor", "subject")
              .annotate(lessons_count=Count("sections__lessons", distinct=True)).order_by("-is_featured", "-published_at", "-id"))
        p = self.request.query_params
        if p.get("free") in ("1", "true"):
            qs = qs.filter(price=0)
        if p.get("for_me") in ("1", "true") and u.is_authenticated:
            from apps.tutoring.models import Subscription
            teachers = Subscription.objects.filter(student=u, status="active").values("teacher_id")
            qs = qs.filter(Q(enrollments__student=u) | Q(included_in_subscription=True, instructor_id__in=teachers)).distinct()
        return qs

    def get_serializer_class(self):
        return s.CourseDetailSerializer if self.action == "retrieve" else s.CourseListSerializer

    def _ctx(self, course):
        access = services.course_access(self.request.user, course)
        enr = access["enrollment"]
        completed = set(enr.lesson_progress.filter(completed=True).values_list("lesson_id", flat=True)) if enr else set()
        path = services.learning_path(self.request.user, course, enr, owner=access["via"] == "owner")
        return {"request": self.request, "enrollment": enr, "access": access, "has_access": access["full"],
                "completed_ids": completed, "path": path}

    def _check_sequence(self, course, lesson, enr, access):
        if not course.sequential or access["via"] == "owner":
            return
        path = services.learning_path(self.request.user, course, enr)
        if path["lessons"].get(lesson.id, {}).get("seq_locked"):
            raise BusinessError("لازم تنجح في كويز الدرس اللي قبله (أو امتحان الوحدة اللي قبلها) الأول.",
                                code="sequence_locked", status_code=403)

    def retrieve(self, request, *a, **kw):
        course = self.get_object()
        return Response(s.CourseDetailSerializer(course, context=self._ctx(course)).data)

    @extend_schema(summary="الاشتراك في كورس مجاني (المدفوع يتم من /payments/checkout/)", request=None,
                   responses=s.EnrollmentSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def enroll(self, request, slug=None):
        course = self.get_object()
        if request.user.role != Roles.STUDENT:
            raise BusinessError("الاشتراك في الكورسات للطلاب.", code="forbidden", status_code=403)
        if not course.is_free:
            raise BusinessError("الكورس مدفوع — كمل الدفع الأول.", code="payment_required", status_code=402)
        enr = services.enroll(request.user, course, source="free")
        return Response(s.EnrollmentSerializer(enr, context={"request": request}).data)

    @extend_schema(summary="محتوى درس — الفيديو/الملف (لازم يكون الدرس مفتوح لك)",
                   description="لو مقفول: 401 login_required (الدرس للمسجلين) أو 403 lesson_locked (محتاج دفع/اشتراك).",
                   responses=s.LessonContentSerializer)
    @action(detail=True, methods=["get"], url_path=r"lessons/(?P<lesson_id>\d+)")
    def lesson(self, request, slug=None, lesson_id=None):
        course = self.get_object()
        lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
        access = services.course_access(request.user, course)
        lock = services.lesson_lock(request.user, lesson, access)
        if lock == "login":
            raise BusinessError("سجّل دخول عشان تشوف الدرس ده — ببلاش.", code="login_required", status_code=401)
        if lock:
            raise BusinessError("الدرس ده للمشتركين — اشترك في الكورس عشان يتفتح.", code="lesson_locked", status_code=403)
        enr = services.ensure_enrollment(request.user, course, access)
        self._check_sequence(course, lesson, enr, access)
        lp = LessonProgress.objects.filter(enrollment=enr, lesson=lesson).first() if enr else None
        return Response(s.LessonContentSerializer(lesson, context={
            "request": request, "position": lp.position_seconds if lp else 0, "completed": bool(lp and lp.completed)}).data)

    @extend_schema(summary="حفظ التقدم في درس (كل 15-30 ثانية أثناء الفيديو، و completed=true في الآخر)",
                   request=s.ProgressSerializer, responses=s.EnrollmentSerializer)
    @action(detail=True, methods=["post"], url_path=r"lessons/(?P<lesson_id>\d+)/progress", permission_classes=[IsAuthenticated])
    def progress(self, request, slug=None, lesson_id=None):
        course = self.get_object()
        lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
        access = services.course_access(request.user, course)
        if services.lesson_lock(request.user, lesson, access):
            raise BusinessError("الدرس ده مقفول.", code="lesson_locked", status_code=403)
        enr = services.ensure_enrollment(request.user, course, access)
        self._check_sequence(course, lesson, enr, access)
        if not enr:
            if request.user.role != Roles.STUDENT or lesson.access == "paid":
                return Response({"saved": False})  # المدرس/الإدارة بيتفرجوا بس
            enr = services.enroll(request.user, course, source="free") if course.is_free else None
            if not enr:
                return Response({"saved": False})  # درس مجاني من كورس مدفوع: مفيش تسجيل
        ser = s.ProgressSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        lp, _ = LessonProgress.objects.get_or_create(enrollment=enr, lesson=lesson)
        lp.position_seconds = ser.validated_data["position_seconds"]
        if ser.validated_data["completed"] and services.lesson_needs_quiz(lesson):
            # الدرس اللي عليه كويز إجباري بيخلص لما الطالب ينجح في الكويز (on_quiz_result)
            passed = services.quiz_results(request.user, [lesson.quiz_id]).get(lesson.quiz_id, {}).get("passed")
            lp.completed = lp.completed or bool(passed)
        else:
            lp.completed = lp.completed or ser.validated_data["completed"]
        lp.save()
        dur = ser.validated_data.get("duration_seconds")
        if dur and not lesson.duration_seconds:
            Lesson.objects.filter(pk=lesson.pk).update(duration_seconds=dur)
        enr.last_lesson = lesson
        services.recalc_progress(enr)
        return Response(s.EnrollmentSerializer(enr, context={"request": request}).data)

    @extend_schema(methods=["GET"], summary="ملاحظاتي على الدرس", responses=s.LessonNoteSerializer(many=True))
    @extend_schema(methods=["POST"], summary="إضافة ملاحظة عند ثانية معينة", request=s.LessonNoteSerializer,
                   responses=s.LessonNoteSerializer)
    @action(detail=True, methods=["get", "post"], url_path=r"lessons/(?P<lesson_id>\d+)/notes",
            permission_classes=[IsAuthenticated], pagination_class=None)
    def notes(self, request, slug=None, lesson_id=None):
        course = self.get_object()
        lesson = get_object_or_404(Lesson, pk=lesson_id, section__course=course)
        if request.method == "GET":
            return Response(s.LessonNoteSerializer(LessonNote.objects.filter(student=request.user, lesson=lesson), many=True).data)
        if services.lesson_lock(request.user, lesson, services.course_access(request.user, course)):
            raise BusinessError("الدرس ده مقفول.", code="lesson_locked", status_code=403)
        ser = s.LessonNoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        note = ser.save(student=request.user, lesson=lesson)
        return Response(s.LessonNoteSerializer(note).data, status=status.HTTP_201_CREATED)

    @extend_schema(methods=["GET"], summary="تقييمات الكورس", responses=s.CourseReviewSerializer(many=True))
    @extend_schema(methods=["POST"], summary="تقييم الكورس (للمشتركين)", request=s.CourseReviewSerializer,
                   responses=s.CourseReviewSerializer)
    @action(detail=True, methods=["get", "post"])
    def reviews(self, request, slug=None):
        course = self.get_object()
        if request.method == "GET":
            page = self.paginate_queryset(course.reviews.filter(is_visible=True).select_related("student"))
            return self.get_paginated_response(s.CourseReviewSerializer(page, many=True).data)
        if not request.user.is_authenticated or not services.active_enrollment(request.user, course):
            raise BusinessError("لازم تكون مشترك في الكورس.", code="not_enrolled", status_code=403)
        ser = s.CourseReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        rev, _ = CourseReview.objects.update_or_create(course=course, student=request.user, defaults=ser.validated_data)
        services.refresh_course_rating(course)
        return Response(s.CourseReviewSerializer(rev).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Courses"])
@schema_safe(Enrollment)
class MyEnrollmentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = s.EnrollmentSerializer

    def get_queryset(self):
        u = self.request.user
        return Enrollment.objects.filter(student=u).select_related("course__instructor", "course__subject")

    @extend_schema(summary="كورساتي")
    def list(self, request, *a, **kw):
        return super().list(request, *a, **kw)


@extend_schema(tags=["Courses"])
@schema_safe(LessonNote)
class MyNoteViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """تعديل/مسح ملاحظة من ملاحظاتي."""
    serializer_class = s.LessonNoteSerializer

    def get_queryset(self):
        return LessonNote.objects.filter(student=self.request.user)


@extend_schema(tags=["Courses"])
@schema_safe(Certificate)
class MyCertificateViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = s.CertificateSerializer

    def get_queryset(self):
        return Certificate.objects.filter(student=self.request.user).select_related("course")

    @extend_schema(summary="شهاداتي (رابط عام للتحقق لكل شهادة)")
    def list(self, request, *a, **kw):
        return super().list(request, *a, **kw)


# ======================= Protected media (signed, Range) =======================
def _range_response(path, content_type, size, range_header):
    """بيرجّع جزء من الملف (206) عشان المشغل يقدر يقدّم ويأخّر من غير ما ينزّل الفيديو كله."""
    import re as _re
    from django.http import HttpResponse, StreamingHttpResponse

    m = _re.match(r"bytes=(\d*)-(\d*)", range_header or "")
    if not m or (not m.group(1) and not m.group(2)):
        return None
    if m.group(1):
        start = int(m.group(1))
        end = int(m.group(2)) if m.group(2) else size - 1
    else:  # bytes=-500 → آخر 500 بايت
        start, end = max(0, size - int(m.group(2))), size - 1
    if start >= size:
        r = HttpResponse(status=416)
        r["Content-Range"] = f"bytes */{size}"
        return r
    end = min(end, size - 1)
    length = end - start + 1

    def chunks(chunk=1024 * 512):
        with open(path, "rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                data = f.read(min(chunk, left))
                if not data:
                    break
                left -= len(data)
                yield data

    r = StreamingHttpResponse(chunks(), status=206, content_type=content_type)
    r["Content-Range"] = f"bytes {start}-{end}/{size}"
    r["Content-Length"] = str(length)
    return r


def course_media(request, token):
    """
    GET /api/v1/courses/media/<token>/?k=v|a — فيديو الدرس المرفوع (v) أو الملف المرفق (a).
    الرابط موقّع ومؤقت (VIDEO_LINK_TTL_MINUTES) وبيطلع بس للي ليه صلاحية على الدرس.
    """
    import mimetypes
    import os

    from django.conf import settings
    from django.core import signing
    from django.http import FileResponse, Http404, HttpResponse

    from .video import read_stream_token

    try:
        data = read_stream_token(token)
    except signing.SignatureExpired:
        return HttpResponse("الرابط انتهى — افتح الدرس تاني.", status=410, content_type="text/plain; charset=utf-8")
    except signing.BadSignature:
        raise Http404
    lesson = Lesson.objects.filter(pk=data.get("l")).first()
    f = (lesson.attachment if request.GET.get("k") == "a" else lesson.video_file) if lesson else None
    if not f:
        raise Http404
    path = f.path
    if not os.path.exists(path):
        raise Http404
    ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if settings.PROTECTED_MEDIA_ACCEL:
        r = HttpResponse(content_type=ctype)
        r["X-Accel-Redirect"] = "/_protected/" + os.path.relpath(path, settings.PRIVATE_MEDIA_ROOT).replace(os.sep, "/")
        return r
    size = os.path.getsize(path)
    r = _range_response(path, ctype, size, request.headers.get("Range"))
    if r is None:
        r = FileResponse(open(path, "rb"), content_type=ctype)
        r["Content-Length"] = str(size)
    r["Accept-Ranges"] = "bytes"
    r["Cache-Control"] = "private, max-age=3600"
    r["X-Robots-Tag"] = "noindex"
    if request.GET.get("k") == "a":
        r["Content-Disposition"] = f'inline; filename="{os.path.basename(path)}"'
    return r


# ======================= Instructor (teacher) + admin moderation =======================
class _OwnedMixin:
    permission_classes = [IsTeacherOrStaff]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def _is_staff(self):
        return self.request.user.role in Roles.STAFF or self.request.user.is_superuser


@extend_schema_view(list=extend_schema(summary="كورساتي كمدرس (الإدارة تشوف الكل ?status=pending_review)"))
@extend_schema(tags=["Instructor"])
@schema_safe(Course)
class InstructorCourseViewSet(_OwnedMixin, viewsets.ModelViewSet):
    serializer_class = s.InstructorCourseSerializer
    filterset_fields = ["status", "subject"]
    search_fields = ["title"]

    def get_queryset(self):
        qs = (Course.objects.select_related("instructor")
              .annotate(sections_count=Count("sections", distinct=True), lessons_count=Count("sections__lessons", distinct=True))
              .order_by("-created_at"))
        return qs if self._is_staff() else qs.filter(instructor=self.request.user)

    def perform_create(self, ser):
        ser.save(instructor=self.request.user)

    @extend_schema(summary="منهج الكورس كامل (الوحدات وجواها الدروس) في طلب واحد — لشاشة بناء الكورس",
                   responses=s.InstructorSectionSerializer(many=True))
    @action(detail=True, methods=["get"])
    def outline(self, request, pk=None):
        c = self.get_object()
        ctx = {"request": request}
        return Response([{**s.InstructorSectionSerializer(sec, context=ctx).data,
                          "lessons": s.InstructorLessonSerializer(sec.lessons.all(), many=True, context=ctx).data}
                         for sec in c.sections.prefetch_related("lessons")])

    @extend_schema(summary="ترتيب الوحدات والدروس (ونقل درس من وحدة لوحدة)", request=s.ReorderSerializer, responses=None)
    @action(detail=True, methods=["post"])
    def reorder(self, request, pk=None):
        c = self.get_object()
        ser = s.ReorderSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sec_ids = set(c.sections.values_list("id", flat=True))
        for i, sid in enumerate(ser.validated_data.get("sections", []), 1):
            if sid in sec_ids:
                Section.objects.filter(pk=sid).update(order=i)
        for sid, ids in ser.validated_data.get("lessons", {}).items():
            sid = int(sid)
            if sid not in sec_ids:
                raise BusinessError("وحدة مش تبع الكورس ده.", code="invalid_section")
            for i, lid in enumerate(ids, 1):
                Lesson.objects.filter(pk=lid, section__course=c).update(order=i, section_id=sid)
        return Response({"ok": True})

    @extend_schema(summary="فتح/قفل مجموعة دروس مرة واحدة (مجاني للكل / للمسجلين / بعد الدفع)",
                   description="الإدارة دايماً تقدر. المدرس يقدر بس لو TEACHER_CAN_SET_FREE_LESSONS شغالة.",
                   request=s.BulkAccessSerializer, responses=None)
    @action(detail=True, methods=["post"], url_path="lessons-access")
    def lessons_access(self, request, pk=None):
        from django.conf import settings
        c = self.get_object()
        ser = s.BulkAccessSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        acc = ser.validated_data["access"]
        if acc != "paid" and not self._is_staff() and not settings.TEACHER_CAN_SET_FREE_LESSONS:
            raise BusinessError("الإدارة بس اللي تقدر تفتح دروس مجاناً.", code="forbidden", status_code=403)
        n = Lesson.objects.filter(section__course=c, pk__in=ser.validated_data["lesson_ids"]).update(access=acc)
        return Response({"updated": n})

    def perform_update(self, ser):
        course = ser.save()
        if course.status == "published" and not self._is_staff():
            pass  # تعديل كورس منشور مسموح، ممكن تخليه يرجع للمراجعة لو حابب

    @extend_schema(summary="إرسال الكورس للمراجعة", request=None, responses=s.InstructorCourseSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        c = self.get_object()
        if not Lesson.objects.filter(section__course=c).exists():
            raise BusinessError("ضيف درس واحد على الأقل.", code="empty_course")
        c.status = "pending_review"
        c.save(update_fields=["status"])
        notify_staff("course_review", "كورس محتاج مراجعة", c.title, {"screen": "course_review", "id": c.id})
        return Response(s.InstructorCourseSerializer(c, context={"request": request}).data)

    @extend_schema(summary="(إدارة) نشر/رفض كورس", request=s.CourseReviewActionSerializer, responses=s.InstructorCourseSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def moderate(self, request, pk=None):
        c = self.get_object()
        ser = s.CourseReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if ser.validated_data["action"] == "approve":
            c.status, c.published_at, c.rejection_reason = "published", c.published_at or timezone.now(), ""
            notify(c.instructor, "course_published", "تم نشر الكورس 🎉", c.title)
        else:
            c.status, c.rejection_reason = "rejected", ser.validated_data.get("reason", "")
            notify(c.instructor, "course_rejected", "الكورس محتاج تعديلات", c.rejection_reason)
        c.save()
        return Response(s.InstructorCourseSerializer(c, context={"request": request}).data)

    @extend_schema(summary="(إدارة) إضافة طالب للكورس يدوياً", request=None, responses=s.EnrollmentSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole], url_path=r"enroll-student/(?P<student_id>\d+)")
    def enroll_student(self, request, pk=None, student_id=None):
        from apps.accounts.models import User
        c = self.get_object()
        st = get_object_or_404(User, pk=student_id, role=Roles.STUDENT)
        return Response(s.EnrollmentSerializer(services.enroll(st, c, source="admin"), context={"request": request}).data)


def _new_course_quiz(course, kind, title, max_attempts):
    from apps.assessments.models import Quiz
    return Quiz.objects.create(owner=course.instructor, subject=course.subject, grade=course.grade, course=course,
                               kind=kind, title=title, pass_percent=50, max_attempts=max_attempts,
                               show_answers_after_submit=True, is_published=False)


def _drop_quiz(quiz):
    """لو حد حل الكويز نخليه (عشان النتايج متضيعش) ونقفله بس، غير كده نمسحه."""
    if quiz.attempts.exists():
        quiz.is_published = False
        quiz.save(update_fields=["is_published"])
    else:
        quiz.delete()


@extend_schema(tags=["Instructor"])
@schema_safe(Section)
class InstructorSectionViewSet(_OwnedMixin, viewsets.ModelViewSet):
    serializer_class = s.InstructorSectionSerializer
    filterset_fields = ["course"]
    pagination_class = None

    def get_queryset(self):
        qs = Section.objects.all()
        return qs if self._is_staff() else qs.filter(course__instructor=self.request.user)

    def perform_create(self, ser):
        course = ser.validated_data["course"]
        if not self._is_staff() and course.instructor_id != self.request.user.id:
            raise BusinessError("الكورس ده مش بتاعك.", code="forbidden", status_code=403)
        ser.save()

    @extend_schema(methods=["POST"], summary="إنشاء امتحان الوحدة (بيرجع الوحدة ومعاها exam_info) — بعدها ضيف الأسئلة من teacher/questions",
                   request=None, responses=s.InstructorSectionSerializer)
    @extend_schema(methods=["DELETE"], summary="شيل امتحان الوحدة", request=None, responses=s.InstructorSectionSerializer)
    @action(detail=True, methods=["post", "delete"])
    def exam(self, request, pk=None):
        sec = self.get_object()
        if request.method == "DELETE":
            if sec.exam:
                q = sec.exam
                sec.exam = None
                sec.save(update_fields=["exam"])
                _drop_quiz(q)
        elif not sec.exam:
            sec.exam = _new_course_quiz(sec.course, "exam", f"امتحان {sec.title}", 3)
            sec.save(update_fields=["exam"])
        return Response(s.InstructorSectionSerializer(sec, context={"request": request}).data)


@extend_schema(tags=["Instructor"])
@schema_safe(Lesson)
class InstructorLessonViewSet(_OwnedMixin, viewsets.ModelViewSet):
    """رفع الفيديو المباشر بالـ multipart (video_file) أو حط رابط يوتيوب/فيميو (video_url)."""
    serializer_class = s.InstructorLessonSerializer
    filterset_fields = ["section", "section__course"]
    pagination_class = None

    def get_queryset(self):
        qs = Lesson.objects.all()
        return qs if self._is_staff() else qs.filter(section__course__instructor=self.request.user)

    def _check_section(self, section):
        if section and not self._is_staff() and section.course.instructor_id != self.request.user.id:
            raise BusinessError("الكورس ده مش بتاعك.", code="forbidden", status_code=403)

    def perform_create(self, ser):
        section = ser.validated_data["section"]
        self._check_section(section)
        if "order" not in self.request.data:
            ser.validated_data["order"] = section.lessons.count() + 1
        ser.save()

    def perform_update(self, ser):
        self._check_section(ser.validated_data.get("section"))
        ser.save()

    def perform_destroy(self, inst):
        for f in (inst.video_file, inst.attachment):
            if f:
                f.delete(save=False)
        q = inst.quiz
        inst.delete()
        if q and not q.lessons.exists():
            _drop_quiz(q)

    @extend_schema(methods=["POST"], summary="إنشاء كويز بعد الدرس (بيرجع الدرس ومعاه quiz_info) — بعدها ضيف الأسئلة من teacher/questions",
                   request=None, responses=s.InstructorLessonSerializer)
    @extend_schema(methods=["DELETE"], summary="شيل كويز الدرس", request=None, responses=s.InstructorLessonSerializer)
    @action(detail=True, methods=["post", "delete"])
    def quiz(self, request, pk=None):
        les = self.get_object()
        if request.method == "DELETE":
            if les.quiz:
                q = les.quiz
                les.quiz = None
                les.save(update_fields=["quiz"])
                _drop_quiz(q)
        elif not les.quiz:
            les.quiz = _new_course_quiz(les.section.course, "quiz", f"كويز: {les.title}", 0)
            les.save(update_fields=["quiz"])
        return Response(s.InstructorLessonSerializer(les, context={"request": request}).data)
