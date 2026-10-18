import datetime as dt

from django.db import transaction
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsStaffRole, IsTeacher, ReadOnlyOrAdmin, Roles
from apps.notifications.services import notify, notify_staff

from . import serializers as s
from . import services
from .models import (SessionFeedback, Package, RescheduleRequest, Review, Session, SessionEvaluation, SessionReport, Subscription,
                     TeacherAvailability, TrialRequest, WeeklySlot)


def _is_staff(user):
    return user.role in Roles.STAFF or user.is_superuser


# ============================================================ Packages
@extend_schema_view(list=extend_schema(summary="الباقات المتاحة (?subject=ID لباقات مادة معينة + العامة)"))
@extend_schema(tags=["Packages"])
class PackageViewSet(viewsets.ModelViewSet):
    serializer_class = s.PackageSerializer
    permission_classes = [ReadOnlyOrAdmin]
    pagination_class = None

    def get_queryset(self):
        qs = Package.objects.all()
        if getattr(self.request.user, "role", None) != Roles.ADMIN:
            qs = qs.filter(is_active=True)
        subject = self.request.query_params.get("subject")
        if subject:
            from django.db.models import Q
            qs = qs.filter(Q(subject_id=subject) | Q(subject__isnull=True))
        return qs


# ============================================================ Availability
@extend_schema_view(list=extend_schema(summary="مواعيد مدرس المتاحة (?teacher=<user_id>) — للمدرس نفسه بدون فلتر"))
@extend_schema(tags=["Availability"])
class AvailabilityViewSet(viewsets.ModelViewSet):
    serializer_class = s.AvailabilitySerializer
    pagination_class = None

    def get_permissions(self):
        if self.action == "list":
            return [AllowAny()]
        return [IsTeacher()]

    def get_queryset(self):
        teacher = self.request.query_params.get("teacher")
        if teacher:
            return TeacherAvailability.objects.filter(teacher_id=teacher)
        if self.request.user.is_authenticated:
            return TeacherAvailability.objects.filter(teacher=self.request.user)
        return TeacherAvailability.objects.none()

    def perform_create(self, ser):
        ser.save(teacher=self.request.user)

    @extend_schema(summary="استبدال كل المواعيد مرة واحدة", request=s.AvailabilitySerializer(many=True),
                   responses=s.AvailabilitySerializer(many=True))
    @action(detail=False, methods=["put"], url_path="bulk")
    def bulk(self, request):
        ser = s.AvailabilitySerializer(data=request.data, many=True)
        ser.is_valid(raise_exception=True)
        with transaction.atomic():
            TeacherAvailability.objects.filter(teacher=request.user).delete()
            objs = [TeacherAvailability(teacher=request.user, **d) for d in ser.validated_data]
            TeacherAvailability.objects.bulk_create(objs)
        return Response(s.AvailabilitySerializer(TeacherAvailability.objects.filter(teacher=request.user), many=True).data)


# ============================================================ Subscriptions
@extend_schema_view(
    list=extend_schema(summary="الاشتراكات (كل دور يشوف اللي يخصه) — ?status=active&student=&teacher="),
    retrieve=extend_schema(summary="تفاصيل اشتراك"),
)
@extend_schema(tags=["Subscriptions"])
@schema_safe(Subscription)
class SubscriptionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.SubscriptionSerializer
    filterset_fields = ["status", "student", "teacher", "subject"]
    ordering_fields = ["created_at", "end_date"]

    def get_queryset(self):
        return services.subscriptions_visible_to(self.request.user).distinct()

    @extend_schema(summary="طلب اشتراك جديد (طالب) — بيرجع pending_payment وبعدها /payments/checkout/",
                   request=s.SubscriptionCreateSerializer, responses={201: s.SubscriptionSerializer})
    def create(self, request):
        ser = s.SubscriptionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        user = request.user
        if user.role == Roles.STUDENT:
            student = user
        elif _is_staff(user):
            student = get_object_or_404(User, pk=d.get("student_id"), role=Roles.STUDENT)
        else:
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        pkg = d["package"]
        sub = Subscription.objects.create(
            student=student, subject=d["subject"], package=pkg, preferred_teacher=d.get("preferred_teacher"),
            preferred_times=d.get("preferred_times", ""), notes=d.get("notes", ""),
            sessions_total=pkg.sessions_count, session_duration=pkg.session_duration,
        )
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def _staff_obj(self):
        if not _is_staff(self.request.user):
            raise BusinessError("للإدارة فقط.", code="forbidden", status_code=403)
        return self.get_object()

    @extend_schema(summary="(إدارة) تعيين مدرس وجدول أسبوعي وتفعيل الاشتراك وتوليد الحصص",
                   request=s.SubscriptionAssignSerializer, responses=s.SubscriptionSerializer)
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        sub = self._staff_obj()
        ser = s.SubscriptionAssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if sub.status in ("cancelled", "expired"):
            raise BusinessError("الاشتراك منتهي أو ملغي.", code="invalid_status")
        if sub.status == "pending_payment" and d["activate"]:
            raise BusinessError("الاشتراك لسه مدفعش. استخدم mark-paid لو الدفع كاش.", code="not_paid")
        with transaction.atomic():
            # لو بنغيّر المدرس: نلغي الحصص المستقبلية القديمة ونولد جديدة
            sub.sessions.filter(status="scheduled", scheduled_at__gt=timezone.now()).delete()
            sub.teacher = d["teacher"]
            sub.save()
            sub.slots.all().delete()
            WeeklySlot.objects.bulk_create([WeeklySlot(subscription=sub, **x) for x in d["slots"]])
            if d["activate"]:
                if sub.status == "active":
                    services.generate_sessions(sub)
                else:
                    services.activate_subscription(sub, d.get("start_date"))
        sub.refresh_from_db()
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data)

    @extend_schema(summary="(أدمن) تسجيل الاشتراك كمدفوع يدوياً (كاش/تحويل)", request=None, responses=s.SubscriptionSerializer)
    @action(detail=True, methods=["post"], url_path="mark-paid")
    def mark_paid(self, request, pk=None):
        sub = self._staff_obj()
        if sub.status != "pending_payment":
            raise BusinessError("الاشتراك مش في انتظار الدفع.", code="invalid_status")
        services.mark_subscription_paid(sub)
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data)

    @extend_schema(summary="(إدارة) إيقاف مؤقت", request=None, responses=s.SubscriptionSerializer)
    @action(detail=True, methods=["post"])
    def pause(self, request, pk=None):
        sub = self._staff_obj()
        sub.status = "paused"
        sub.save(update_fields=["status"])
        sub.sessions.filter(status="scheduled").delete()
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data)

    @extend_schema(summary="(إدارة) استئناف — بيمد تاريخ الانتهاء ويولد الحصص الباقية", request=None, responses=s.SubscriptionSerializer)
    @action(detail=True, methods=["post"])
    def resume(self, request, pk=None):
        sub = self._staff_obj()
        if sub.status != "paused":
            raise BusinessError("الاشتراك مش متوقف.", code="invalid_status")
        sub.status = "active"
        sub.start_date = timezone.localdate()
        sub.end_date = max(sub.end_date or sub.start_date, timezone.localdate() + dt.timedelta(days=sub.package.duration_days))
        sub.save()
        services.generate_sessions(sub)
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data)

    @extend_schema(summary="(إدارة) إلغاء الاشتراك", request=s.CancelSerializer, responses=s.SubscriptionSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        sub = self._staff_obj()
        sub.status = "cancelled"
        sub.notes = (sub.notes + "\n" + request.data.get("reason", "")).strip()
        sub.save()
        sub.sessions.filter(status="scheduled").update(status="cancelled", cancel_reason="إلغاء الاشتراك", cancelled_by=request.user)
        notify(sub.student, "subscription_cancelled", "تم إلغاء الاشتراك", request.data.get("reason", ""),
               {"screen": "subscription", "id": sub.id})
        return Response(s.SubscriptionSerializer(sub, context={"request": request}).data)

    @extend_schema(summary="تجديد اشتراك منتهي بنفس المدرس والجدول (بيعمل اشتراك جديد pending_payment)",
                   request=None, responses={201: s.SubscriptionSerializer})
    @action(detail=True, methods=["post"])
    def renew(self, request, pk=None):
        old = self.get_object()
        if request.user.id != old.student_id and not _is_staff(request.user):
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        with transaction.atomic():
            new = Subscription.objects.create(
                student=old.student, teacher=old.teacher, preferred_teacher=old.teacher, subject=old.subject,
                package=old.package, sessions_total=old.package.sessions_count,
                session_duration=old.package.session_duration, notes=f"تجديد للاشتراك #{old.id}",
            )
            WeeklySlot.objects.bulk_create([WeeklySlot(subscription=new, weekday=x.weekday, start_time=x.start_time)
                                            for x in old.slots.all()])
        return Response(s.SubscriptionSerializer(new, context={"request": request}).data, status=status.HTTP_201_CREATED)


# ============================================================ Sessions
@extend_schema_view(
    list=extend_schema(
        summary="الحصص (كل دور يشوف اللي يخصه)",
        parameters=[
            OpenApiParameter("from", OpenApiTypes.DATE, description="من تاريخ YYYY-MM-DD"),
            OpenApiParameter("to", OpenApiTypes.DATE, description="إلى تاريخ YYYY-MM-DD"),
            OpenApiParameter("upcoming", OpenApiTypes.BOOL, description="true = القادمة فقط"),
        ],
    ),
    retrieve=extend_schema(summary="تفاصيل حصة + التقرير + تقييم المشرف"),
)
@extend_schema(tags=["Sessions"])
@schema_safe(Session)
class SessionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    filterset_fields = ["status", "subject", "teacher", "student", "subscription", "is_trial"]
    ordering_fields = ["scheduled_at"]

    def get_serializer_class(self):
        return s.SessionDetailSerializer if self.action == "retrieve" else s.SessionSerializer

    def get_queryset(self):
        qs = services.sessions_visible_to(self.request.user).select_related("report")
        p = self.request.query_params
        if p.get("from"):
            qs = qs.filter(scheduled_at__date__gte=parse_date(p["from"]))
        if p.get("to"):
            qs = qs.filter(scheduled_at__date__lte=parse_date(p["to"]))
        if p.get("upcoming") in ("1", "true"):
            qs = qs.filter(status__in=["scheduled", "live"], scheduled_at__gte=timezone.now() - dt.timedelta(hours=3))
        return qs

    @extend_schema(summary="(إدارة) إنشاء حصة يدوية", request=s.SessionCreateSerializer, responses={201: s.SessionSerializer})
    def create(self, request):
        if not _is_staff(request.user):
            raise BusinessError("للإدارة فقط.", code="forbidden", status_code=403)
        ser = s.SessionCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        clash = services.check_conflict(d["teacher"], d["scheduled_at"], d["duration"])
        if clash:
            raise BusinessError(f"المدرس عنده حصة في نفس الوقت (#{clash.id}).", code="teacher_conflict")
        session = Session.objects.create(**d)
        for u in (session.teacher, session.student):
            notify(u, "session_scheduled", "حصة جديدة في جدولك",
                   f"{session.subject} — {timezone.localtime(session.scheduled_at):%Y-%m-%d %H:%M}",
                   {"screen": "session", "id": session.id})
        return Response(s.SessionSerializer(session, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="دخول الحصة — بيرجع بيانات Jitsi (domain, room, jwt, url, config)", request=None,
                   responses={200: OpenApiTypes.OBJECT})
    @action(detail=True, methods=["post"])
    def join(self, request, pk=None):
        return Response(services.join_session(self.get_object(), request.user))

    @extend_schema(summary="إنهاء الحصة (المدرس)", request=None, responses=s.SessionSerializer)
    @action(detail=True, methods=["post"])
    def end(self, request, pk=None):
        return Response(s.SessionSerializer(services.end_session(self.get_object(), request.user), context={"request": request}).data)

    @extend_schema(summary="تقييم الطالب للحصة (بعد ما تخلص)", request=s.SessionFeedbackSerializer,
                   responses=s.SessionFeedbackSerializer)
    @action(detail=True, methods=["post"])
    def feedback(self, request, pk=None):
        sess = self.get_object()
        if request.user.id != sess.student_id:
            raise BusinessError("الطالب بس اللي يقيّم الحصة.", code="forbidden", status_code=403)
        if sess.status != "completed":
            raise BusinessError("تقدر تقيّم الحصة بعد ما تخلص.", code="invalid_status")
        ser = s.SessionFeedbackSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        fb, _ = SessionFeedback.objects.update_or_create(session=sess, defaults={**ser.validated_data, "student": request.user})
        if fb.rating <= 2:
            notify_staff("session_low_rating", "حصة اتقيمت تقييم ضعيف",
                         f"{sess.student.full_name} ← {sess.teacher.full_name}: {fb.rating}/5",
                         {"screen": "session", "id": sess.id})
        return Response(s.SessionFeedbackSerializer(fb).data)

    @extend_schema(summary="إلغاء حصة (قبلها بساعتين وإلا بتتحسب على الطالب)", request=s.CancelSerializer, responses=s.SessionSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        ser = s.CancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sess = services.cancel_session(self.get_object(), request.user, ser.validated_data.get("reason", ""))
        return Response(s.SessionSerializer(sess, context={"request": request}).data)

    @extend_schema(summary="تسجيل غياب (المدرس يسجل غياب الطالب بعد 15 دقيقة)", request=s.AbsentSerializer, responses=s.SessionSerializer)
    @action(detail=True, methods=["post"], url_path="mark-absent")
    def mark_absent(self, request, pk=None):
        ser = s.AbsentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        sess = services.mark_absent(self.get_object(), request.user, ser.validated_data["who"])
        return Response(s.SessionSerializer(sess, context={"request": request}).data)

    @extend_schema(methods=["GET"], summary="تقرير الحصة", responses=s.SessionReportSerializer)
    @extend_schema(methods=["POST", "PUT"], summary="كتابة/تعديل تقرير الحصة (المدرس)", request=s.SessionReportSerializer,
                   responses=s.SessionReportSerializer)
    @action(detail=True, methods=["get", "post", "put"])
    def report(self, request, pk=None):
        session = self.get_object()
        if request.method == "GET":
            rep = get_object_or_404(SessionReport, session=session)
            return Response(s.SessionReportSerializer(rep, context={"request": request}).data)
        if request.user.id != session.teacher_id and not services.can_manage(request.user, session):
            raise BusinessError("المدرس بس اللي يكتب التقرير.", code="forbidden", status_code=403)
        if session.status not in ("completed", "student_absent", "live"):
            raise BusinessError("التقرير بيتكتب بعد الحصة.", code="invalid_status")
        rep = getattr(session, "report", None)
        ser = s.SessionReportSerializer(rep, data=request.data, context={"request": request}, partial=rep is not None)
        ser.is_valid(raise_exception=True)
        rep = ser.save(session=session)
        payload = {"screen": "session", "id": session.id}
        notify(session.student, "session_report", "تقرير الحصة جاهز", rep.topics[:120], payload)
        return Response(s.SessionReportSerializer(rep, context={"request": request}).data)

    @extend_schema(summary="(مشرف) تقييم جودة الحصة", request=s.SessionEvaluationSerializer, responses=s.SessionEvaluationSerializer)
    @action(detail=True, methods=["post"])
    def evaluate(self, request, pk=None):
        session = self.get_object()
        if not services.can_manage(request.user, session):
            raise BusinessError("للمشرف فقط.", code="forbidden", status_code=403)
        ser = s.SessionEvaluationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        ev, _ = SessionEvaluation.objects.update_or_create(
            session=session, defaults={"supervisor": request.user, **ser.validated_data})
        return Response(s.SessionEvaluationSerializer(ev).data)

    @extend_schema(summary="طلب تغيير ميعاد الحصة (الإدارة توافق) — الأدمن بيتنفذ فوراً",
                   request=s.RescheduleRequestSerializer, responses={201: s.RescheduleRequestSerializer})
    @action(detail=True, methods=["post"], url_path="reschedule")
    def reschedule(self, request, pk=None):
        session = self.get_object()
        ser = s.RescheduleRequestSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        if services.can_manage(request.user, session):
            clash = services.check_conflict(session.teacher, ser.validated_data["proposed_time"], session.duration, session.id)
            if clash:
                raise BusinessError(f"المدرس عنده حصة في نفس الوقت (#{clash.id}).", code="teacher_conflict")
            services.reschedule(session, ser.validated_data["proposed_time"])
            req = ser.save(session=session, requested_by=request.user, status="approved", handled_by=request.user)
        else:
            if session.status != "scheduled":
                raise BusinessError("مينفعش تغيّر ميعاد الحصة دي.", code="invalid_status")
            req = ser.save(session=session, requested_by=request.user)
            notify_staff("reschedule_request", "طلب تغيير ميعاد", f"{request.user.full_name} - حصة #{session.id}",
                         {"screen": "reschedule", "id": req.id}, supervisor=session.teacher.teacher_profile.supervisor)
        return Response(s.RescheduleRequestSerializer(req, context={"request": request}).data, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Sessions"])
@schema_safe(RescheduleRequest)
class RescheduleRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    serializer_class = s.RescheduleRequestSerializer
    filterset_fields = ["status"]

    def get_queryset(self):
        u = self.request.user
        qs = RescheduleRequest.objects.select_related("session", "requested_by")
        if _is_staff(u):
            return qs.filter(session__in=services.sessions_visible_to(u))
        return qs.filter(requested_by=u)

    @extend_schema(summary="(إدارة) قبول طلب تغيير الميعاد", request=None, responses=s.RescheduleRequestSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def approve(self, request, pk=None):
        req = self.get_object()
        if req.status != "pending":
            raise BusinessError("الطلب اتعامل معاه قبل كده.", code="invalid_status")
        clash = services.check_conflict(req.session.teacher, req.proposed_time, req.session.duration, req.session_id)
        if clash:
            raise BusinessError(f"المدرس عنده حصة في نفس الوقت (#{clash.id}).", code="teacher_conflict")
        services.reschedule(req.session, req.proposed_time)
        req.status, req.handled_by = "approved", request.user
        req.save()
        return Response(s.RescheduleRequestSerializer(req, context={"request": request}).data)

    @extend_schema(summary="(إدارة) رفض طلب تغيير الميعاد", request=None, responses=s.RescheduleRequestSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def reject(self, request, pk=None):
        req = self.get_object()
        req.status, req.handled_by = "rejected", request.user
        req.save()
        notify(req.requested_by, "reschedule_rejected", "تم رفض طلب تغيير الميعاد", "", {"screen": "session", "id": req.session_id})
        return Response(s.RescheduleRequestSerializer(req, context={"request": request}).data)


# ============================================================ Trials
@extend_schema(tags=["Trials"])
@schema_safe(TrialRequest)
class TrialRequestViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.TrialRequestSerializer
    filterset_fields = ["status", "subject"]

    def get_queryset(self):
        u = self.request.user
        qs = TrialRequest.objects.select_related("student", "subject", "session")
        return qs if _is_staff(u) else qs.filter(student=u)

    @extend_schema(summary="طلب حصة تجريبية مجانية (طالب) — مرة واحدة لكل مادة")
    def create(self, request, *a, **kw):
        if request.user.role != Roles.STUDENT:
            raise BusinessError("للطلاب فقط.", code="forbidden", status_code=403)
        return super().create(request, *a, **kw)

    def perform_create(self, ser):
        if TrialRequest.objects.filter(student=self.request.user, subject=ser.validated_data["subject"]).exclude(status="cancelled").exists():
            raise BusinessError("أخدت حصة تجريبية في المادة دي قبل كده.", code="trial_exists")
        tr = ser.save(student=self.request.user)
        notify_staff("trial_request", "طلب حصة تجريبية", f"{tr.student.full_name} - {tr.subject}", {"screen": "trial", "id": tr.id})

    @extend_schema(summary="(إدارة) تحديد مدرس وميعاد للحصة التجريبية", request=s.TrialScheduleSerializer,
                   responses=s.TrialRequestSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def schedule(self, request, pk=None):
        tr = self.get_object()
        ser = s.TrialScheduleSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        clash = services.check_conflict(d["teacher"], d["scheduled_at"], d["duration"])
        if clash:
            raise BusinessError(f"المدرس عنده حصة في نفس الوقت (#{clash.id}).", code="teacher_conflict")
        sess = Session.objects.create(teacher=d["teacher"], student=tr.student, subject=tr.subject, is_trial=True,
                                      scheduled_at=d["scheduled_at"], duration=d["duration"], title="حصة تجريبية")
        tr.session, tr.status = sess, "scheduled"
        tr.save()
        for u in (sess.teacher, sess.student):
            notify(u, "session_scheduled", "حصة تجريبية في جدولك",
                   f"{tr.subject} — {timezone.localtime(sess.scheduled_at):%Y-%m-%d %H:%M}", {"screen": "session", "id": sess.id})
        return Response(s.TrialRequestSerializer(tr, context={"request": request}).data)


# ============================================================ Reviews
@extend_schema_view(list=extend_schema(summary="تقييمات مدرس (?teacher=<user_id>)"))
@extend_schema(tags=["Reviews"])
class ReviewViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = s.ReviewSerializer
    filterset_fields = ["teacher", "rating"]

    def get_permissions(self):
        return [AllowAny()] if self.action == "list" else [IsAuthenticated()]

    def get_queryset(self):
        qs = Review.objects.select_related("student")
        if not (self.request.user.is_authenticated and _is_staff(self.request.user)):
            qs = qs.filter(is_visible=True)
        return qs

    @extend_schema(summary="تقييم المدرس (لازم يكون عندك حصة مكتملة معاه) — بيحدّث التقييم القديم لو موجود")
    def create(self, request, *a, **kw):
        if request.user.role != Roles.STUDENT:
            raise BusinessError("للطلاب فقط.", code="forbidden", status_code=403)
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        teacher = ser.validated_data["teacher"]
        if not Session.objects.filter(teacher=teacher, student=request.user, status="completed").exists():
            raise BusinessError("لازم تحضر حصة مع المدرس الأول.", code="no_completed_session")
        review, _ = Review.objects.update_or_create(
            teacher=teacher, student=request.user,
            defaults={"rating": ser.validated_data["rating"], "comment": ser.validated_data.get("comment", "")})
        services.refresh_teacher_rating(teacher)
        return Response(s.ReviewSerializer(review).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="(إدارة) إخفاء/إظهار تقييم", request=None, responses=s.ReviewSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole], url_path="toggle-visibility")
    def toggle_visibility(self, request, pk=None):
        r = get_object_or_404(Review, pk=pk)
        r.is_visible = not r.is_visible
        r.save(update_fields=["is_visible"])
        services.refresh_teacher_rating(r.teacher)
        return Response(s.ReviewSerializer(r).data)


# ============================================================ Teacher: my students
@extend_schema(tags=["Teacher"])
class TeacherStudentsView(APIView):
    permission_classes = [IsTeacher]

    @extend_schema(summary="طلابي (المدرس) مع اشتراكاتهم", responses=s.TeacherStudentSerializer(many=True))
    def get(self, request):
        subs = (Subscription.objects.filter(teacher=request.user, status__in=["active", "paused"])
                .select_related("student", "subject", "package").prefetch_related("slots"))
        grouped = {}
        for sub in subs:
            grouped.setdefault(sub.student_id, {"student": sub.student, "subscriptions": []})["subscriptions"].append(sub)
        return Response(s.TeacherStudentSerializer(list(grouped.values()), many=True, context={"request": request}).data)
