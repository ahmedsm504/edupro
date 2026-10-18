from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("payments/orders", v.OrderViewSet, basename="orders")
router.register("admin/coupons", v.CouponViewSet, basename="coupons")

urlpatterns = [
    path("payments/checkout/", v.CheckoutView.as_view()),
    path("payments/coupons/validate/", v.CouponValidateView.as_view()),
    path("payments/paymob/webhook/", v.PaymobWebhookView.as_view()),
    path("", include(router.urls)),
]
