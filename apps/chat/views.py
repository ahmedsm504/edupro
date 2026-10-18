from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.serializers import UserMiniSerializer
from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.pagination import MessageCursorPagination
from apps.core.permissions import IsStaffRole, Roles

from . import serializers as s
from . import services
from .models import ContactViolation, Conversation, Message


@extend_schema_view(
    list=extend_schema(summary="محادثاتي (الأحدث أولاً) — الإدارة: ?all=true لكل المحادثات للمراقبة",
                       parameters=[OpenApiParameter("all", bool)]),
)
@extend_schema(tags=["Chat"])
@schema_safe(Conversation)
class ConversationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.ConversationSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def get_queryset(self):
        oversight = self.request.query_params.get("all") in ("1", "true") or self.action not in ("list",)
        return services.conversations_for(self.request.user, oversight=oversight).prefetch_related("members__user")

    def get_object(self):
        conv = get_object_or_404(Conversation, pk=self.kwargs["pk"])
        if not services.can_view(self.request.user, conv):
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        return conv

    @extend_schema(summary="فتح/إنشاء محادثة مع مستخدم (لازم يكون مسموح)", request=s.StartConversationSerializer,
                   responses=s.ConversationSerializer)
    @action(detail=False, methods=["post"])
    def start(self, request):
        ser = s.StartConversationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        other = get_object_or_404(User, pk=ser.validated_data["user_id"], is_active=True)
        conv, created = services.get_or_create_direct(request.user, other)
        return Response(s.ConversationSerializer(conv, context={"request": request}).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    @extend_schema(summary="محادثة الدعم الفني", request=None, responses=s.ConversationSerializer)
    @action(detail=False, methods=["post"])
    def support(self, request):
        conv = services.get_support_conversation(request.user)
        return Response(s.ConversationSerializer(conv, context={"request": request}).data)

    @extend_schema(summary="الأشخاص اللي مسموح أكلمهم (مدرسيني/طلابي/أولياء الأمور/الإدارة)",
                   responses=UserMiniSerializer(many=True))
    @action(detail=False, methods=["get"])
    def contacts(self, request):
        ids = services.allowed_contacts(request.user)
        qs = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
        if ids is not None:
            qs = qs.filter(pk__in=ids)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(full_name__icontains=search) | Q(phone__icontains=search))
        page = self.paginate_queryset(qs.order_by("role", "full_name"))
        return self.get_paginated_response(UserMiniSerializer(page, many=True, context={"request": request}).data)

    @extend_schema(methods=["GET"], summary="رسائل المحادثة (cursor pagination، الأحدث أولاً)",
                   responses=s.MessageSerializer(many=True))
    @extend_schema(methods=["POST"], summary="إرسال رسالة (نص JSON، أو multipart لصورة/ملف/صوت)",
                   request=s.SendMessageSerializer, responses={201: s.MessageSerializer})
    @action(detail=True, methods=["get", "post"])
    def messages(self, request, pk=None):
        conv = self.get_object()
        is_staff = request.user.role in Roles.STAFF
        if request.method == "GET":
            qs = conv.messages.select_related("sender")
            paginator = MessageCursorPagination()
            page = paginator.paginate_queryset(qs, request, view=self)
            data = s.MessageSerializer(page, many=True, context={"request": request, "for_staff": is_staff}).data
            return paginator.get_paginated_response(data)
        ser = s.SendMessageSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        reply = Message.objects.filter(pk=d.get("reply_to"), conversation=conv).first() if d.get("reply_to") else None
        msg = services.send_message(request.user, conv, text=d.get("text", ""), type=d["type"],
                                    attachment=d.get("attachment"), duration=d.get("duration_seconds"),
                                    reply_to=reply, request=request)
        return Response(s.MessageSerializer(msg, context={"request": request, "for_staff": is_staff}).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(summary="تعليم المحادثة كمقروءة", request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        services.mark_read(request.user, self.get_object())
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="كتم/إلغاء كتم الإشعارات", request=None, responses={200: None})
    @action(detail=True, methods=["post"])
    def mute(self, request, pk=None):
        conv = self.get_object()
        p = conv.members.filter(user=request.user).first()
        if p:
            p.muted = not p.muted
            p.save(update_fields=["muted"])
        return Response({"muted": bool(p and p.muted)})

    @extend_schema(summary="(إدارة) قفل/فتح المحادثة", request=None, responses=s.ConversationSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def lock(self, request, pk=None):
        conv = self.get_object()
        conv.is_locked = not conv.is_locked
        conv.save(update_fields=["is_locked"])
        return Response(s.ConversationSerializer(conv, context={"request": request}).data)


@extend_schema(tags=["Chat"])
@schema_safe(Message)
class MessageViewSet(mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = s.MessageSerializer

    def get_queryset(self):
        u = self.request.user
        return Message.objects.all() if u.role in Roles.STAFF else Message.objects.filter(sender=u)

    @extend_schema(summary="حذف رسالة (صاحبها أو الإدارة)")
    def destroy(self, request, *a, **kw):
        m = self.get_object()
        m.is_deleted = True
        m.save(update_fields=["is_deleted"])
        from apps.notifications.services import ws_send
        for p in m.conversation.members.all():
            ws_send(p.user_id, "message.deleted", {"conversation_id": m.conversation_id, "message_id": m.id})
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(list=extend_schema(summary="(إدارة) محاولات التواصل خارج المنصة ?reviewed=false"))
@extend_schema(tags=["Admin - Chat oversight"])
@schema_safe(ContactViolation)
class ViolationViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsStaffRole]
    serializer_class = s.ContactViolationSerializer
    filterset_fields = ["reviewed", "user"]
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        qs = ContactViolation.objects.select_related("user", "message__sender").order_by("-created_at")
        if self.request.user.role == Roles.SUPERVISOR:
            qs = qs.filter(Q(user__teacher_profile__supervisor=self.request.user) |
                           Q(message__conversation__members__user__teacher_profile__supervisor=self.request.user)).distinct()
        return qs
