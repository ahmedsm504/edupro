from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view, inline_serializer
from rest_framework import mixins, parsers, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import BusinessError
from apps.core.models import schema_safe
from apps.core.permissions import IsStaffRole, Roles
from apps.seo.models import Tag

from . import serializers as s
from . import services
from .models import Answer, Question


def _tags(names):
    out = []
    for n in names or []:
        n = n.strip().lstrip("#")[:40]
        if n:
            out.append(Tag.objects.get_or_create(name=n)[0])
    return out


@extend_schema_view(
    list=extend_schema(
        summary="الأسئلة (عامة) — فلترة وبحث وترتيب",
        parameters=[
            OpenApiParameter("subject", int), OpenApiParameter("subject__slug", str), OpenApiParameter("tags__slug", str),
            OpenApiParameter("tab", str, enum=["latest", "unanswered", "popular", "mine"],
                             description="latest = آخر نشاط، unanswered = بدون إجابة، popular = الأعلى تصويتاً، mine = أسئلتي"),
            OpenApiParameter("search", str),
        ],
    ),
    retrieve=extend_schema(summary="تفاصيل سؤال بالإجابات (الإجابة المختارة أولاً) — بالـ slug"),
)
@extend_schema(tags=["Q&A"])
@schema_safe(Question)
class QuestionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_fields = ["subject", "subject__slug", "grade", "tags__slug", "moderation"]
    search_fields = ["title", "body"]
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]

    def get_permissions(self):
        return [AllowAny()] if self.action in ("list", "retrieve") else [IsAuthenticated()]

    def get_serializer_class(self):
        return s.QuestionDetailSerializer if self.action == "retrieve" else s.QuestionListSerializer

    def get_queryset(self):
        qs = services.visible_questions(self.request.user)
        tab = self.request.query_params.get("tab")
        if tab == "unanswered":
            qs = qs.filter(answers_count=0, is_closed=False)
        elif tab == "popular":
            qs = qs.order_by("-score", "-answers_count", "-views_count")
        elif tab == "mine" and self.request.user.is_authenticated:
            qs = qs.filter(author=self.request.user)
        elif tab == "for_me" and self.request.user.role == Roles.TEACHER:
            qs = qs.filter(subject__in=self.request.user.teacher_profile.subjects.all(), moderation="approved") \
                   .exclude(answers__author=self.request.user).order_by("answers_count", "-created_at")
        return qs.distinct()

    def retrieve(self, request, *a, **kw):
        q = self.get_object()
        services.bump_views(q)
        return Response(s.QuestionDetailSerializer(q, context={"request": request}).data)

    @extend_schema(summary="اسأل سؤال (أي مستخدم مسجل) — لو فيه رقم/لينك بيتعلّق للمراجعة (moderation=pending)",
                   request=s.AskSerializer, responses={201: s.QuestionDetailSerializer})
    def create(self, request):
        ser = s.AskSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        names = d.pop("tags", None)
        if not names and hasattr(request.data, "getlist"):
            names = request.data.getlist("tags")
        if isinstance(names, str):
            names = names.split(",")
        q = services.ask(request.user, d, _tags(names))
        return Response(s.QuestionDetailSerializer(q, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="تعديل سؤالي", request=s.AskSerializer, responses=s.QuestionDetailSerializer)
    def partial_update(self, request, slug=None):
        q = self.get_object()
        if q.author_id != request.user.id and not services.is_staff(request.user):
            raise BusinessError("مش سؤالك.", code="forbidden", status_code=403)
        ser = s.AskSerializer(q, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = dict(ser.validated_data)
        tags = d.pop("tags", None)
        for k, v in d.items():
            setattr(q, k, v)
        mod, reasons = services._moderate(request.user, q.title, q.body)
        q.moderation, q.flag_reasons = (mod, reasons) if mod == "pending" else (q.moderation, q.flag_reasons)
        q.save()
        if tags is not None:
            q.tags.set(_tags(tags))
        return Response(s.QuestionDetailSerializer(q, context={"request": request}).data)

    def destroy(self, request, *a, **kw):
        q = self.get_object()
        if not services.is_staff(request.user) and (q.author_id != request.user.id or q.answers_count):
            raise BusinessError("تقدر تمسح سؤالك بس لو مفيش عليه إجابات.", code="forbidden", status_code=403)
        q.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="إضافة إجابة", request=s.AnswerCreateSerializer, responses={201: s.AnswerSerializer})
    @action(detail=True, methods=["post"])
    def answers(self, request, slug=None):
        q = self.get_object()
        ser = s.AnswerCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        a = services.answer(request.user, q, ser.validated_data["body"], ser.validated_data.get("image"))
        return Response(s.AnswerSerializer(a, context={"request": request}).data, status=status.HTTP_201_CREATED)

    @extend_schema(summary="تصويت على السؤال", request=s.VoteSerializer,
                   responses=inline_serializer("VoteResult", {"score": serializers.IntegerField(), "my_vote": serializers.IntegerField()}))
    @action(detail=True, methods=["post"])
    def vote(self, request, slug=None):
        q = self.get_object()
        ser = s.VoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        score = services.vote(request.user, ser.validated_data["value"], question=q)
        return Response({"score": score, "my_vote": ser.validated_data["value"]})

    @extend_schema(summary="(إدارة) قفل/فتح السؤال", request=None, responses=s.QuestionListSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def close(self, request, slug=None):
        q = self.get_object()
        q.is_closed = not q.is_closed
        q.save(update_fields=["is_closed"])
        return Response(s.QuestionListSerializer(q, context={"request": request}).data)


@extend_schema(tags=["Q&A"])
@schema_safe(Answer)
class AnswerViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = s.AnswerSerializer
    http_method_names = ["patch", "delete", "post"]

    def get_queryset(self):
        return Answer.objects.select_related("question", "author")

    def _own(self):
        a = self.get_object()
        if a.author_id != self.request.user.id and not services.is_staff(self.request.user):
            raise BusinessError("مش إجابتك.", code="forbidden", status_code=403)
        return a

    @extend_schema(summary="تعديل إجابتي", request=s.AnswerCreateSerializer)
    def partial_update(self, request, *a, **kw):
        ans = self._own()
        ser = s.AnswerCreateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        if "body" in ser.validated_data:
            ans.body = ser.validated_data["body"]
            mod, reasons = services._moderate(request.user, ans.body)
            if mod == "pending":
                ans.moderation, ans.flag_reasons = mod, reasons
        ans.save()
        services.recount(ans.question)
        return Response(s.AnswerSerializer(ans, context={"request": request}).data)

    def destroy(self, request, *a, **kw):
        ans = self._own()
        q = ans.question
        if q.accepted_answer_id == ans.id:
            q.accepted_answer = None
            q.save(update_fields=["accepted_answer"])
        ans.delete()
        services.recount(q)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(summary="تصويت على إجابة", request=s.VoteSerializer,
                   responses=inline_serializer("AnswerVoteResult", {"score": serializers.IntegerField(), "my_vote": serializers.IntegerField()}))
    @action(detail=True, methods=["post"])
    def vote(self, request, pk=None):
        a = self.get_object()
        ser = s.VoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        return Response({"score": services.vote(request.user, ser.validated_data["value"], answer=a), "my_vote": ser.validated_data["value"]})

    @extend_schema(summary="اختيار/إلغاء أفضل إجابة (صاحب السؤال أو الإدارة)", request=None, responses=s.QuestionListSerializer)
    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        q = services.accept(request.user, self.get_object())
        return Response(s.QuestionListSerializer(q, context={"request": request}).data)


class ModerationView(APIView):
    """طابور المراجعة: أسئلة وإجابات اتعلّمت بسبب بيانات تواصل."""
    permission_classes = [IsStaffRole]

    @extend_schema(tags=["Q&A"], summary="(إدارة) طابور مراجعة الأسئلة والإجابات", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        qs = Question.objects.filter(moderation="pending").select_related("author", "subject")
        ans = Answer.objects.filter(moderation="pending").select_related("author", "question")
        ctx = {"request": request}
        return Response({
            "questions": s.QuestionDetailSerializer(qs, many=True, context=ctx).data,
            "answers": [{**s.AnswerSerializer(a, context=ctx).data, "flag_reasons": a.flag_reasons,
                         "question": {"slug": a.question.slug, "title": a.question.title}} for a in ans],
        })

    @extend_schema(tags=["Q&A"], summary="(إدارة) قبول/رفض سؤال أو إجابة",
                   request=inline_serializer("ModerateBody", {"kind": serializers.ChoiceField(choices=["question", "answer"]),
                                                               "id": serializers.IntegerField(),
                                                               "action": serializers.ChoiceField(choices=["approve", "reject"])}),
                   responses={200: OpenApiTypes.OBJECT})
    def post(self, request):
        kind, pk, act = request.data.get("kind"), request.data.get("id"), request.data.get("action")
        if act not in ("approve", "reject") or kind not in ("question", "answer"):
            raise BusinessError("بيانات غلط.", code="validation_error")
        obj = get_object_or_404(Question if kind == "question" else Answer, pk=pk)
        services.moderate(obj, act, request.user)
        return Response({"ok": True, "moderation": obj.moderation})


class QAStatsView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(tags=["Q&A"], summary="إحصائيات بنك الأسئلة + أكتر المدرسين إجابة", responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        from django.db.models import Count
        from apps.accounts.models import User
        approved = Question.objects.filter(moderation="approved")
        top = (User.objects.filter(role=Roles.TEACHER, answers__moderation="approved")
               .annotate(n=Count("answers")).order_by("-n")[:5])
        return Response({
            "questions": approved.count(),
            "answered": approved.filter(answers_count__gt=0).count(),
            "answers": Answer.objects.filter(moderation="approved").count(),
            "top_teachers": [{"id": u.id, "full_name": u.full_name, "answers": u.n,
                              "slug": getattr(getattr(u, "teacher_profile", None), "slug", None)} for u in top],
        })
