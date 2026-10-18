from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserMiniSerializer
from apps.catalog.models import Subject
from apps.catalog.serializers import SubjectMiniSerializer
from apps.core.permissions import Roles

from .models import (SessionFeedback, Package, RescheduleRequest, Review, Session, SessionEvaluation, SessionReport, Subscription,
                     TeacherAvailability, TrialRequest, WeeklySlot)


class PackageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Package
        fields = ["id", "name", "description", "subject", "sessions_count", "session_duration", "duration_days",
                  "price", "old_price", "currency", "is_trial", "is_featured", "is_active", "order"]


class AvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherAvailability
        fields = ["id", "teacher", "weekday", "start_time", "end_time"]
        read_only_fields = ["teacher"]

    def validate(self, a):
        if a["start_time"] >= a["end_time"]:
            raise serializers.ValidationError("وقت البداية لازم يكون قبل النهاية.")
        return a


class WeeklySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = WeeklySlot
        fields = ["weekday", "start_time"]


class SubscriptionSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    teacher = UserMiniSerializer(read_only=True)
    subject = SubjectMiniSerializer(read_only=True)
    package = PackageSerializer(read_only=True)
    slots = WeeklySlotSerializer(many=True, read_only=True)
    sessions_remaining = serializers.IntegerField(read_only=True)
    next_session = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = ["id", "student", "teacher", "preferred_teacher", "subject", "package", "status", "sessions_total", "sessions_used",
                  "sessions_remaining", "session_duration", "start_date", "end_date", "price_paid", "slots",
                  "preferred_times", "notes", "next_session", "created_at"]

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_next_session(self, obj):
        s = obj.sessions.filter(status="scheduled", scheduled_at__gte=timezone.now()).order_by("scheduled_at").first()
        return s.scheduled_at if s else None


class SubscriptionCreateSerializer(serializers.Serializer):
    """الطالب يطلب اشتراك جديد (أو الإدارة نيابة عنه)."""
    package = serializers.PrimaryKeyRelatedField(queryset=Package.objects.filter(is_active=True))
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True))
    preferred_teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Roles.TEACHER, teacher_profile__approval_status="approved"),
        required=False, allow_null=True, help_text="user id للمدرس")
    preferred_times = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    student_id = serializers.IntegerField(required=False, help_text="للإدارة: id الطالب")

    def validate(self, a):
        pkg = a["package"]
        if pkg.subject_id and pkg.subject_id != a["subject"].id:
            raise serializers.ValidationError({"package": "الباقة دي مش للمادة المختارة."})
        t = a.get("preferred_teacher")
        if t and not t.teacher_profile.subjects.filter(pk=a["subject"].id).exists():
            raise serializers.ValidationError({"preferred_teacher": "المدرس ده مش بيدرّس المادة دي."})
        return a


class SubscriptionAssignSerializer(serializers.Serializer):
    """الإدارة/المشرف: تعيين المدرس والجدول وتفعيل الاشتراك."""
    teacher = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Roles.TEACHER, teacher_profile__approval_status="approved"))
    slots = WeeklySlotSerializer(many=True)
    start_date = serializers.DateField(required=False)
    activate = serializers.BooleanField(default=True, help_text="false = حفظ المدرس والجدول من غير تفعيل")

    def validate_slots(self, v):
        if not v:
            raise serializers.ValidationError("حدد ميعاد واحد على الأقل.")
        return v


class SessionReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionReport
        fields = ["attendance", "topics", "homework", "performance", "behavior", "notes_for_student",
                  "private_notes", "created_at", "updated_at"]

    def to_representation(self, inst):
        data = super().to_representation(inst)
        user = self.context["request"].user
        if user.role == Roles.STUDENT:
            data.pop("private_notes", None)
        return data


class SessionEvaluationSerializer(serializers.ModelSerializer):
    supervisor = UserMiniSerializer(read_only=True)

    class Meta:
        model = SessionEvaluation
        fields = ["score", "notes", "supervisor", "created_at"]


class SessionSerializer(serializers.ModelSerializer):
    teacher = UserMiniSerializer(read_only=True)
    student = UserMiniSerializer(read_only=True)
    subject = SubjectMiniSerializer(read_only=True)
    ends_at = serializers.DateTimeField(read_only=True)
    has_report = serializers.SerializerMethodField()
    can_join = serializers.SerializerMethodField()

    class Meta:
        model = Session
        fields = ["id", "subscription", "teacher", "student", "subject", "title", "scheduled_at", "ends_at",
                  "duration", "status", "is_trial", "started_at", "ended_at", "teacher_joined_at",
                  "student_joined_at", "cancel_reason", "counted", "recording_url", "has_report", "can_join"]

    def get_has_report(self, obj) -> bool:
        return hasattr(obj, "report")

    def get_can_join(self, obj) -> bool:
        from django.conf import settings
        import datetime as dt
        now = timezone.now()
        return obj.status in ("scheduled", "live") and \
            obj.scheduled_at - dt.timedelta(minutes=settings.SESSION_JOIN_EARLY_MINUTES) <= now <= obj.ends_at + dt.timedelta(minutes=30)


class SessionFeedbackSerializer(serializers.ModelSerializer):
    issues = serializers.ListField(child=serializers.ChoiceField(choices=[k for k, _ in SessionFeedback.ISSUES]),
                                   required=False, default=list)

    class Meta:
        model = SessionFeedback
        fields = ["rating", "issues", "comment", "created_at"]


class SessionDetailSerializer(SessionSerializer):
    """
    تفاصيل الحصة + اللي تحتاجه شاشة غرفة الحصة:
    join_opens_at (من إمتى زرار الدخول يشتغل)، server_time (عشان العداد يبقى مظبوط حتى لو ساعة الجهاز غلط)،
    previous_homework (الواجب من آخر حصة)، feedback (تقييم الطالب للحصة).
    """
    report = serializers.SerializerMethodField()
    evaluation = serializers.SerializerMethodField()
    join_opens_at = serializers.SerializerMethodField()
    server_time = serializers.SerializerMethodField()
    previous_homework = serializers.SerializerMethodField()
    feedback = serializers.SerializerMethodField()

    class Meta(SessionSerializer.Meta):
        fields = SessionSerializer.Meta.fields + ["report", "evaluation", "join_opens_at", "server_time",
                                                  "previous_homework", "feedback"]

    def get_join_opens_at(self, obj) -> str:
        import datetime as dt
        from django.conf import settings
        return (obj.scheduled_at - dt.timedelta(minutes=settings.SESSION_JOIN_EARLY_MINUTES)).isoformat()

    def get_server_time(self, obj) -> str:
        return timezone.now().isoformat()

    def get_previous_homework(self, obj) -> dict | None:
        prev = (SessionReport.objects.filter(session__teacher_id=obj.teacher_id, session__student_id=obj.student_id,
                                             session__scheduled_at__lt=obj.scheduled_at)
                .exclude(homework="").order_by("-session__scheduled_at").select_related("session").first())
        return {"session_id": prev.session_id, "date": prev.session.scheduled_at.isoformat(), "homework": prev.homework} if prev else None

    @extend_schema_field(SessionFeedbackSerializer(allow_null=True))
    def get_feedback(self, obj):
        return SessionFeedbackSerializer(obj.feedback).data if hasattr(obj, "feedback") else None

    @extend_schema_field(SessionReportSerializer(allow_null=True))
    def get_report(self, obj):
        return SessionReportSerializer(obj.report, context=self.context).data if hasattr(obj, "report") else None

    @extend_schema_field(SessionEvaluationSerializer(allow_null=True))
    def get_evaluation(self, obj):
        if self.context["request"].user.role == Roles.STUDENT:
            return None
        return SessionEvaluationSerializer(obj.evaluation).data if hasattr(obj, "evaluation") else None


class SessionCreateSerializer(serializers.Serializer):
    """إنشاء حصة يدوياً (إدارة/مشرف) — حصة إضافية أو تعويضية أو تجريبية."""
    teacher = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=Roles.TEACHER))
    student = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=Roles.STUDENT))
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())
    scheduled_at = serializers.DateTimeField()
    duration = serializers.IntegerField(default=60, min_value=15, max_value=240)
    title = serializers.CharField(required=False, allow_blank=True)
    subscription = serializers.PrimaryKeyRelatedField(queryset=Subscription.objects.all(), required=False, allow_null=True)
    is_trial = serializers.BooleanField(default=False)


class CancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class AbsentSerializer(serializers.Serializer):
    who = serializers.ChoiceField(choices=["student", "teacher"])


class RescheduleRequestSerializer(serializers.ModelSerializer):
    requested_by = UserMiniSerializer(read_only=True)
    session_info = SessionSerializer(source="session", read_only=True)

    class Meta:
        model = RescheduleRequest
        fields = ["id", "session", "session_info", "requested_by", "proposed_time", "reason", "status", "created_at"]
        read_only_fields = ["session", "status"]

    def validate_proposed_time(self, v):
        if v <= timezone.now():
            raise serializers.ValidationError("الميعاد لازم يكون في المستقبل.")
        return v


class TrialRequestSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)
    subject_info = SubjectMiniSerializer(source="subject", read_only=True)
    session = SessionSerializer(read_only=True)

    class Meta:
        model = TrialRequest
        fields = ["id", "student", "subject", "subject_info", "preferred_teacher", "preferred_times", "notes",
                  "status", "session", "created_at"]
        read_only_fields = ["status"]


class TrialScheduleSerializer(serializers.Serializer):
    teacher = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=Roles.TEACHER))
    scheduled_at = serializers.DateTimeField()
    duration = serializers.IntegerField(default=30)


class ReviewSerializer(serializers.ModelSerializer):
    student = UserMiniSerializer(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "teacher", "student", "rating", "comment", "is_visible", "created_at"]
        read_only_fields = ["is_visible"]


class TeacherStudentSerializer(serializers.Serializer):
    """طالب كما يظهر في "طلابي" عند المدرس."""
    student = UserMiniSerializer()
    subscriptions = SubscriptionSerializer(many=True)
