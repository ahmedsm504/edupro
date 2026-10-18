from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics, mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsAdmin, IsStaffRole, IsTeacher, Roles

from . import serializers as s
from .models import OTPCode, StudentProfile, TeacherDocument, TeacherProfile, User
from .utils import normalize_phone, send_sms


class AuthThrottle(ScopedRateThrottle):
    scope_attr = "throttle_scope"


# =========================== Auth ===========================
@extend_schema(tags=["Auth"])
class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="تسجيل حساب جديد (طالب أو مدرس)", request=s.RegisterSerializer,
                   responses={201: s.AuthResponseSerializer})
    def post(self, request):
        ser = s.RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        if user.role == Roles.TEACHER:
            from apps.notifications.services import notify_staff
            notify_staff("teacher_application", "طلب انضمام مدرس جديد", user.full_name, {"user_id": user.id}, admins_only=True)
        return Response({**s.tokens_for(user), "user": s.UserSerializer(user, context={"request": request}).data},
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=["Auth"])
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="تسجيل الدخول بالموبايل أو الإيميل", request=s.LoginSerializer,
                   responses={200: s.AuthResponseSerializer})
    def post(self, request):
        ser = s.LoginSerializer(data=request.data, context={"request": request})
        ser.is_valid(raise_exception=True)
        user = ser.validated_data["user"]
        from django.contrib.auth.models import update_last_login
        update_last_login(None, user)
        return Response({**s.tokens_for(user), "user": s.UserSerializer(user, context={"request": request}).data})


@extend_schema(tags=["Auth"])
class LogoutView(APIView):
    @extend_schema(summary="تسجيل الخروج (إلغاء الـ refresh token)", request=s.LogoutSerializer, responses={204: None})
    def post(self, request):
        ser = s.LogoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        try:
            RefreshToken(ser.validated_data["refresh"]).blacklist()
        except TokenError:
            pass
        device_token = request.data.get("fcm_token")
        if device_token:
            from apps.notifications.models import Device
            Device.objects.filter(user=request.user, token=device_token).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Auth"])
class OTPSendView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "otp"
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="إرسال كود OTP (تأكيد الموبايل / نسيت كلمة السر)", request=s.OTPSendSerializer,
                   responses=s.DetailSerializer)
    def post(self, request):
        ser = s.OTPSendSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = normalize_phone(ser.validated_data["phone"])
        purpose = ser.validated_data["purpose"]
        if User.objects.filter(phone=phone).exists():
            _, code = OTPCode.issue(phone, purpose)
            send_sms(phone, f"كود التحقق: {code}")
        # نفس الرد دايماً عشان محدش يعرف الأرقام المسجلة
        return Response({"detail": "لو الرقم مسجل هيوصلك كود خلال دقيقة."})


@extend_schema(tags=["Auth"])
class VerifyPhoneView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="تأكيد رقم الموبايل بالكود", request=s.OTPVerifySerializer, responses=s.DetailSerializer)
    def post(self, request):
        ser = s.OTPVerifySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = normalize_phone(ser.validated_data["phone"])
        otp = OTPCode.objects.filter(phone=phone, purpose="verify_phone", used=False).order_by("-created_at").first()
        if not otp or not otp.verify(ser.validated_data["code"]):
            raise BusinessError("الكود غير صحيح أو منتهي.", code="invalid_otp")
        User.objects.filter(phone=phone).update(is_phone_verified=True)
        return Response({"detail": "تم تأكيد رقم الموبايل."})


@extend_schema(tags=["Auth"])
class PasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_scope = "auth"
    throttle_classes = [AuthThrottle]

    @extend_schema(summary="تعيين كلمة سر جديدة بالكود", request=s.PasswordResetSerializer, responses=s.DetailSerializer)
    def post(self, request):
        ser = s.PasswordResetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        phone = normalize_phone(ser.validated_data["phone"])
        otp = OTPCode.objects.filter(phone=phone, purpose="reset_password", used=False).order_by("-created_at").first()
        if not otp or not otp.verify(ser.validated_data["code"]):
            raise BusinessError("الكود غير صحيح أو منتهي.", code="invalid_otp")
        user = User.objects.get(phone=phone)
        user.set_password(ser.validated_data["new_password"])
        user.is_phone_verified = True
        user.save()
        return Response({"detail": "تم تغيير كلمة السر، سجّل دخول من جديد."})


@extend_schema(tags=["Auth"])
class PasswordChangeView(APIView):
    @extend_schema(summary="تغيير كلمة السر", request=s.PasswordChangeSerializer, responses=s.DetailSerializer)
    def post(self, request):
        ser = s.PasswordChangeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if not request.user.check_password(ser.validated_data["old_password"]):
            raise BusinessError("كلمة السر الحالية غير صحيحة.", code="wrong_password")
        request.user.set_password(ser.validated_data["new_password"])
        request.user.save()
        return Response({"detail": "تم تغيير كلمة السر."})


# =========================== Me ===========================
@extend_schema(tags=["Me"])
class MeView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = s.UserSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    http_method_names = ["get", "patch", "delete"]

    def get_object(self):
        return self.request.user

    @extend_schema(summary="بيانات المستخدم الحالي + بروفايله حسب الدور")
    def get(self, request, *a, **kw):
        return super().get(request, *a, **kw)

    @extend_schema(summary="تعديل البيانات الأساسية (الاسم، الصورة multipart، الإيميل...)")
    def patch(self, request, *a, **kw):
        return super().patch(request, *a, **kw)

    @extend_schema(summary="حذف الحساب (مطلوب من App Store / Google Play)")
    def delete(self, request, *a, **kw):
        u = request.user
        u.is_active = False
        u.phone = f"deleted_{u.id}_{u.phone}"[:20]
        u.username = u.phone
        u.email = None
        u.full_name = "مستخدم محذوف"
        u.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Me"])
class MyTeacherProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = s.TeacherProfileSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        if self.request.user.role != Roles.TEACHER:
            raise BusinessError("الحساب ليس حساب مدرس.", code="not_teacher", status_code=403)
        return self.request.user.teacher_profile


@extend_schema(tags=["Me"])
class MyStudentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = s.StudentProfileSerializer
    http_method_names = ["get", "patch"]

    def get_object(self):
        if self.request.user.role != Roles.STUDENT:
            raise BusinessError("الحساب ليس حساب طالب.", code="not_student", status_code=403)
        return self.request.user.student_profile


@extend_schema(tags=["Me"])
@schema_safe(TeacherDocument)
class MyTeacherDocumentsView(generics.ListCreateAPIView):
    """رفع مستندات طلب الانضمام (multipart: title, file)"""
    serializer_class = s.TeacherDocumentSerializer
    parser_classes = [parsers.MultiPartParser, parsers.FormParser]
    pagination_class = None

    def get_queryset(self):
        return TeacherDocument.objects.filter(teacher__user=self.request.user)

    def perform_create(self, ser):
        if self.request.user.role != Roles.TEACHER:
            raise BusinessError("الحساب ليس حساب مدرس.", code="not_teacher", status_code=403)
        ser.save(teacher=self.request.user.teacher_profile)


# =========================== Public teachers ===========================
@extend_schema_view(
    list=extend_schema(summary="قائمة المدرسين المعتمدين",
                       description="فلاتر: ?subjects=<id>&grades=<id>&user__gender=female&is_featured=true&search=...&ordering=-rating_avg"),
    retrieve=extend_schema(summary="بروفايل مدرس عام (بالـ slug)"),
)
@extend_schema(tags=["Teachers"])
class PublicTeacherViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_fields = ["subjects", "grades", "user__gender", "is_featured", "accepts_new_students", "subjects__slug"]
    search_fields = ["user__full_name", "headline", "subjects__name"]
    ordering_fields = ["rating_avg", "experience_years", "hourly_rate", "created_at"]
    ordering = ["-is_featured", "-rating_avg"]

    def get_queryset(self):
        return (TeacherProfile.objects.filter(approval_status="approved", user__is_active=True)
                .select_related("user").prefetch_related("subjects", "grades").distinct())

    def get_serializer_class(self):
        return s.PublicTeacherDetailSerializer if self.action == "retrieve" else s.PublicTeacherSerializer


# =========================== Admin ===========================
@extend_schema_view(list=extend_schema(summary="كل المستخدمين (?role=teacher&is_active=true&search=)"))
@extend_schema(tags=["Admin - Users"])
@schema_safe(User)
class AdminUserViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRole]
    filterset_fields = ["role", "is_active", "is_phone_verified", "teacher_profile__approval_status"]
    search_fields = ["full_name", "phone", "email"]
    ordering_fields = ["date_joined", "last_login", "full_name"]
    ordering = ["-date_joined"]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "teacher_review"):
            return [IsAdmin()]
        return super().get_permissions()

    def get_queryset(self):
        qs = User.objects.all().select_related("teacher_profile", "student_profile")
        if self.request.user.role == Roles.SUPERVISOR:
            qs = qs.filter(Q(teacher_profile__supervisor=self.request.user) | Q(role=Roles.STUDENT))
        return qs

    def get_serializer_class(self):
        return s.AdminCreateUserSerializer if self.action == "create" else s.AdminUserSerializer

    def perform_destroy(self, instance):
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    @extend_schema(summary="اعتماد/رفض/إيقاف مدرس + تعيين مشرف", request=s.TeacherReviewActionSerializer,
                   responses={200: s.AdminUserSerializer})
    @action(detail=True, methods=["post"], url_path="teacher-review")
    def teacher_review(self, request, pk=None):
        user = self.get_object()
        tp = get_object_or_404(TeacherProfile, user=user)
        ser = s.TeacherReviewActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        act = ser.validated_data["action"]
        tp.approval_status = {"approve": "approved", "reject": "rejected", "suspend": "suspended"}[act]
        tp.rejection_reason = ser.validated_data.get("reason", "")
        if "supervisor" in ser.validated_data:
            tp.supervisor = ser.validated_data["supervisor"]
        tp.save()
        from apps.notifications.services import notify
        msgs = {"approve": "تم اعتماد حسابك كمدرس 🎉", "reject": "تم رفض طلب الانضمام", "suspend": "تم إيقاف حسابك مؤقتاً"}
        notify(user, "teacher_status", msgs[act], tp.rejection_reason or "", {"status": tp.approval_status})
        return Response(s.AdminUserSerializer(user, context={"request": request}).data)
