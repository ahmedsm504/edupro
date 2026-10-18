"""
بنك الأسئلة والأجوبة (Q&A):
- الطالب يسأل في مادة معينة، والمدرسين (وأي حد مسجل) يجاوبوا.
- صاحب السؤال (أو الإدارة) يختار "أفضل إجابة".
- تصويت لأعلى/لأسفل على الأسئلة والإجابات.
- فلتر منع التواصل خارج المنصة بيشتغل هنا كمان: أي محتوى فيه أرقام/لينكات بيتعلّق للمراجعة.
- كل سؤال ليه صفحة عامة بـ schema.org/QAPage عشان يظهر في جوجل.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel, unique_slug

User = settings.AUTH_USER_MODEL


class Question(TimeStampedModel):
    MODERATION = [("approved", "منشور"), ("pending", "مستني مراجعة"), ("rejected", "مرفوض")]

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="questions")
    subject = models.ForeignKey("catalog.Subject", on_delete=models.PROTECT, related_name="questions")
    grade = models.ForeignKey("catalog.Grade", null=True, blank=True, on_delete=models.SET_NULL, related_name="questions")
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=230, unique=True, allow_unicode=True, blank=True)
    body = models.TextField(blank=True, help_text="نص عادي — الأسطر الفاضية بتعمل فقرات و ```كود```")
    image = models.ImageField(upload_to="qa/", blank=True, null=True)
    tags = models.ManyToManyField("seo.Tag", blank=True, related_name="questions")
    moderation = models.CharField(max_length=10, choices=MODERATION, default="approved", db_index=True)
    flag_reasons = models.JSONField(default=list, blank=True)
    accepted_answer = models.OneToOneField("Answer", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_closed = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    score = models.IntegerField(default=0)
    answers_count = models.PositiveIntegerField(default=0)
    views_count = models.PositiveIntegerField(default=0)
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-last_activity_at"]

    def save(self, *a, **kw):
        if not self.slug:
            self.slug = unique_slug(self, self.title, max_length=200)
        super().save(*a, **kw)

    @property
    def is_answered(self):
        return self.answers_count > 0

    @property
    def is_indexable(self):
        """جوجل مش بيحب الصفحات الفاضية: السؤال بيدخل الـ index بس لما يكون ليه إجابة منشورة."""
        return self.moderation == "approved" and self.answers_count > 0

    def get_absolute_url(self):
        return f"/questions/{self.slug}/"

    def __str__(self):
        return self.title


class Answer(TimeStampedModel):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="answers")
    body = models.TextField()
    image = models.ImageField(upload_to="qa/", blank=True, null=True)
    moderation = models.CharField(max_length=10, choices=Question.MODERATION, default="approved", db_index=True)
    flag_reasons = models.JSONField(default=list, blank=True)
    score = models.IntegerField(default=0)

    class Meta:
        ordering = ["-score", "created_at"]

    @property
    def is_accepted(self):
        return self.question.accepted_answer_id == self.id

    def __str__(self):
        return f"إجابة على: {self.question}"


class Vote(TimeStampedModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="qa_votes")
    question = models.ForeignKey(Question, null=True, blank=True, on_delete=models.CASCADE, related_name="votes")
    answer = models.ForeignKey(Answer, null=True, blank=True, on_delete=models.CASCADE, related_name="votes")
    value = models.SmallIntegerField(choices=[(1, "up"), (-1, "down")])

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "question"], condition=models.Q(answer__isnull=True), name="uniq_vote_question"),
            models.UniqueConstraint(fields=["user", "answer"], condition=models.Q(answer__isnull=False), name="uniq_vote_answer"),
        ]
