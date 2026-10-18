from django.utils import translation


class ArabicSiteMiddleware:
    """صفحات الموقع دايماً عربي (التواريخ وأسماء الشهور) حتى لو المتصفح إنجليزي.
    الـ API بيفضل يحترم Accept-Language للتطبيق."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/"):
            translation.activate("ar")
            request.LANGUAGE_CODE = "ar"
        return self.get_response(request)
