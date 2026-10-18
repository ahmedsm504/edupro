from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.catalog.models import Grade, Subject
from apps.catalog.serializers import SubjectMiniSerializer
from apps.core.richtext import text_to_html
from apps.seo.models import Tag

from . import services
from .models import Answer, Question


class QAUserSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    avatar = serializers.ImageField()
    role = serializers.CharField()
    teacher_slug = serializers.SerializerMethodField()
    is_verified_teacher = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_teacher_slug(self, u):
        tp = getattr(u, "teacher_profile", None)
        return tp.slug if tp and tp.is_approved else None

    def get_is_verified_teacher(self, u) -> bool:
        tp = getattr(u, "teacher_profile", None)
        return bool(tp and tp.is_approved)


class QATagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class QuestionListSerializer(serializers.ModelSerializer):
    author = QAUserSerializer(read_only=True)
    subject = SubjectMiniSerializer(read_only=True)
    tags = QATagSerializer(many=True, read_only=True)
    has_accepted_answer = serializers.SerializerMethodField()
    excerpt = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = ["id", "slug", "title", "excerpt", "author", "subject", "grade", "tags", "score", "answers_count",
                  "views_count", "has_accepted_answer", "is_closed", "moderation", "created_at", "last_activity_at"]

    def get_has_accepted_answer(self, q) -> bool:
        return bool(q.accepted_answer_id)

    def get_excerpt(self, q) -> str:
        t = (q.body or "").strip().replace("\n", " ")
        return t[:180] + ("…" if len(t) > 180 else "")


class AnswerSerializer(serializers.ModelSerializer):
    author = QAUserSerializer(read_only=True)
    body_html = serializers.SerializerMethodField()
    is_accepted = serializers.SerializerMethodField()
    my_vote = serializers.SerializerMethodField()

    class Meta:
        model = Answer
        fields = ["id", "author", "body", "body_html", "image", "score", "is_accepted", "my_vote", "moderation", "created_at", "updated_at"]
        read_only_fields = ["score", "moderation"]

    def get_body_html(self, a) -> str:
        return text_to_html(a.body)

    def get_is_accepted(self, a) -> bool:
        return a.question.accepted_answer_id == a.id

    def get_my_vote(self, a) -> int:
        return services.my_vote(self.context["request"].user, answer=a)


class QuestionDetailSerializer(QuestionListSerializer):
    body_html = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    my_vote = serializers.SerializerMethodField()
    can_accept = serializers.SerializerMethodField()

    class Meta(QuestionListSerializer.Meta):
        fields = QuestionListSerializer.Meta.fields + ["body", "body_html", "image", "accepted_answer", "answers", "my_vote",
                                                       "can_accept", "flag_reasons"]

    def get_body_html(self, q) -> str:
        return text_to_html(q.body)

    @extend_schema_field(AnswerSerializer(many=True))
    def get_answers(self, q):
        user = self.context["request"].user
        rows = sorted(services.visible_answers(user, q), key=lambda a: (a.id != q.accepted_answer_id, -a.score, a.created_at))
        return AnswerSerializer(rows, many=True, context=self.context).data

    def get_my_vote(self, q) -> int:
        return services.my_vote(self.context["request"].user, question=q)

    def get_can_accept(self, q) -> bool:
        u = self.context["request"].user
        return u.is_authenticated and (u.id == q.author_id or services.is_staff(u))

    def to_representation(self, q):
        d = super().to_representation(q)
        if not services.is_staff(self.context["request"].user):
            d.pop("flag_reasons", None)
        return d


class AskSerializer(serializers.Serializer):
    title = serializers.CharField(min_length=12, max_length=200, help_text="السؤال في جملة واضحة (12 حرف على الأقل)")
    body = serializers.CharField(required=False, allow_blank=True, max_length=8000)
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.filter(is_active=True))
    grade = serializers.PrimaryKeyRelatedField(queryset=Grade.objects.all(), required=False, allow_null=True)
    image = serializers.ImageField(required=False, allow_null=True)
    tags = serializers.ListField(child=serializers.CharField(max_length=40), required=False, max_length=5,
                                 help_text="لحد 5 وسوم بالاسم")


class AnswerCreateSerializer(serializers.Serializer):
    body = serializers.CharField(min_length=20, max_length=12000, help_text="20 حرف على الأقل")
    image = serializers.ImageField(required=False, allow_null=True)


class VoteSerializer(serializers.Serializer):
    value = serializers.ChoiceField(choices=[1, -1, 0], help_text="1 = مفيد، -1 = مش مفيد، 0 = إلغاء التصويت")


class ModerationSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
