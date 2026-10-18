"""
EduPro — منصة تعليمية لكل المواد (API-first لتطبيق Flutter + موقع).
كل الإعدادات الحساسة بتتقرا من متغيرات البيئة (.env) — شوف .env.example
"""
import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv():
    env_file = BASE_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


def env(key, default=None):
    return os.environ.get(key, default)


def env_bool(key, default=False):
    return str(os.environ.get(key, default)).lower() in ("1", "true", "yes", "on")


def env_list(key, default=""):
    return [x.strip() for x in os.environ.get(key, default).split(",") if x.strip()]


# Railway بيحط المتغيرات دي لوحده — لو موجودة بنظبط الدومين والأمان أوتوماتيك
ON_RAILWAY = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_PROJECT_ID"))
RAILWAY_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")

def _persistent_secret_key():
    """
    على Railway لو SECRET_KEY مش متحط: بنولّد مفتاح عشوائي مرة واحدة ونحفظه على الـ Volume (/data)
    عشان يفضل ثابت بين كل نشر والتاني (من غيره الناس هتخرج من حساباتها مع كل نشر).
    """
    import secrets
    path = Path(env("SECRET_KEY_FILE", "/data/.django_secret_key"))
    try:
        if path.exists():
            return path.read_text().strip()
        if path.parent.is_dir():
            key = secrets.token_urlsafe(50)
            path.write_text(key)
            os.chmod(path, 0o600)
            return key
    except OSError:
        pass
    return secrets.token_urlsafe(50)  # مفيش volume (زي أمر migrate): مفتاح مؤقت، مش مستخدم في توقيع حاجة دايمة


SECRET_KEY = env("SECRET_KEY") or (_persistent_secret_key() if ON_RAILWAY else "dev-only-insecure-key-change-me-in-production-0123456789")
DEBUG = env_bool("DEBUG", not ON_RAILWAY)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "*" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", "")
SITE_URL = env("SITE_URL", f"https://{RAILWAY_DOMAIN}" if RAILWAY_DOMAIN else "http://localhost:8000").rstrip("/")
if ON_RAILWAY:
    # healthcheck.railway.app = الدومين اللي Railway بيكلم بيه السيرفر وهو بيتأكد إنه اشتغل
    for h in filter(None, [RAILWAY_DOMAIN, "healthcheck.railway.app", urlparse(SITE_URL).hostname]):
        if h not in ALLOWED_HOSTS and "*" not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)
    for o in filter(None, [f"https://{RAILWAY_DOMAIN}" if RAILWAY_DOMAIN else "", SITE_URL]):
        if o.startswith("https://") and o not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(o)
SITE_NAME = env("SITE_NAME", "EduPro")

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    # third party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "corsheaders",
    "drf_spectacular",
    "channels",
    # local
    "apps.core",
    "apps.accounts",
    "apps.catalog",
    "apps.tutoring",
    "apps.courses",
    "apps.assessments",
    "apps.chat",
    "apps.notifications",
    "apps.payments",
    "apps.seo",
    "apps.qa",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # بيقدّم ملفات static من غير Nginx (Railway وغيره)
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.seo.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------- Database ----------
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    u = urlparse(DATABASE_URL)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": u.path.lstrip("/"),
            "USER": u.username,
            "PASSWORD": u.password,
            "HOST": u.hostname,
            "PORT": u.port or 5432,
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "apps.accounts.backends.PhoneOrEmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ar"
LANGUAGES = [("ar", "العربية"), ("en", "English")]
TIME_ZONE = env("TIME_ZONE", "Africa/Cairo")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", str(BASE_DIR / "media")))
# من غير Nginx (زي Railway) Django نفسه يقدّم صور /media/ (الصور الشخصية وأغلفة الكورسات)
SERVE_MEDIA = env_bool("SERVE_MEDIA", ON_RAILWAY)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 50 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
# فيديوهات الكورسات المرفوعة بتتحفظ هنا — برا MEDIA، ومحدش يوصلها غير برابط موقّع مؤقت بعد التأكد من الاشتراك
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))
if len(sys.argv) > 1 and sys.argv[1] == "test":  # الاختبارات ما تكتبش فيديوهات في فولدر المشروع
    import tempfile
    PRIVATE_MEDIA_ROOT = Path(tempfile.mkdtemp(prefix="edupro-test-private-"))
# في الإنتاج: Nginx يبعت الملف بنفسه (X-Accel-Redirect) بدل ما Django يقراه — شوف nginx.conf.example
PROTECTED_MEDIA_ACCEL = env_bool("PROTECTED_MEDIA_ACCEL", False)
VIDEO_MAX_UPLOAD_MB = int(env("VIDEO_MAX_UPLOAD_MB", 2048))
VIDEO_LINK_TTL_MINUTES = int(env("VIDEO_LINK_TTL_MINUTES", 240))
# المدرس يقدر يحدد بنفسه الدروس المجانية؟ لو False الإدارة بس اللي تفتح دروس مجاناً
TEACHER_CAN_SET_FREE_LESSONS = env_bool("TEACHER_CAN_SET_FREE_LESSONS", True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------- CORS (موقع الويب / Flutter Web) ----------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "")
CORS_ALLOW_ALL_ORIGINS = DEBUG and not CORS_ALLOWED_ORIGINS

# ---------- DRF ----------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        "auth": "10/min" if not DEBUG else "200/min",   # في التطوير بتبدّل بين الحسابات كتير
        "otp": "5/hour" if not DEBUG else "100/hour",
    },
    "DATETIME_FORMAT": "iso-8601",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(env("JWT_ACCESS_MINUTES", 60))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(env("JWT_REFRESH_DAYS", 30))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": f"{SITE_NAME} API",
    "DESCRIPTION": "API منصة التعليم أونلاين (حصص لايف، كورسات مسجلة، واجبات وامتحانات، شات، دفع). "
    "كل الطلبات المحمية محتاجة هيدر Authorization: Bearer <access>.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": "apps.core.permissions.Roles.CHOICES",
        "RegisterRoleEnum": ["student", "teacher"],
        "ApproveRejectEnum": ["approve", "reject"],
        "TeacherApprovalActionEnum": ["approve", "reject", "suspend"],
        "SessionStatusEnum": "apps.tutoring.models.Session.STATUS",
        "SubscriptionStatusEnum": "apps.tutoring.models.Subscription.STATUS",
        "TrialStatusEnum": "apps.tutoring.models.TrialRequest.STATUS",
        "RescheduleStatusEnum": "apps.tutoring.models.RescheduleRequest.STATUS",
        "TeacherApprovalStatusEnum": "apps.accounts.models.TeacherProfile.STATUS",
        "CourseStatusEnum": "apps.courses.models.Course.STATUS",
        "LessonTypeEnum": "apps.courses.models.Lesson.TYPES",
        "QuizKindEnum": "apps.assessments.models.Quiz.KINDS",
        "QuestionTypeEnum": "apps.assessments.models.Question.TYPES",
        "AttemptStatusEnum": "apps.assessments.models.Attempt.STATUS",
        "OrderStatusEnum": "apps.payments.models.Order.STATUS",
        "OrderKindEnum": "apps.payments.models.Order.KINDS",
        "OrderMethodEnum": "apps.payments.models.Order.METHODS",
        "MessageTypeEnum": "apps.chat.models.Message.TYPES",
        "ConversationTypeEnum": "apps.chat.models.Conversation.TYPES",
        "DevicePlatformEnum": "apps.notifications.models.Device.PLATFORMS",
    },
}

# ---------- Channels (WebSocket) ----------
REDIS_URL = env("REDIS_URL")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels_redis.core.RedisChannelLayer", "CONFIG": {"hosts": [REDIS_URL]}}
    }
else:
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}

# ---------- Jitsi (الحصص اللايف) ----------
JITSI_DOMAIN = env("JITSI_DOMAIN", "meet.jit.si")
JITSI_APP_ID = env("JITSI_APP_ID", "")          # لو سيرفر Jitsi بتاعك مفعّل عليه JWT
JITSI_APP_SECRET = env("JITSI_APP_SECRET", "")
JITSI_ROOM_PREFIX = env("JITSI_ROOM_PREFIX", "edupro")
# 8x8 JaaS (Jitsi as a Service) — أسهل حل للإنتاج من غير سيرفر خاص. لو اتظبطوا بيتقدموا على السيرفر الخاص.
JITSI_JAAS_APP_ID = env("JITSI_JAAS_APP_ID", "")              # vpaas-magic-cookie-xxxxxxxx
JITSI_JAAS_KID = env("JITSI_JAAS_KID", "")                    # vpaas-magic-cookie-xxxxxxxx/abc123
JITSI_JAAS_PRIVATE_KEY_FILE = env("JITSI_JAAS_PRIVATE_KEY_FILE", "")
JITSI_JAAS_PRIVATE_KEY = env("JITSI_JAAS_PRIVATE_KEY", "")            # بديل للملف: نص المفتاح نفسه (PEM)
SESSION_JOIN_EARLY_MINUTES = int(env("SESSION_JOIN_EARLY_MINUTES", 10))

# ---------- Paymob ----------
PAYMOB_SECRET_KEY = env("PAYMOB_SECRET_KEY", "")
PAYMOB_PUBLIC_KEY = env("PAYMOB_PUBLIC_KEY", "")
PAYMOB_HMAC_SECRET = env("PAYMOB_HMAC_SECRET", "")
PAYMOB_INTEGRATION_IDS = [int(x) for x in env_list("PAYMOB_INTEGRATION_IDS", "")]
PAYMOB_BASE_URL = env("PAYMOB_BASE_URL", "https://accept.paymob.com")
DEFAULT_CURRENCY = env("DEFAULT_CURRENCY", "EGP")
# وضع الدفع التجريبي: لو مفيش مفاتيح Paymob والـ DEBUG شغال، الدفع بيروح لصفحة محاكاة محلية
PAYMENTS_DEV_MODE = env_bool("PAYMENTS_DEV_MODE", DEBUG) and not PAYMOB_SECRET_KEY

# ---------- Push (Firebase Cloud Messaging HTTP v1) ----------
FCM_SERVICE_ACCOUNT_FILE = env("FCM_SERVICE_ACCOUNT_FILE", "")
FCM_SERVICE_ACCOUNT_JSON = env("FCM_SERVICE_ACCOUNT_JSON", "")  # بديل للملف: محتوى الـ JSON كله
FCM_PROJECT_ID = env("FCM_PROJECT_ID", "")

# ---------- SMS / OTP ----------
SMS_BACKEND = env("SMS_BACKEND", "console")   # console | custom
OTP_TTL_MINUTES = 10

# ---------- Email ----------
EMAIL_BACKEND = env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = int(env("EMAIL_PORT", 587))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", f"{SITE_NAME} <no-reply@example.com>")

# ---------- Mobile app (force update + deep links) ----------
APP_MIN_VERSION_ANDROID = env("APP_MIN_VERSION_ANDROID", "1.0.0")
APP_MIN_VERSION_IOS = env("APP_MIN_VERSION_IOS", "1.0.0")
APP_LATEST_VERSION = env("APP_LATEST_VERSION", "1.0.0")
ANDROID_PACKAGE = env("ANDROID_PACKAGE", "com.example.edupro")
ANDROID_SHA256_FINGERPRINTS = env_list("ANDROID_SHA256_FINGERPRINTS", "")
IOS_APP_ID = env("IOS_APP_ID", "")  # TEAMID.bundle.id
PLAY_STORE_URL = env("PLAY_STORE_URL", "")
APP_STORE_URL = env("APP_STORE_URL", "")
SUPPORT_PHONE = env("SUPPORT_PHONE", "")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", "")

# ---------- Production hardening ----------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_REDIRECT_EXEMPT = [r"^api/v1/health/$"]  # فحص السيرفر الداخلي بيجي على http
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    # من غير propagate=False كل سطر في اللوج بيتكرر مرتين (مرة من django ومرة من root)
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "daphne": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        # طلبات بدومين غلط (بوتات) بترجع 400 من غير traceback يملا اللوج
        "django.security.DisallowedHost": {"handlers": [], "propagate": False},
    },
}
