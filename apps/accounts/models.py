import random
import secrets
import string

from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, unique_slug
from apps.core.permissions import Roles


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create(self, phone, password, **extra):
        if not phone:
            raise ValueError("phone is required")
        extra.setdefault("username", phone)
        email = extra.pop("email", "") or ""
        user = self.model(phone=phone, email=self.normalize_email(email) if email else None, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create(phone, password, **extra)

    def create_superuser(self, phone, password=None, **extra):
        extra.update(is_staff=True, is_superuser=True, role=Roles.ADMIN)
        return self._create(phone, password, **extra)


class User(AbstractUser):
    """المستخدم الموحد لكل الأدوار. الدخول بالموبايل أو الإيميل."""
    GENDER_CHOICES = [("male", "ذكر"), ("female", "أنثى")]

    first_name = None
    last_name = None
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Roles.CHOICES, default=Roles.STUDENT, db_index=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    country = models.CharField(max_length=60, blank=True, default="EG")
    timezone = models.CharField(max_length=50, default="Africa/Cairo")
    language = models.CharField(max_length=5, default="ar")
    is_phone_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["full_name"]
    objects = UserManager()

    def save(self, *a, **kw):
        if not self.username:
            self.username = self.phone
        super().save(*a, **kw)

    def __str__(self):
        return f"{self.full_name} ({self.get_role_display()})"

    @property
    def is_platform_staff(self):
        return self.role in Roles.STAFF or self.is_superuser


class TeacherProfile(TimeStampedModel):
    STATUS = [("pending", "قيد المراجعة"), ("approved", "معتمد"), ("rejected", "مرفوض"), ("suspended", "موقوف")]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="teacher_profile")
    slug = models.SlugField(max_length=180, unique=True, allow_unicode=True, blank=True)
    headline = models.CharField(max_length=200, blank=True, help_text="مثال: مدرس فيزياء للثانوية العامة")
    bio = models.TextField(blank=True)
    subjects = models.ManyToManyField("catalog.Subject", related_name="teachers", blank=True)
    grades = models.ManyToManyField("catalog.Grade", related_name="teachers", blank=True)
    experience_years = models.PositiveIntegerField(default=0)
    qualifications = models.TextField(blank=True)
    intro_video_url = models.URLField(blank=True)
    hourly_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="سعر الساعة (للعرض)")
    teaches_gender = models.CharField(max_length=10, choices=[("all", "الكل"), ("male", "ذكور"), ("female", "إناث")], default="all")
    approval_status = models.CharField(max_length=20, choices=STATUS, default="pending", db_index=True)
    rejection_reason = models.TextField(blank=True)
    supervisor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="supervised_teachers",
        limit_choices_to={"role": Roles.SUPERVISOR},
    )
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    rating_count = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False)
    accepts_new_students = models.BooleanField(default=True)

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.user.full_name)
        super().save(*a, **kw)

    @property
    def is_approved(self):
        return self.approval_status == "approved"

    def get_absolute_url(self):
        return f"/teachers/{self.slug}/"

    def __str__(self):
        return self.user.full_name


class TeacherDocument(TimeStampedModel):
    """مستندات طلب الانضمام (CV، شهادات...)."""
    teacher = models.ForeignKey(TeacherProfile, on_delete=models.CASCADE, related_name="documents")
    title = models.CharField(max_length=120)
    file = models.FileField(upload_to="teachers/docs/")


def _parent_code():
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=8))


class StudentProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="student_profile")
    grade = models.ForeignKey("catalog.Grade", null=True, blank=True, on_delete=models.SET_NULL)
    school = models.CharField(max_length=150, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="ملاحظات الإدارة")

    def __str__(self):
        return self.user.full_name


class OTPCode(TimeStampedModel):
    PURPOSES = [("verify_phone", "تأكيد الموبايل"), ("reset_password", "استرجاع كلمة السر")]
    phone = models.CharField(max_length=20, db_index=True)
    purpose = models.CharField(max_length=20, choices=PURPOSES)
    code_hash = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    @classmethod
    def issue(cls, phone, purpose):
        from django.contrib.auth.hashers import make_password
        code = f"{secrets.randbelow(10**6):06d}"
        cls.objects.filter(phone=phone, purpose=purpose, used=False).update(used=True)
        obj = cls.objects.create(
            phone=phone, purpose=purpose, code_hash=make_password(code),
            expires_at=timezone.now() + timezone.timedelta(minutes=settings.OTP_TTL_MINUTES),
        )
        return obj, code

    def verify(self, code):
        from django.contrib.auth.hashers import check_password
        if self.used or self.expires_at < timezone.now() or self.attempts >= 5:
            return False
        self.attempts += 1
        ok = check_password(code, self.code_hash)
        if ok:
            self.used = True
        self.save(update_fields=["attempts", "used"])
        return ok
