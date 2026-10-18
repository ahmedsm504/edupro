from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


class AppConfigView(APIView):
    """إعدادات عامة للتطبيق: أقل إصدار مسموح (force update)، روابط المتاجر، الدعم، الفيتشرز المفعلة."""
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Config"], summary="إعدادات التطبيق العامة", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response({
            "site_name": settings.SITE_NAME,
            "site_url": settings.SITE_URL,
            "currency": settings.DEFAULT_CURRENCY,
            "min_version": {"android": settings.APP_MIN_VERSION_ANDROID, "ios": settings.APP_MIN_VERSION_IOS},
            "latest_version": settings.APP_LATEST_VERSION,
            "store_urls": {"android": settings.PLAY_STORE_URL, "ios": settings.APP_STORE_URL},
            "support": {"phone": settings.SUPPORT_PHONE, "email": settings.SUPPORT_EMAIL},
            "jitsi_domain": settings.JITSI_DOMAIN,
            "session_join_early_minutes": settings.SESSION_JOIN_EARLY_MINUTES,
            "features": {
                "live_sessions": True, "recorded_courses": True, "quizzes": True,
                "chat": True, "blog": True, "qa": True,
                "online_payment": bool(settings.PAYMOB_SECRET_KEY) or settings.PAYMENTS_DEV_MODE,
                "payments_dev_mode": settings.PAYMENTS_DEV_MODE,
                "certificates": True, "lesson_notes": True,
            },
            "courses": {
                "teacher_can_set_free_lessons": settings.TEACHER_CAN_SET_FREE_LESSONS,
                "video_max_upload_mb": settings.VIDEO_MAX_UPLOAD_MB,
                "video_formats": ["mp4", "webm", "mov", "m4v"],
            },
            "live_provider": "jaas" if (settings.JITSI_JAAS_APP_ID and settings.JITSI_JAAS_KID) else ("jitsi_jwt" if settings.JITSI_APP_ID else "jitsi_public"),
            "websocket_path": "/ws/",
        })


class HealthView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["Config"], summary="فحص صحة السيرفر", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        return Response({"status": "ok"})
