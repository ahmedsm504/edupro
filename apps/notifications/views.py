from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import schema_safe
from .models import Device, Notification
from .serializers import DeviceSerializer, NotificationSerializer


@extend_schema(tags=["Notifications"])
@schema_safe(Notification)
class NotificationViewSet(mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = NotificationSerializer
    filterset_fields = ["is_read", "type"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(summary="عدد الإشعارات غير المقروءة",
                   responses=inline_serializer("UnreadCount", {"unread": serializers.IntegerField()}))
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        return Response({"unread": self.get_queryset().filter(is_read=False).count()})

    @extend_schema(summary="تعليم إشعار كمقروء", request=None, responses=NotificationSerializer)
    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        n = self.get_object()
        n.is_read = True
        n.save(update_fields=["is_read"])
        return Response(NotificationSerializer(n).data)

    @extend_schema(summary="تعليم الكل كمقروء", request=None, responses={204: None})
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(tags=["Notifications"])
@schema_safe(Device)
class DeviceViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """تسجيل توكن FCM بعد الدخول وكل ما التوكن يتغير (onTokenRefresh)."""
    serializer_class = DeviceSerializer

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    @extend_schema(summary="تسجيل/تحديث توكن FCM للجهاز")
    def create(self, request, *a, **kw):
        ser = DeviceSerializer(data=request.data)
        ser.is_valid(raise_exception=False)
        token = request.data.get("token")
        if not token:
            ser.is_valid(raise_exception=True)
        dev, _ = Device.objects.update_or_create(
            token=token, defaults={"user": request.user, "platform": request.data.get("platform", "android"),
                                   "app_version": request.data.get("app_version", "")})
        return Response(DeviceSerializer(dev).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="حذف توكن (عند تسجيل الخروج)",
                   request=inline_serializer("DeviceUnregister", {"token": serializers.CharField()}), responses={204: None})
    @action(detail=False, methods=["post"])
    def unregister(self, request):
        Device.objects.filter(user=request.user, token=request.data.get("token")).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
