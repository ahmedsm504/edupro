from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.catalog.models import Grade, Subject
from apps.catalog.serializers import SubjectMiniSerializer
from apps.core.permissions import Roles

from .models import StudentProfile, TeacherDocument, TeacherProfile, User
from .utils import normalize_phone


def tokens_for(user):
    refresh = RefreshToken.for_user(user)
    refresh["role"] = user.role
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class UserMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "full_name", "avatar", "role"]


class TeacherProfileSerializer(serializers.ModelSerializer):
    subjects = SubjectMiniSerializer(many=True, read_only=True)
    subject_ids = serializers.PrimaryKeyRelatedField(
        source="subjects", many=True, queryset=Subject.objects.filter(is_active=True), write_only=True, required=False
    )
    grade_ids = serializers.PrimaryKeyRelatedField(
        source="grades", many=True, queryset=Grade.objects.all(), write_only=True, required=False
    )

    class Meta:
        model = TeacherProfile
        fields = [
            "id", "slug", "headline", "bio", "subjects", "subject_ids", "grades", "grade_ids",
            "experience_years", "qualifications", "intro_video_url", "hourly_rate", "teaches_gender",
            "approval_status", "rejection_reason", "rating_avg", "rating_count", "accepts_new_students",
        ]
        read_only_fields = ["slug", "grades", "approval_status", "rejection_reason", "rating_avg", "rating_count"]


class StudentProfileSerializer(serializers.ModelSerializer):
    grade_name = serializers.CharField(source="grade.__str__", read_only=True, default=None)

    class Meta:
        model = StudentProfile
        fields = ["id", "grade", "grade_name", "school", "birth_date"]


class UserSerializer(serializers.ModelSerializer):
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "username", "full_name", "phone", "email", "role", "avatar", "gender", "country", "timezone",
            "language", "is_phone_verified", "date_joined", "profile",
        ]
        read_only_fields = ["username", "phone", "role", "is_phone_verified", "date_joined"]

    @extend_schema_field(serializers.DictField())
    def get_profile(self, obj):
        if obj.role == Roles.TEACHER and hasattr(obj, "teacher_profile"):
            return TeacherProfileSerializer(obj.teacher_profile, context=self.context).data
        if obj.role == Roles.STUDENT and hasattr(obj, "student_profile"):
            return StudentProfileSerializer(obj.student_profile, context=self.context).data
        return None


class RegisterSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=20)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=[Roles.STUDENT, Roles.TEACHER])
    gender = serializers.ChoiceField(choices=User.GENDER_CHOICES, required=False, allow_blank=True)
    country = serializers.CharField(required=False, default="EG")
    timezone = serializers.CharField(required=False, default="Africa/Cairo")
    # طالب
    grade = serializers.PrimaryKeyRelatedField(queryset=Grade.objects.all(), required=False, allow_null=True)
    # مدرس
    subject_ids = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True), many=True, required=False)
    headline = serializers.CharField(required=False, allow_blank=True)
    bio = serializers.CharField(required=False, allow_blank=True)
    experience_years = serializers.IntegerField(required=False, min_value=0)

    def validate_phone(self, v):
        v = normalize_phone(v)
        if len(v) < 8:
            raise serializers.ValidationError("رقم الموبايل غير صحيح.")
        if User.objects.filter(phone=v).exists():
            raise serializers.ValidationError("رقم الموبايل مسجل بالفعل.")
        return v

    def validate_email(self, v):
        if v and User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError("البريد الإلكتروني مسجل بالفعل.")
        return v or None

    def validate_password(self, v):
        validate_password(v)
        return v

    def validate(self, attrs):
        if attrs["role"] == Roles.TEACHER and not attrs.get("subject_ids"):
            raise serializers.ValidationError({"subject_ids": "اختر مادة واحدة على الأقل."})
        return attrs

    @transaction.atomic
    def create(self, data):
        role = data["role"]
        user = User.objects.create_user(
            phone=data["phone"], password=data["password"], full_name=data["full_name"],
            email=data.get("email"), role=role, gender=data.get("gender", ""),
            country=data.get("country", "EG"), timezone=data.get("timezone", "Africa/Cairo"),
        )
        if role == Roles.STUDENT:
            StudentProfile.objects.create(user=user, grade=data.get("grade"))
        elif role == Roles.TEACHER:
            tp = TeacherProfile.objects.create(
                user=user, headline=data.get("headline", ""), bio=data.get("bio", ""),
                experience_years=data.get("experience_years", 0),
            )
            tp.subjects.set(data.get("subject_ids", []))
        return user


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(help_text="اسم المستخدم أو رقم الموبايل أو الإيميل")
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(self.context.get("request"), username=attrs["identifier"], password=attrs["password"])
        if not user:
            raise serializers.ValidationError("بيانات الدخول غير صحيحة.", code="invalid_credentials")
        attrs["user"] = user
        return attrs


class AuthResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserSerializer()


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class OTPSendSerializer(serializers.Serializer):
    phone = serializers.CharField()
    purpose = serializers.ChoiceField(choices=["verify_phone", "reset_password"])


class OTPVerifySerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)


class PasswordResetSerializer(serializers.Serializer):
    phone = serializers.CharField()
    code = serializers.CharField(max_length=6)
    new_password = serializers.CharField()

    def validate_new_password(self, v):
        validate_password(v)
        return v


class PasswordChangeSerializer(serializers.Serializer):
    old_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate_new_password(self, v):
        validate_password(v)
        return v


class TeacherDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherDocument
        fields = ["id", "title", "file", "created_at"]


# ---------- Public teacher listing ----------
class PublicTeacherSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="user.full_name")
    avatar = serializers.ImageField(source="user.avatar")
    gender = serializers.CharField(source="user.gender")
    country = serializers.CharField(source="user.country")
    user_id = serializers.IntegerField(source="user.id")
    subjects = SubjectMiniSerializer(many=True)

    class Meta:
        model = TeacherProfile
        fields = [
            "id", "user_id", "slug", "full_name", "avatar", "gender", "country", "headline", "subjects",
            "experience_years", "hourly_rate", "rating_avg", "rating_count", "is_featured", "accepts_new_students",
        ]


class PublicTeacherDetailSerializer(PublicTeacherSerializer):
    class Meta(PublicTeacherSerializer.Meta):
        fields = PublicTeacherSerializer.Meta.fields + ["bio", "qualifications", "intro_video_url", "grades", "teaches_gender"]


# ---------- Admin ----------
class AdminUserSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + ["is_active", "last_login"]
        read_only_fields = ["date_joined", "last_login"]


class AdminCreateUserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "full_name", "phone", "email", "role", "password", "gender"]

    def validate_phone(self, v):
        v = normalize_phone(v)
        if User.objects.filter(phone=v).exists():
            raise serializers.ValidationError("رقم الموبايل مسجل بالفعل.")
        return v

    def create(self, data):
        pwd = data.pop("password")
        user = User.objects.create_user(password=pwd, **data)
        if user.role == Roles.STUDENT:
            StudentProfile.objects.create(user=user)
        elif user.role == Roles.TEACHER:
            TeacherProfile.objects.create(user=user, approval_status="approved")
        return user


class TeacherReviewActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "suspend"])
    reason = serializers.CharField(required=False, allow_blank=True)
    supervisor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=Roles.SUPERVISOR), required=False, allow_null=True
    )


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()
