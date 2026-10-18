from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from apps.core.contact_filter import scan
from apps.core.exceptions import BusinessError
from apps.core.permissions import Roles
from apps.notifications.services import notify, notify_staff

from .models import Answer, Question, Vote


def is_staff(user):
    return user.is_authenticated and (user.role in Roles.STAFF or user.is_superuser)


def _moderate(user, *texts):
    """الإدارة: منشور على طول. غير كده لو فيه أرقام/لينكات → مستني مراجعة."""
    if is_staff(user):
        return "approved", []
    reasons = []
    for t in texts:
        reasons += scan(t or "")[1]
    return ("pending" if reasons else "approved"), sorted(set(reasons))


def visible_questions(user):
    qs = Question.objects.select_related("author", "subject", "grade").prefetch_related("tags")
    if is_staff(user):
        return qs
    if user.is_authenticated:
        from django.db.models import Q
        return qs.filter(Q(moderation="approved") | Q(author=user))
    return qs.filter(moderation="approved")


def visible_answers(user, question):
    qs = question.answers.select_related("author", "author__teacher_profile")
    if is_staff(user):
        return qs
    if user.is_authenticated:
        from django.db.models import Q
        return qs.filter(Q(moderation="approved") | Q(author=user))
    return qs.filter(moderation="approved")


def recount(question):
    question.answers_count = question.answers.filter(moderation="approved").count()
    question.save(update_fields=["answers_count"])


@transaction.atomic
def ask(user, data, tags=()):
    mod, reasons = _moderate(user, data.get("title"), data.get("body"))
    q = Question.objects.create(author=user, moderation=mod, flag_reasons=reasons, **data)
    if tags:
        q.tags.set(tags)
    if mod == "pending":
        notify_staff("qa_flagged", "سؤال محتاج مراجعة", f"{user.full_name}: {q.title}", {"screen": "qa_moderation", "id": q.id})
    else:
        _notify_subject_teachers(q)
    return q


def _notify_subject_teachers(q):
    from apps.accounts.models import User
    teachers = User.objects.filter(role=Roles.TEACHER, is_active=True, teacher_profile__approval_status="approved",
                                   teacher_profile__subjects=q.subject).exclude(pk=q.author_id)[:30]
    for t in teachers:
        notify(t, "qa_new_question", f"سؤال جديد في {q.subject.name}", q.title, {"screen": "question", "slug": q.slug}, push=False)


@transaction.atomic
def answer(user, question, body, image=None):
    if question.is_closed:
        raise BusinessError("السؤال ده مقفول.", code="question_closed")
    if question.moderation != "approved" and not is_staff(user):
        raise BusinessError("السؤال لسه بيتراجع.", code="question_pending")
    mod, reasons = _moderate(user, body)
    a = Answer.objects.create(question=question, author=user, body=body, image=image, moderation=mod, flag_reasons=reasons)
    Question.objects.filter(pk=question.pk).update(last_activity_at=timezone.now())
    recount(question)
    if mod == "pending":
        notify_staff("qa_flagged", "إجابة محتاجة مراجعة", f"{user.full_name} على: {question.title}",
                     {"screen": "qa_moderation", "id": question.id})
    elif question.author_id != user.id:
        notify(question.author, "qa_new_answer", "فيه إجابة جديدة على سؤالك 💬",
               f"{user.full_name}: {question.title}", {"screen": "question", "slug": question.slug})
    return a


def accept(user, ans: Answer):
    q = ans.question
    if user.id != q.author_id and not is_staff(user):
        raise BusinessError("صاحب السؤال بس اللي يختار أفضل إجابة.", code="forbidden", status_code=403)
    if ans.moderation != "approved":
        raise BusinessError("الإجابة لسه بتتراجع.", code="answer_pending")
    q.accepted_answer = None if q.accepted_answer_id == ans.id else ans
    q.save(update_fields=["accepted_answer"])
    if q.accepted_answer_id and ans.author_id != user.id:
        notify(ans.author, "qa_answer_accepted", "إجابتك اتختارت أفضل إجابة ✅", q.title, {"screen": "question", "slug": q.slug})
    return q


@transaction.atomic
def vote(user, value, question=None, answer=None):
    if value not in (1, -1, 0):
        raise BusinessError("value لازم 1 أو -1 أو 0.", code="validation_error")
    target = answer or question
    if target.author_id == user.id:
        raise BusinessError("مينفعش تصوّت لنفسك.", code="self_vote")
    lookup = {"user": user, "answer": answer} if answer else {"user": user, "question": question, "answer": None}
    Vote.objects.filter(**lookup).delete()
    if value:
        Vote.objects.create(value=value, **lookup)
    agg = (Vote.objects.filter(answer=answer) if answer else Vote.objects.filter(question=question, answer=None)).aggregate(s=Sum("value"))
    target.score = agg["s"] or 0
    target.save(update_fields=["score"])
    return target.score


def my_vote(user, question=None, answer=None):
    if not user.is_authenticated:
        return 0
    v = Vote.objects.filter(user=user, answer=answer).first() if answer else \
        Vote.objects.filter(user=user, question=question, answer=None).first()
    return v.value if v else 0


def moderate(obj, action, staff_user):
    obj.moderation = {"approve": "approved", "reject": "rejected"}[action]
    obj.save(update_fields=["moderation"])
    if isinstance(obj, Answer):
        recount(obj.question)
        if action == "approve" and obj.question.author_id != obj.author_id:
            notify(obj.question.author, "qa_new_answer", "فيه إجابة جديدة على سؤالك 💬", obj.question.title,
                   {"screen": "question", "slug": obj.question.slug})
    elif action == "approve":
        _notify_subject_teachers(obj)
    notify(obj.author, "qa_moderated", "تمت مراجعة مشاركتك" if action == "approve" else "مشاركتك اترفضت",
           "اتنشرت ✅" if action == "approve" else "فيها بيانات تواصل أو مخالفة لسياسة المنصة",
           {"screen": "question", "slug": (obj.question if isinstance(obj, Answer) else obj).slug})


def bump_views(question):
    Question.objects.filter(pk=question.pk).update(views_count=F("views_count") + 1)
