import datetime as dt

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import TeacherProfile, User
from apps.assessments.models import Attempt, QuizAssignment
from apps.chat.models import ContactViolation
from apps.core.permissions import IsStaffRole, Roles
from apps.courses.models import Course, Enrollment
from apps.payments.models import Order
from apps.tutoring.models import Session, SessionReport, Subscription, TrialRequest
from apps.tutoring.serializers import SessionSerializer, SubscriptionSerializer


def _upcoming(qs, request, n=5):
    data = qs.filter(status__in=["scheduled", "live"], scheduled_at__gte=timezone.now() - dt.timedelta(hours=2)).order_by("scheduled_at")[:n]
    return SessionSerializer(data, many=True, context={"request": request}).data


def _today_range():
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + dt.timedelta(days=1)


class DashboardView(APIView):
    @extend_schema(tags=["Dashboard"], summary="الشاشة الرئيسية حسب الدور (طالب/مدرس/مشرف/أدمن)",
                   responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        u = request.user
        fn = {Roles.STUDENT: self.student, Roles.TEACHER: self.teacher,
              Roles.SUPERVISOR: self.supervisor, Roles.ADMIN: self.admin}.get(u.role, self.admin if u.is_superuser else None)
        return Response({"role": u.role, **(fn(request) if fn else {})})

    def _student_summary(self, request, student):
        subs = Subscription.objects.filter(student=student, status__in=["active", "paused", "pending_assignment", "pending_payment"])
        pending_q = QuizAssignment.objects.filter(student=student, quiz__is_published=True).exclude(
            quiz__attempts__student=student, quiz__attempts__status__in=["submitted", "graded"]).count()
        last_reports = SessionReport.objects.filter(session__student=student).select_related("session__subject").order_by("-created_at")[:3]
        return {
            "upcoming_sessions": _upcoming(Session.objects.filter(student=student).select_related("teacher", "subject"), request),
            "subscriptions": SubscriptionSerializer(subs, many=True, context={"request": request}).data,
            "stats": {
                "completed_sessions": Session.objects.filter(student=student, status="completed").count(),
                "absences": Session.objects.filter(student=student, status="student_absent").count(),
                "courses": Enrollment.objects.filter(student=student).count(),
                "pending_quizzes": pending_q,
                "avg_quiz_percent": self._avg_percent(student),
            },
            "latest_reports": [{"session_id": r.session_id, "subject": str(r.session.subject), "date": r.session.scheduled_at,
                                "topics": r.topics, "homework": r.homework, "performance": r.performance} for r in last_reports],
        }

    def _avg_percent(self, student):
        atts = Attempt.objects.filter(student=student, status="graded")
        vals = [a.percent for a in atts[:50]]
        return round(sum(vals) / len(vals), 1) if vals else None

    def student(self, request):
        data = self._student_summary(request, request.user)
        data["continue_courses"] = [
            {"course_id": e.course_id, "title": e.course.title, "slug": e.course.slug,
             "thumbnail": request.build_absolute_uri(e.course.thumbnail.url) if e.course.thumbnail else None,
             "progress_percent": e.progress_percent, "last_lesson": e.last_lesson_id}
            for e in Enrollment.objects.filter(student=request.user, completed_at__isnull=True).select_related("course")[:5]]
        return data

    def teacher(self, request):
        u = request.user
        start, end = _today_range()
        month_start = timezone.localdate().replace(day=1)
        month_sessions = Session.objects.filter(teacher=u, status="completed", scheduled_at__date__gte=month_start)
        return {
            "approval_status": u.teacher_profile.approval_status,
            "upcoming_sessions": _upcoming(Session.objects.filter(teacher=u).select_related("student", "subject"), request, 10),
            "stats": {
                "today_sessions": Session.objects.filter(teacher=u, scheduled_at__range=(start, end)).exclude(status="cancelled").count(),
                "active_students": Subscription.objects.filter(teacher=u, status="active").values("student").distinct().count(),
                "month_completed_sessions": month_sessions.count(),
                "month_minutes": month_sessions.aggregate(m=Sum("duration"))["m"] or 0,
                "reports_missing": Session.objects.filter(teacher=u, status="completed", report__isnull=True).count(),
                "to_grade": Attempt.objects.filter(quiz__owner=u, status="submitted").count(),
                "rating_avg": float(u.teacher_profile.rating_avg), "rating_count": u.teacher_profile.rating_count,
                "courses": Course.objects.filter(instructor=u).count(),
            },
        }

    def supervisor(self, request):
        u = request.user
        start, end = _today_range()
        sessions = Session.objects.filter(teacher__teacher_profile__supervisor=u)
        return {
            "teachers_count": TeacherProfile.objects.filter(supervisor=u).count(),
            "live_now": SessionSerializer(sessions.filter(status="live").select_related("teacher", "student", "subject"),
                                          many=True, context={"request": request}).data,
            "stats": {
                "today_sessions": sessions.filter(scheduled_at__range=(start, end)).exclude(status="cancelled").count(),
                "today_teacher_absent": sessions.filter(scheduled_at__range=(start, end), status="teacher_absent").count(),
                "to_evaluate": sessions.filter(status="completed", evaluation__isnull=True,
                                               scheduled_at__gte=timezone.now() - dt.timedelta(days=7)).count(),
                "unreviewed_violations": ContactViolation.objects.filter(reviewed=False, user__teacher_profile__supervisor=u).count(),
                "pending_assignment": Subscription.objects.filter(status="pending_assignment").count(),
            },
        }

    def admin(self, request):
        start, end = _today_range()
        month_start = timezone.localdate().replace(day=1)
        paid = Order.objects.filter(status="paid")
        return {
            "users": dict(User.objects.filter(is_active=True).values_list("role").annotate(c=Count("id")).values_list("role", "c")),
            "stats": {
                "pending_teachers": TeacherProfile.objects.filter(approval_status="pending").count(),
                "pending_assignment": Subscription.objects.filter(status="pending_assignment").count(),
                "pending_trials": TrialRequest.objects.filter(status="pending").count(),
                "active_subscriptions": Subscription.objects.filter(status="active").count(),
                "today_sessions": Session.objects.filter(scheduled_at__range=(start, end)).exclude(status="cancelled").count(),
                "live_now": Session.objects.filter(status="live").count(),
                "courses_pending_review": Course.objects.filter(status="pending_review").count(),
                "unreviewed_violations": ContactViolation.objects.filter(reviewed=False).count(),
                "month_revenue": paid.filter(paid_at__date__gte=month_start).aggregate(s=Sum("total"))["s"] or 0,
                "total_revenue": paid.aggregate(s=Sum("total"))["s"] or 0,
            },
            "revenue_by_month": [
                {"month": r["m"].strftime("%Y-%m"), "total": r["s"]}
                for r in paid.filter(paid_at__gte=timezone.now() - dt.timedelta(days=365))
                .annotate(m=TruncMonth("paid_at")).values("m").annotate(s=Sum("total")).order_by("m")
            ],
        }


class TeacherHoursReportView(APIView):
    """تقرير ساعات المدرسين في شهر — للمحاسبة."""
    permission_classes = [IsStaffRole]

    @extend_schema(tags=["Admin - Reports"], summary="تقرير ساعات/حصص المدرسين لشهر (?month=2026-10)",
                   parameters=[OpenApiParameter("month", str)], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        month = request.query_params.get("month") or timezone.localdate().strftime("%Y-%m")
        y, m = map(int, month.split("-"))
        start = dt.date(y, m, 1)
        end = (start + dt.timedelta(days=32)).replace(day=1)
        qs = Session.objects.filter(scheduled_at__date__gte=start, scheduled_at__date__lt=end)
        if request.user.role == Roles.SUPERVISOR:
            qs = qs.filter(teacher__teacher_profile__supervisor=request.user)
        rows = (qs.values("teacher_id", "teacher__full_name").annotate(
            completed=Count("id", filter=Q(status="completed")),
            student_absent=Count("id", filter=Q(status="student_absent")),
            teacher_absent=Count("id", filter=Q(status="teacher_absent")),
            cancelled=Count("id", filter=Q(status="cancelled")),
            paid_minutes=Sum("duration", filter=Q(status__in=["completed", "student_absent"])),
        ).order_by("teacher__full_name"))
        return Response({"month": month, "rows": [
            {**r, "paid_minutes": r["paid_minutes"] or 0, "paid_hours": round((r["paid_minutes"] or 0) / 60, 2)} for r in rows]})
