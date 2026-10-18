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


def recalc_progress(enr: Enrollment):
    total = Lesson.objects.filter(section__course=enr.course).count()
    done = LessonProgress.objects.filter(enrollment=enr, completed=True).count()
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
