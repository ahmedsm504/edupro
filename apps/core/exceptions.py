"""
شكل موحد لكل الأخطاء:
{
  "success": false,
  "error": {"code": "validation_error", "message": "رسالة مفهومة", "details": {...}}
}
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class BusinessError(exceptions.APIException):
    """خطأ منطق عمل (مثلاً: الحصة لم تبدأ بعد). code بيكون ثابت عشان الفلاتر يتعامل معاه."""
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "business_error"
    default_detail = "لا يمكن تنفيذ العملية."

    def __init__(self, message=None, code=None, status_code=None):
        super().__init__(detail=message or self.default_detail, code=code or self.default_code)
        if status_code:
            self.status_code = status_code
        self.error_code = code or self.default_code


def _first_message(details):
    if isinstance(details, list) and details:
        return _first_message(details[0])
    if isinstance(details, dict) and details:
        return _first_message(next(iter(details.values())))
    return str(details)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, BusinessError):
        code = exc.error_code
        details = None
        message = str(exc.detail)
    elif isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
        details = response.data
        message = _first_message(response.data)
    else:
        codes = exc.get_codes() if hasattr(exc, "get_codes") else "error"
        if isinstance(codes, dict):  # SimpleJWT: {"detail":..., "code": "token_not_valid", ...}
            codes = codes.get("code") or codes.get("detail") or "error"
        code = codes if isinstance(codes, str) else "error"
        details = None
        message = response.data.get("detail", str(exc)) if isinstance(response.data, dict) else str(exc)

    payload = {"success": False, "error": {"code": code, "message": str(message), "details": details}}
    if isinstance(exc, exceptions.Throttled) and exc.wait:
        payload["error"]["retry_after"] = int(exc.wait)
    new = Response(payload, status=response.status_code)
    for h in ("Retry-After", "WWW-Authenticate"):
        if response.has_header(h):
            new[h] = response[h]
    return new
