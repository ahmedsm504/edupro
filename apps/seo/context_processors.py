import json

from django.conf import settings
from django.core.cache import cache


def _nav_subjects():
    data = cache.get("nav_subjects")
    if data is None:
        from apps.catalog.models import Subject
        data = list(Subject.objects.filter(is_active=True).order_by("-is_featured", "order").values("name", "slug", "color")[:14])
        cache.set("nav_subjects", data, 300)
    return data


def site(request):
    path = request.path
    site_schema = json.dumps([
        {"@context": "https://schema.org", "@type": "EducationalOrganization", "name": settings.SITE_NAME, "url": settings.SITE_URL,
         "logo": f"{settings.SITE_URL}/static/img/logo.svg",
         **({"contactPoint": {"@type": "ContactPoint", "telephone": settings.SUPPORT_PHONE, "contactType": "customer support",
                              "areaServed": "EG", "availableLanguage": ["ar"]}} if settings.SUPPORT_PHONE else {})},
        {"@context": "https://schema.org", "@type": "WebSite", "name": settings.SITE_NAME, "url": settings.SITE_URL, "inLanguage": "ar",
         "potentialAction": {"@type": "SearchAction", "target": f"{settings.SITE_URL}/search/?q={{search_term_string}}",
                             "query-input": "required name=search_term_string"}},
    ], ensure_ascii=False) if path == "/" else ""
    return {
        "SITE_NAME": settings.SITE_NAME, "SITE_URL": settings.SITE_URL,
        "PLAY_STORE_URL": settings.PLAY_STORE_URL, "APP_STORE_URL": settings.APP_STORE_URL,
        "SUPPORT_PHONE": settings.SUPPORT_PHONE, "SUPPORT_EMAIL": settings.SUPPORT_EMAIL,
        "CANONICAL": settings.SITE_URL + path + (f"?page={request.GET['page']}" if request.GET.get("page", "1") != "1" else ""),
        "NAV_SUBJECTS": _nav_subjects() if not path.startswith(("/app", "/login", "/admin", "/api")) else [],
        "SITE_SCHEMA": site_schema,
        "NAV": path.strip("/").split("/")[0],
    }
