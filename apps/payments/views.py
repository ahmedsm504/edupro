import json
import logging

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsAdmin, IsStaffRole, Roles

from . import paymob
from . import serializers as s
from .models import Coupon, Order
from .services import apply_coupon, fulfill, handle_paymob_transaction

logger = logging.getLogger(__name__)


def _billing(user):
    parts = (user.full_name or "Student").split(" ", 1)
    return {
        "first_name": parts[0], "last_name": parts[1] if len(parts) > 1 else parts[0],
        "email": user.email or f"user{user.id}@example.com", "phone_number": user.phone,
        "apartment": "NA", "floor": "NA", "street": "NA", "building": "NA", "city": "NA",
        "country": user.country or "EG", "state": "NA", "postal_code": "NA",
    }


@extend_schema(tags=["Payments"])
class CheckoutView(APIView):
    @extend_schema(
        summary="بدء الدفع لاشتراك أو كورس",
        description="لو الإجمالي = 0 بيتفعل فوراً (status=paid). غير كده افتح checkout_url في WebView، "
                    "ولما الـ URL يبدأ بـ success_url_prefix اقفل الـ WebView واعمل GET على /payments/orders/{id}/ لحد ما status=paid.",
        request=s.CheckoutSerializer, responses={201: s.CheckoutResponseSerializer})
    def post(self, request):
        ser = s.CheckoutSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        user = request.user
        if d["kind"] == "subscription":
            from apps.tutoring.services import subscriptions_visible_to
            sub = get_object_or_404(subscriptions_visible_to(user), pk=d["subscription_id"])
            if sub.status != "pending_payment":
                raise BusinessError("الاشتراك ده مش في انتظار الدفع.", code="invalid_status")
            amount, student, currency = sub.package.price, sub.student, sub.package.currency
            target = {"subscription": sub}
        else:
            from apps.courses.models import Course
            from apps.courses.services import active_enrollment
            course = get_object_or_404(Course, pk=d["course_id"], status="published")
            if user.role != Roles.STUDENT:
                raise BusinessError("شراء الكورسات للطلاب.", code="forbidden", status_code=403)
            student = user
            if active_enrollment(student, course):
                raise BusinessError("مشترك في الكورس ده بالفعل.", code="already_enrolled")
            amount, currency = course.price, course.currency
            target = {"course": course}
        coupon, discount = apply_coupon(d.get("coupon"), d["kind"], amount)
        total = amount - discount
        order = Order.objects.create(user=user, student=student, kind=d["kind"], amount=amount, discount=discount,
                                     total=total, currency=currency, coupon=coupon, **target)
        resp = {"order": None, "checkout_url": None, "client_secret": None, "public_key": None,
                "success_url_prefix": f"{settings.SITE_URL}/payments/result/"}
        if total <= 0:
            order = fulfill(order.id, method="free")
        elif settings.PAYMENTS_DEV_MODE:
            # بيئة تجربة: صفحة دفع محلية بدل Paymob
            dev_url = request.build_absolute_uri(f"/payments/dev-checkout/{order.reference}/")
            resp.update(checkout_url=dev_url, client_secret="dev", public_key="dev",
                        success_url_prefix=request.build_absolute_uri("/payments/result/"))
        else:
            try:
                data = paymob.create_intention(order, _billing(user))
            except paymob.PaymobError as e:
                order.status = "failed"
                order.save(update_fields=["status"])
                raise BusinessError(str(e), code="payment_gateway_error", status_code=502)
            order.client_secret = data.get("client_secret", "")
            order.paymob_intention_id = str(data.get("id", ""))
            if data.get("intention_order_id"):
                order.paymob_order_id = str(data["intention_order_id"])
            order.save()
            resp.update(checkout_url=paymob.checkout_url(order.client_secret), client_secret=order.client_secret,
                        public_key=settings.PAYMOB_PUBLIC_KEY)
        resp["order"] = s.OrderSerializer(order).data
        return Response(resp, status=status.HTTP_201_CREATED)


@extend_schema(tags=["Payments"])
class CouponValidateView(APIView):
    @extend_schema(summary="التحقق من كود خصم", request=s.CouponValidateSerializer,
                   responses=inline_serializer("CouponResult", {"code": serializers.CharField(),
                                                                "discount": serializers.DecimalField(10, 2),
                                                                "total": serializers.DecimalField(10, 2)}))
    def post(self, request):
        ser = s.CouponValidateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        c, discount = apply_coupon(d["code"], d["kind"], d["amount"])
        return Response({"code": c.code, "discount": discount, "total": d["amount"] - discount})


@extend_schema(tags=["Payments"])
@schema_safe(Order)
class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.OrderSerializer
    filterset_fields = ["status", "kind", "method"]

    def get_queryset(self):
        u = self.request.user
        qs = Order.objects.select_related("course", "subscription__package", "subscription__subject")
        return qs if u.role in Roles.STAFF else qs.filter(user=u)

    @extend_schema(summary="(أدمن) تأكيد دفع يدوي (كاش/تحويل/فودافون كاش)", request=None, responses=s.OrderSerializer)
    @action(detail=True, methods=["post"], url_path="mark-paid", permission_classes=[IsAdmin])
    def mark_paid(self, request, pk=None):
        order = self.get_object()
        return Response(s.OrderSerializer(fulfill(order.id, method="manual")).data)


@extend_schema(tags=["Admin - Payments"])
class CouponViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdmin]
    serializer_class = s.CouponSerializer
    queryset = Coupon.objects.all().order_by("-created_at")


@method_decorator(csrf_exempt, name="dispatch")
class PaymobWebhookView(APIView):
    """Paymob → Transaction processed callback. متحطش عليه auth."""
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = []

    @extend_schema(tags=["Payments"], summary="Webhook بتاع Paymob (للسيرفر فقط — مش للتطبيق)", request=None, responses={200: None})
    def post(self, request):
        payload = request.data if isinstance(request.data, dict) else json.loads(request.body or "{}")
        obj = payload.get("obj") or {}
        received = request.query_params.get("hmac") or payload.get("hmac", "")
        if not paymob.verify_hmac_webhook(obj, received):
            logger.warning("Paymob webhook HMAC mismatch")
            return Response({"detail": "invalid hmac"}, status=400)
        if payload.get("type", "TRANSACTION") == "TRANSACTION":
            handle_paymob_transaction(obj)
        return Response({"received": True})


def payment_result(request):
    """الصفحة اللي Paymob بيحوّل عليها بعد الدفع (التطبيق بيقفل الـ WebView لما يوصلها)."""
    params = request.GET.dict()
    if settings.PAYMENTS_DEV_MODE and params.get("dev") == "1":
        order = Order.objects.filter(reference=params.get("ref")).first() if params.get("ref") else None
        success = bool(order and order.status == "paid")
    else:
        valid = bool(settings.PAYMOB_HMAC_SECRET) and paymob.verify_hmac_redirect(params)
        success = valid and params.get("success") == "true"
    return render(request, "seo/payment_result.html", {"success": success, "params": params, "noindex": True})


@csrf_exempt
def dev_checkout(request, reference):
    """محاكاة صفحة الدفع (تشتغل بس في وضع التجربة) — زرار نجاح وزرار فشل."""
    from django.http import Http404
    from django.shortcuts import redirect
    if not settings.PAYMENTS_DEV_MODE:
        raise Http404
    order = get_object_or_404(Order, reference=reference)
    if request.method == "POST" and order.status == "pending":
        if request.POST.get("result") == "success":
            fulfill(order.id, method="paymob")
        else:
            order.status = "failed"
            order.save(update_fields=["status"])
        return redirect(f"/payments/result/?dev=1&ref={order.reference}")
    return render(request, "seo/dev_checkout.html", {"order": order, "noindex": True})
