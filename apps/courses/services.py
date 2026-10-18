from django.db.models import Avg, Count, F
from django.utils import timezone

from apps.notifications.services import notify

from .models import Certificate, Course, CourseReview, Enrollment, Lesson, LessonProgress


def enroll(student, course, source="purchase"):
    expires = timezone.now() + timezone.timedelta(days=course.access_days) if course.access_days else None
    enr, created = Enrollment.objects.get_or_create(student=student, course=course,
                                                     defaults={"source": source, "expires_at": expires})
    if not created and enr.expires_at and enr.expires_at < timezone.now():
        enr.expires_at = expires  # تجديد وصول منتهي
        enr.save(update_fields=["expires_at"])
    if created:
        Course.objects.filter(pk=course.pk).update(students_count=F("students_count") + 1)
        notify(student, "course_enrolled", "تم الاشتراك في الكورس 🎓", course.title, {"screen": "course", "slug": course.slug})
    return enr


def active_enrollment(user, course):
    if not user.is_authenticated:
        return None
    enr = Enrollment.objects.filter(student=user, course=course).first()
    if enr and enr.expires_at and enr.expires_at < timezone.now():
        return None
    return enr


def has_subscription_access(user, course) -> bool:
    """طالب عنده اشتراك حصص لايف شغال مع مدرس الكورس (والكورس مفتوح لطلاب الاشتراك)."""
    if not (course.included_in_subscription and user.is_authenticated):
        return False
    from apps.tutoring.models import Subscription
    return Subscription.objects.filter(student=user, teacher_id=course.instructor_id, status="active").exists()


def course_access(user, course):
    """
    مين يقدر يشوف الدروس المدفوعة؟
    يرجّع dict: full (كل الدروس مفتوحة) + via (owner | enrollment | subscription | None) + enrollment.
    """
    enr = active_enrollment(user, course)
    via = None
    if user.is_authenticated and (course.instructor_id == user.id or user.role in ("admin", "supervisor") or user.is_superuser):
        via = "owner"
    elif enr and enr.source != "subscription":
        via = "enrollment"
    elif has_subscription_access(user, course):
        via = "subscription"  # التسجيل اللي جه من الاشتراك بيفضل شغال طول ما الاشتراك شغال بس
    return {"full": via is not None, "via": via, "enrollment": enr}


def lesson_lock(user, lesson, access) -> str | None:
    """None لو الدرس مفتوح، أو سبب القفل: login (سجّل دخول) | payment (محتاج اشتراك/دفع)."""
    if access["full"] or lesson.access == "free":
        return None
    if lesson.access == "members":
        return None if user.is_authenticated else "login"
    return "payment"


def ensure_enrollment(user, course, access):
    """طالب الاشتراك اللايف بيتسجل في الكورس أوتوماتيك أول ما يفتحه عشان تقدمه يتحفظ."""
    if access["enrollment"] or access["via"] != "subscription":
        return access["enrollment"]
    access["enrollment"] = enroll(user, course, source="subscription")
    return access["enrollment"]


def issue_certificate(enr: Enrollment):
    course = enr.course
    if not course.certificate_enabled:
        return None
    total = sum(l.duration_seconds for l in Lesson.objects.filter(section__course=course))
    cert, created = Certificate.objects.get_or_create(student=enr.student, course=course, defaults={
        "student_name": enr.student.full_name, "course_title": course.title,
        "instructor_name": course.instructor.full_name, "hours": round(total / 3600, 1)})
    if created:
        notify(enr.student, "certificate_issued", "شهادتك جاهزة 🎓", course.title,
               {"screen": "certificate", "code": cert.code})
    return cert


# ============================================================ مسار التعلم: كويز بعد كل درس + امتحان آخر كل وحدة
def quiz_results(user, quiz_ids) -> dict:
    """{quiz_id: {attempts, best_percent, passed, pending}} للطالب ده."""
    from apps.assessments.models import Attempt
    res = {}
    if not (user and user.is_authenticated and quiz_ids):
        return res
    for a in Attempt.objects.filter(student=user, quiz_id__in=quiz_ids).exclude(status="in_progress").select_related("quiz"):
        r = res.setdefault(a.quiz_id, {"attempts": 0, "best_percent": None, "passed": False, "pending": False})
        r["attempts"] += 1
        if a.status == "graded":
            r["best_percent"] = max(r["best_percent"] or 0, a.percent)
            r["passed"] = r["passed"] or a.passed
        else:
            r["pending"] = True
    return res


def _course_sections(course):
    from django.db.models import Prefetch
    return list(course.sections.select_related("exam").prefetch_related(
        Prefetch("lessons", queryset=Lesson.objects.select_related("quiz").order_by("order", "id"))).order_by("order", "id"))


def _active(quiz):
    """الكويز بيتحسب بس لو المدرس نشره وفيه أسئلة."""
    return bool(quiz and quiz.is_published and quiz.questions.exists())


def _qinfo(quiz, r, **extra):
    return {"id": quiz.id, "title": quiz.title, "kind": quiz.kind, "questions_count": quiz.questions.count(),
            "pass_percent": quiz.pass_percent, "max_attempts": quiz.max_attempts, "time_limit_minutes": quiz.time_limit_minutes,
            "attempts": r.get("attempts", 0), "best_percent": r.get("best_percent"), "passed": r.get("passed", False),
            "pending": r.get("pending", False), **extra}


def learning_path(user, course, enr=None, owner=False) -> dict:
    """
    حالة الطالب في الكورس:
    lessons: {lesson_id: {seq_locked, quiz}}، sections: {section_id: {exam}}، total/done (للنسبة).
    - لو الكورس «بالترتيب»: الدرس بيتقفل لحد ما ينجح في كويز الدرس اللي قبله، والوحدة لحد ما ينجح في امتحان اللي قبلها.
    - امتحان الوحدة بيتفتح لما كل دروس الوحدة تخلص.
    """
    sections = _course_sections(course)
    quizzes = [l.quiz for s in sections for l in s.lessons.all() if l.quiz_id] + [s.exam for s in sections if s.exam_id]
    results = quiz_results(user, [q.id for q in quizzes])
    completed = set(enr.lesson_progress.filter(completed=True).values_list("lesson_id", flat=True)) if enr else set()
    seq = course.sequential and not owner
    gate = True  # كل اللي قبل كده اتعدّى؟
    lessons, secs, total, done = {}, {}, 0, 0
    for s in sections:
        unit_done = True
        for l in s.lessons.all():
            locked = seq and not gate
            q = l.quiz if _active(l.quiz) else None
            r = results.get(q.id, {}) if q else {}
            lessons[l.id] = {"seq_locked": locked,
                             "quiz": _qinfo(q, r, required=l.quiz_required, locked=locked) if q else None}
            total += 1
            if l.id in completed:
                done += 1
            else:
                unit_done = False
            if seq and q and l.quiz_required and not r.get("passed"):
                gate = False
        ex = s.exam if _active(s.exam) else None
        if ex:
            r = results.get(ex.id, {})
            reason = None if owner else ("sequence" if seq and not gate else ("unit" if not unit_done else None))
            secs[s.id] = {"exam": _qinfo(ex, r, required=s.exam_required, locked=bool(reason), lock_reason=reason)}
            total += 1
            if r.get("passed"):
                done += 1
            if seq and s.exam_required and not r.get("passed"):
                gate = False
        else:
            secs[s.id] = {"exam": None}
    return {"lessons": lessons, "sections": secs, "total": total, "done": done}


def lesson_needs_quiz(lesson) -> bool:
    """الدرس ده محتاج نجاح في كويز عشان يتعلّم إنه خلص؟"""
    return bool(lesson.quiz_required and _active(lesson.quiz))


def quiz_gate(user, quiz):
    """قبل ما الطالب يبدأ كويز درس/امتحان وحدة: لو مقفول يرجّع رسالة، غير كده None (وبيسجّله في الكورس لو داخل بالاشتراك)."""
    lesson = Lesson.objects.filter(quiz=quiz).select_related("section__course").first()
    from .models import Section
    section = None if lesson else Section.objects.filter(exam=quiz).select_related("course").first()
    if not (lesson or section):
        return None
    course = lesson.section.course if lesson else section.course
    access = course_access(user, course)
    if lesson and lesson_lock(user, lesson, access):
        return "اشترك في الكورس الأول عشان تحل الكويز ده."
    if section and not access["full"]:
        return "اشترك في الكورس الأول عشان تمتحن امتحان الوحدة."
    enr = ensure_enrollment(user, course, access)
    if not enr and course.is_free and user.role == "student":
        enr = enroll(user, course, source="free")
    if not enr:
        return "اشترك في الكورس الأول."
    path = learning_path(user, course, enr, owner=access["via"] == "owner")
    if lesson and path["lessons"].get(lesson.id, {}).get("seq_locked"):
        return "لازم تنجح في كويز الدرس اللي قبله الأول."
    if section:
        ex = path["sections"].get(section.id, {}).get("exam") or {}
        if ex.get("lock_reason") == "sequence":
            return "لازم تنجح في امتحان الوحدة اللي قبلها الأول."
        if ex.get("lock_reason") == "unit":
            return "خلّص كل دروس الوحدة الأول وبعدها امتحان الوحدة هيتفتح."
    return None


def on_quiz_result(attempt):
    """بعد تصحيح أي محاولة: لو نجح في كويز درس → الدرس يتعلّم إنه خلص، ونحدّث نسبة التقدم."""
    if not attempt.passed:
        return
    from .models import Section
    lessons = list(Lesson.objects.filter(quiz=attempt.quiz).select_related("section__course"))
    courses = {l.section.course_id for l in lessons} | set(
        Section.objects.filter(exam=attempt.quiz).values_list("course_id", flat=True))
    for cid in courses:
        enr = Enrollment.objects.filter(student=attempt.student, course_id=cid).first()
        if not enr:
            continue
        for l in lessons:
            if l.section.course_id == cid:
                lp, _ = LessonProgress.objects.get_or_create(enrollment=enr, lesson=l)
                if not lp.completed:
                    lp.completed = True
                    lp.save(update_fields=["completed", "updated_at"])
        recalc_progress(enr)


def recalc_progress(enr: Enrollment):
    p = learning_path(enr.student, enr.course, enr)
    total, done = p["total"], p["done"]
    enr.progress_percent = int(done * 100 / total) if total else 0
    if enr.progress_percent == 100 and not enr.completed_at:
        enr.completed_at = timezone.now()
        notify(enr.student, "course_completed", "مبروك! خلصت الكورس 🏆", enr.course.title,
               {"screen": "course", "slug": enr.course.slug})
    enr.save(update_fields=["progress_percent", "completed_at", "last_lesson", "updated_at"])
    if enr.progress_percent == 100:
        issue_certificate(enr)


def refresh_course_rating(course):
    agg = CourseReview.objects.filter(course=course, is_visible=True).aggregate(a=Avg("rating"), c=Count("id"))
    course.rating_avg = round(agg["a"] or 0, 2)
    course.rating_count = agg["c"]
    course.save(update_fields=["rating_avg", "rating_count"])
