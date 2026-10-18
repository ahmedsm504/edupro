from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel

User = settings.AUTH_USER_MODEL


class Quiz(TimeStampedModel):
    """واجب أو اختبار قصير أو امتحان. ممكن يتربط بكورس/درس، أو يتبعت لطلاب معينين."""
    KINDS = [("homework", "واجب"), ("quiz", "اختبار قصير"), ("exam", "امتحان")]
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quizzes")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT, related_name="quizzes")
    grade = models.ForeignKey("catalog.Grade", null=True, blank=True, on_delete=models.SET_NULL)
    course = models.ForeignKey("courses.Course", null=True, blank=True, on_delete=models.CASCADE, related_name="quizzes",
                               help_text="لو مربوط بكورس: أي مشترك في الكورس يقدر يحله")
    session = models.ForeignKey("tutoring.Session", null=True, blank=True, on_delete=models.SET_NULL, related_name="quizzes",
                                help_text="واجب مرتبط بحصة")
    kind = models.CharField(max_length=10, choices=KINDS, default="quiz")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    time_limit_minutes = models.PositiveIntegerField(null=True, blank=True, help_text="فاضي = بدون وقت")
    pass_percent = models.PositiveSmallIntegerField(default=50)
    max_attempts = models.PositiveSmallIntegerField(default=1, help_text="0 = غير محدود")
    shuffle_questions = models.BooleanField(default=False)
    show_answers_after_submit = models.BooleanField(default=True)
    available_from = models.DateTimeField(null=True, blank=True)
    available_until = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    is_public = models.BooleanField(default=False, help_text="متاح لأي طالب (بنك أسئلة/امتحانات تجريبية)")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Question(TimeStampedModel):
    TYPES = [
        ("single", "اختيار من متعدد (إجابة واحدة)"),
        ("multiple", "اختيار من متعدد (أكثر من إجابة)"),
        ("true_false", "صح وغلط"),
        ("short", "إجابة قصيرة (تصحيح تلقائي بالمطابقة)"),
        ("essay", "مقالي (تصحيح يدوي)"),
        ("file", "رفع ملف/صورة الحل (تصحيح يدوي)"),
    ]
    AUTO = ("single", "multiple", "true_false", "short")

    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="questions")
    type = models.CharField(max_length=10, choices=TYPES, default="single")
    text = models.TextField()
    image = models.ImageField(upload_to="questions/", blank=True, null=True)
    points = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    correct_text = models.CharField(max_length=300, blank=True, help_text="للأسئلة القصيرة: الإجابات الصحيحة مفصولة بـ |")
    explanation = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class QuizAssignment(TimeStampedModel):
    """إرسال واجب/امتحان لطالب معين بميعاد تسليم."""
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="assignments")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="quiz_assignments")
    due_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("quiz", "student")]


class Attempt(TimeStampedModel):
    STATUS = [("in_progress", "جاري الحل"), ("submitted", "في انتظار التصحيح"), ("graded", "تم التصحيح")]
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name="attempts")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attempts")
    status = models.CharField(max_length=15, choices=STATUS, default="in_progress")
    started_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    max_score = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    question_order = models.JSONField(default=list, blank=True)
    teacher_feedback = models.TextField(blank=True)

    class Meta:
        ordering = ["-started_at"]

    @property
    def percent(self):
        return round(float(self.score) * 100 / float(self.max_score), 1) if self.max_score else 0

    @property
    def passed(self):
        return self.status == "graded" and self.percent >= self.quiz.pass_percent


class Answer(TimeStampedModel):
    attempt = models.ForeignKey(Attempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="+")
    selected_choices = models.ManyToManyField(Choice, blank=True)
    text_answer = models.TextField(blank=True)
    file = models.FileField(upload_to="answers/", blank=True, null=True)
    is_correct = models.BooleanField(null=True)
    points_awarded = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = [("attempt", "question")]
