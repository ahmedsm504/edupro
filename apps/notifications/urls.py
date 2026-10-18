from rest_framework.routers import DefaultRouter

from .views import DeviceViewSet, NotificationViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("devices", DeviceViewSet, basename="devices")
urlpatterns = router.urls
