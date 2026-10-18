from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from apps.catalog.views import CurriculumViewSet, GradeViewSet, StageViewSet, SubjectViewSet
from apps.core.views import AppConfigView, HealthView

catalog = DefaultRouter()
catalog.register("curricula", CurriculumViewSet, basename="curricula")
catalog.register("stages", StageViewSet, basename="stages")
catalog.register("grades", GradeViewSet, basename="grades")
catalog.register("subjects", SubjectViewSet, basename="subjects")

api_v1 = [
    path("config/", AppConfigView.as_view()),
    path("health/", HealthView.as_view()),
    path("", include(catalog.urls)),
    path("", include("apps.accounts.urls")),
    path("", include("apps.tutoring.urls")),
    path("", include("apps.courses.urls")),
    path("", include("apps.assessments.urls")),
    path("", include("apps.chat.urls")),
    path("", include("apps.notifications.urls")),
    path("", include("apps.payments.urls")),
    path("", include("apps.dashboard.urls")),
    path("", include("apps.seo.api_urls")),
    path("", include("apps.qa.urls")),
]

admin.site.site_header = f"{settings.SITE_NAME} — لوحة الإدارة"
admin.site.site_title = settings.SITE_NAME

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1)),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("", include("apps.seo.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
elif settings.SERVE_MEDIA:
    from django.urls import re_path
    from django.views.static import serve

    def media(request, path):
        # الصور المرفوعة (أغلفة المقالات/الكورسات…): كاش أسبوع في المتصفح عشان تفتح على طول
        r = serve(request, path, document_root=settings.MEDIA_ROOT)
        if r.status_code == 200:
            r["Cache-Control"] = "public, max-age=604800"
        return r

    urlpatterns.insert(0, re_path(r"^media/(?P<path>.*)$", media))

handler404 = "apps.seo.views.not_found"
