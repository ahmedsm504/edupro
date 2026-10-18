from decimal import Decimal

from django.db import transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import UserMiniSerializer
from apps.core.permissions import Roles

from .models import Answer, Attempt, Choice, Question, Quiz, QuizAssignment


# ---------------- Teacher (authoring) ----------------
class ChoiceWriteSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)

    class Meta:
        model = Choice
        fields = ["id", "text", "is_correct", "order"]


class QuestionWriteSerializer(serializers.ModelSerializer):
    choices = ChoiceWriteSerializer(many=True, required=False)

    class Meta:
        model = Question
        fields = ["id", "quiz", "type", "text", "image", "points", "correct_text", "explanation", "order", "choices"]

    def validate(self, a):
        t = a.get("type", getattr(self.instance, "type", "single"))
        choices = a.get("choices")
        if t in ("single", "multiple", "true_false") and choices is not None:
            correct = [c for c in choices if c.get("is_correct")]
            if len(choices) < 2:
                raise serializers.ValidationError({"choices": "لازم اختيارين على الأقل."})
            if not correct:
                raise serializers.ValidationError({"choices": "حدد الإجابة الصحيحة."})
            if t in ("single", "true_false") and len(correct) > 1:
                raise serializers.ValidationError({"choices": "السؤال ده له إجابة صحيحة واحدة."})
        if t == "short" and not a.get("correct_text", getattr(self.instance, "correct_text", "")):
            raise serializers.ValidationError({"correct_text": "اكتب الإجابات المقبولة."})
        return a

    @transaction.atomic
    def create(self, data):
        choices = data.pop("choices", [])
        q = Question.objects.create(**data)
        Choice.objects.bulk_create([Choice(question=q, **{k: v for k, v in c.items() if k != "id"}) for c in choices])
        return q

    @transaction.atomic
    def update(self, inst, data):
        choices = data.pop("choices", None)
        inst = super().update(inst, data)
        if choices is not None:
            inst.choices.all().delete()
            Choice.objects.bulk_create([Choice(question=inst, **{k: v for k, v in c.items() if k != "id"}) for c in choices])
        return inst


class QuizSerializer(serializers.ModelSerializer):
    questions_count = serializers.IntegerField(source="questions.count", read_only=True)
    total_points = serializers.SerializerMethodField()

    class Meta:
        model = Quiz
        fields = ["id", "kind", "title", "description", "subject", "grade", "course", "session", "time_limit_minutes",
                  "pass_percent", "max_attempts", "shuffle_questions", "show_answers_after_submit", "available_from",
                  "available_until", "is_published", "is_public", "questions_count", "total_points", "created_at"]

    def get_total_points(self, obj) -> float:
        return float(sum(q.points for q in obj.questions.all()))


class QuizDetailTeacherSerializer(QuizSerializer):
    questions = QuestionWriteSerializer(many=True, read_only=True)

    class Meta(QuizSerializer.Meta):
        fields = QuizSerializer.Meta.fields + ["questions"]


class AssignSerializer(serializers.Serializer):
    student_ids = serializers.PrimaryKeyRelatedField(queryset=User.objects.filter(role=Roles.STUDENT), many=True)
    due_at = serializers.DateTimeField(required=False, allow_null=True)


# ---------------- Student (solving) ----------------
class ChoicePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ["id", "text"]


class QuestionPublicSerializer(serializers.ModelSerializer):
    choices = ChoicePublicSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ["id", "type", "text", "image", "points", "choices"]


class StudentQuizSerializer(QuizSerializer):
    due_at = serializers.SerializerMethodField()
    my_attempts = serializers.SerializerMethodField()
    best_score = serializers.SerializerMethodField()
    owner = UserMiniSerializer(read_only=True)

    class Meta(QuizSerializer.Meta):
        fields = ["id", "kind", "title", "description", "subject", "course", "owner", "time_limit_minutes",
                  "pass_percent", "max_attempts", "available_from", "available_until", "questions_count",
                  "total_points", "due_at", "my_attempts", "best_score"]

    def _student(self):
        return self.context["request"].user

    @extend_schema_field(serializers.DateTimeField(allow_null=True))
    def get_due_at(self, obj):
        a = obj.assignments.filter(student=self._student()).first()
        return a.due_at if a else None

    def get_my_attempts(self, obj) -> int:
        return obj.attempts.filter(student=self._student()).count()

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_best_score(self, obj):
        best = obj.attempts.filter(student=self._student(), status="graded").order_by("-score").first()
        return float(best.score) if best else None


class AnswerSubmitSerializer(serializers.Serializer):
    question = serializers.IntegerField()
    selected_choices = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    text_answer = serializers.CharField(required=False, allow_blank=True, default="")
    file = serializers.FileField(required=False, allow_null=True)


class AnswerResultSerializer(serializers.ModelSerializer):
    selected_choices = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    correct_choices = serializers.SerializerMethodField()
    explanation = serializers.CharField(source="question.explanation", read_only=True)

    class Meta:
        model = Answer
        fields = ["id", "question", "selected_choices", "text_answer", "file", "is_correct", "points_awarded",
                  "feedback", "correct_choices", "explanation"]

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_correct_choices(self, obj):
        return list(obj.question.choices.filter(is_correct=True).values_list("id", flat=True))


class AttemptSerializer(serializers.ModelSerializer):
    quiz = StudentQuizSerializer(read_only=True)
    student = UserMiniSerializer(read_only=True)
    percent = serializers.FloatField(read_only=True)
    passed = serializers.BooleanField(read_only=True)
    questions = serializers.SerializerMethodField()
    answers = serializers.SerializerMethodField()
    remaining_seconds = serializers.SerializerMethodField()

    class Meta:
        model = Attempt
        fields = ["id", "quiz", "student", "status", "started_at", "expires_at", "remaining_seconds", "submitted_at",
                  "score", "max_score", "percent", "passed", "teacher_feedback", "questions", "answers"]

    @extend_schema_field(QuestionPublicSerializer(many=True))
    def get_questions(self, obj):
        qs = {q.id: q for q in obj.quiz.questions.prefetch_related("choices")}
        ordered = [qs[i] for i in obj.question_order if i in qs] or list(qs.values())
        return QuestionPublicSerializer(ordered, many=True, context=self.context).data

    @extend_schema_field(AnswerResultSerializer(many=True))
    def get_answers(self, obj):
        user = self.context["request"].user
        reveal = obj.status != "in_progress" and (obj.quiz.show_answers_after_submit or user.id != obj.student_id)
        if obj.status == "in_progress":
            # نرجّع اللي اتحفظ بس من غير تصحيح
            return [{"question": a.question_id, "selected_choices": list(a.selected_choices.values_list("id", flat=True)),
                     "text_answer": a.text_answer} for a in obj.answers.all()]
        data = AnswerResultSerializer(obj.answers.select_related("question"), many=True, context=self.context).data
        if not reveal:
            for d in data:
                d.pop("correct_choices", None)
                d.pop("explanation", None)
        return data

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_remaining_seconds(self, obj):
        from django.utils import timezone
        if obj.status != "in_progress" or not obj.expires_at:
            return None
        return max(int((obj.expires_at - timezone.now()).total_seconds()), 0)


class AttemptListSerializer(serializers.ModelSerializer):
    quiz_title = serializers.CharField(source="quiz.title", read_only=True)
    quiz_kind = serializers.CharField(source="quiz.kind", read_only=True)
    student = UserMiniSerializer(read_only=True)
    percent = serializers.FloatField(read_only=True)

    class Meta:
        model = Attempt
        fields = ["id", "quiz", "quiz_title", "quiz_kind", "student", "status", "score", "max_score", "percent",
                  "started_at", "submitted_at"]


class AttemptGradeItemSerializer(serializers.Serializer):
    answer_id = serializers.IntegerField()
    points_awarded = serializers.DecimalField(max_digits=6, decimal_places=2, min_value=Decimal("0"))
    feedback = serializers.CharField(required=False, allow_blank=True)


class AttemptGradeSerializer(serializers.Serializer):
    answers = AttemptGradeItemSerializer(many=True)
    teacher_feedback = serializers.CharField(required=False, allow_blank=True)
