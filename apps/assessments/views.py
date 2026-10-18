from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, parsers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.models import schema_safe
from apps.core.exceptions import BusinessError
from apps.core.permissions import IsTeacherOrStaff, Roles
from apps.notifications.services import notify

from . import serializers as s
from . import services
from .models import Answer, Attempt, Question, Quiz, QuizAssignment


@extend_schema_view(list=extend_schema(summary="اختباراتي/واجباتي كمدرس (الإدارة تشوف الكل)"))
@extend_schema(tags=["Quizzes - Teacher"])
@schema_safe(Quiz)
class QuizManageViewSet(viewsets.ModelViewSet):
    permission_classes = [IsTeacherOrStaff]
    filterset_fields = ["kind", "subject", "course", "is_published", "session"]
    search_fields = ["title"]

    def get_queryset(self):
        u = self.request.user
        qs = Quiz.objects.prefetch_related("questions")
        return qs if u.role in Roles.STAFF else qs.filter(owner=u)

    def get_serializer_class(self):
        return s.QuizDetailTeacherSerializer if self.action == "retrieve" else s.QuizSerializer

    def perform_create(self, ser):
        ser.save(owner=self.request.user)

    @extend_schema(summary="نشر الاختبار", request=None, responses=s.QuizSerializer)
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        q = self.get_object()
        if not q.questions.exists():
            raise BusinessError("ضيف أسئلة الأول.", code="empty_quiz")
        q.is_published = True
        q.save(update_fields=["is_published"])
        return Response(s.QuizSerializer(q).data)

    @extend_schema(summary="إرسال الواجب/الامتحان لطلاب معينين", request=s.AssignSerializer, responses={200: None})
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        quiz = self.get_object()
        ser = s.AssignSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        if request.user.role == Roles.TEACHER:
            from apps.tutoring.models import Subscription
            mine = set(Subscription.objects.filter(teacher=request.user).values_list("student_id", flat=True))
            bad = [st.id for st in ser.validated_data["student_ids"] if st.id not in mine]
            if bad:
                raise BusinessError("فيه طلاب مش من طلابك.", code="not_your_students")
        due = ser.validated_data.get("due_at")
        for st in ser.validated_data["student_ids"]:
            QuizAssignment.objects.update_or_create(quiz=quiz, student=st, defaults={"due_at": due})
            label = {"homework": "واجب جديد", "quiz": "اختبار جديد", "exam": "امتحان جديد"}[quiz.kind]
            notify(st, "quiz_assigned", f"{label} 📚", quiz.title, {"screen": "quiz", "id": quiz.id})
        if not quiz.is_published and quiz.questions.exists():
            quiz.is_published = True
            quiz.save(update_fields=["is_published"])
        return Response({"assigned": len(ser.validated_data["student_ids"])})

    @extend_schema(summary="محاولات الطلاب على الاختبار", responses=s.AttemptListSerializer(many=True))
    @action(detail=True, methods=["get"])
    def attempts(self, request, pk=None):
        quiz = self.get_object()
        page = self.paginate_queryset(quiz.attempts.select_related("student", "quiz"))
        return self.get_paginated_response(s.AttemptListSerializer(page, many=True).data)


@extend_schema(tags=["Quizzes - Teacher"])
@schema_safe(Question)
class QuestionViewSet(viewsets.ModelViewSet):
    """الأسئلة مع الاختيارات (choices) في نفس الطلب. الصورة بالـ multipart."""
    permission_classes = [IsTeacherOrStaff]
    serializer_class = s.QuestionWriteSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    filterset_fields = ["quiz"]
    pagination_class = None

    def get_queryset(self):
        u = self.request.user
        qs = Question.objects.prefetch_related("choices")
        return qs if u.role in Roles.STAFF else qs.filter(quiz__owner=u)

    def perform_create(self, ser):
        if not services.can_manage_quiz(self.request.user, ser.validated_data["quiz"]):
            raise BusinessError("الاختبار ده مش بتاعك.", code="forbidden", status_code=403)
        ser.save()


@extend_schema_view(list=extend_schema(summary="الواجبات والاختبارات المتاحة لي (طالب)"))
@extend_schema(tags=["Quizzes - Student"])
@schema_safe(Quiz)
class StudentQuizViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = s.StudentQuizSerializer
    filterset_fields = ["kind", "subject", "course"]

    def get_queryset(self):
        if self.request.user.role != Roles.STUDENT:
            return Quiz.objects.none()
        return services.quizzes_available_to(self.request.user).select_related("owner")

    @extend_schema(summary="بدء محاولة (أو استكمال المحاولة المفتوحة) — بيرجع الأسئلة", request=None, responses=s.AttemptSerializer)
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        quiz = get_object_or_404(Quiz, pk=pk)
        attempt = services.start_attempt(request.user, quiz)
        return Response(s.AttemptSerializer(attempt, context={"request": request}).data)


@extend_schema_view(list=extend_schema(summary="المحاولات/النتائج (الطالب: بتاعته، المدرس: لطلابه، الإدارة: الكل)"))
@extend_schema(tags=["Quizzes - Student"])
@schema_safe(Attempt)
class AttemptViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    filterset_fields = ["status", "quiz", "student"]

    def get_serializer_class(self):
        return s.AttemptSerializer if self.action != "list" else s.AttemptListSerializer

    def get_queryset(self):
        u = self.request.user
        qs = Attempt.objects.select_related("quiz", "student")
        if u.role in Roles.STAFF or u.is_superuser:
            return qs
        if u.role == Roles.TEACHER:
            return qs.filter(quiz__owner=u)
        return qs.filter(student=u)

    def _own_open(self):
        att = self.get_object()
        if att.student_id != self.request.user.id:
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        if att.status != "in_progress":
            raise BusinessError("المحاولة اتسلمت.", code="already_submitted")
        if att.expires_at and att.expires_at < timezone.now():
            services.submit_attempt(att)
            raise BusinessError("الوقت خلص واتسلمت المحاولة تلقائياً.", code="time_over")
        return att

    @extend_schema(summary="حفظ إجابة سؤال (ينفع تتبعت أكتر من مرة)", request=s.AnswerSubmitSerializer, responses={200: None})
    @action(detail=True, methods=["post"])
    def answer(self, request, pk=None):
        att = self._own_open()
        ser = s.AnswerSubmitSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        q = get_object_or_404(Question, pk=d["question"], quiz=att.quiz)
        ans, _ = Answer.objects.get_or_create(attempt=att, question=q)
        ans.text_answer = d.get("text_answer", "")
        if d.get("file"):
            ans.file = d["file"]
        ans.save()
        ans.selected_choices.set(q.choices.filter(id__in=d.get("selected_choices", [])))
        return Response({"saved": True, "question": q.id})

    @extend_schema(summary="تسليم المحاولة والتصحيح التلقائي", request=None, responses=s.AttemptSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        att = self.get_object()
        if att.student_id != request.user.id:
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        services.submit_attempt(att)
        return Response(s.AttemptSerializer(att, context={"request": request}).data)

    @extend_schema(summary="(مدرس) تصحيح الأسئلة المقالية/الملفات", request=s.AttemptGradeSerializer, responses=s.AttemptSerializer)
    @action(detail=True, methods=["post"])
    def grade(self, request, pk=None):
        att = self.get_object()
        if not services.can_manage_quiz(request.user, att.quiz):
            raise BusinessError("غير مسموح.", code="forbidden", status_code=403)
        if att.status == "in_progress":
            raise BusinessError("الطالب لسه مسلمش.", code="not_submitted")
        ser = s.AttemptGradeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        for item in ser.validated_data["answers"]:
            ans = get_object_or_404(Answer, pk=item["answer_id"], attempt=att)
            if item["points_awarded"] > ans.question.points:
                raise BusinessError("الدرجة أكبر من درجة السؤال.", code="invalid_points")
            ans.points_awarded = item["points_awarded"]
            ans.is_correct = item["points_awarded"] >= ans.question.points
            ans.feedback = item.get("feedback", "")
            ans.save()
        if "teacher_feedback" in ser.validated_data:
            att.teacher_feedback = ser.validated_data["teacher_feedback"]
            att.save(update_fields=["teacher_feedback"])
        att.status = "submitted" if att.status == "graded" else att.status
        services.finalize_manual_grading(att)
        return Response(s.AttemptSerializer(att, context={"request": request}).data)
