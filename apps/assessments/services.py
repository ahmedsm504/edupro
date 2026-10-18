import random
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from apps.core.exceptions import BusinessError
from apps.core.permissions import Roles

from .models import Answer, Attempt, Question, Quiz


def quizzes_available_to(student):
    from apps.courses.models import Enrollment
    course_ids = Enrollment.objects.filter(student=student).values_list("course_id", flat=True)
    return Quiz.objects.filter(is_published=True).filter(
        Q(assignments__student=student) | Q(course_id__in=course_ids) | Q(is_public=True)
    ).distinct()


def can_access(student, quiz):
    return quizzes_available_to(student).filter(pk=quiz.pk).exists()


def start_attempt(student, quiz: Quiz):
    from apps.courses.services import quiz_gate
    msg = quiz_gate(student, quiz)  # كويز درس/امتحان وحدة: لازم الدرس يكون مفتوح له
    if msg:
        raise BusinessError(msg, code="quiz_locked", status_code=403)
    if not can_access(student, quiz):
        raise BusinessError("الاختبار ده مش متاح لك.", code="quiz_not_available", status_code=403)
    now = timezone.now()
    if quiz.available_from and now < quiz.available_from:
        raise BusinessError("الاختبار لسه مبدأش.", code="quiz_not_open")
    if quiz.available_until and now > quiz.available_until:
        raise BusinessError("ميعاد الاختبار خلص.", code="quiz_closed")
    current = quiz.attempts.filter(student=student, status="in_progress").first()
    if current:
        if current.expires_at and current.expires_at < now:
            submit_attempt(current)
        else:
            return current
    done = quiz.attempts.filter(student=student).exclude(status="in_progress").count()
    if quiz.max_attempts and done >= quiz.max_attempts:
        raise BusinessError("خلصت عدد المحاولات المسموحة.", code="max_attempts_reached")
    ids = list(quiz.questions.values_list("id", flat=True))
    if quiz.shuffle_questions:
        random.shuffle(ids)
    return Attempt.objects.create(
        quiz=quiz, student=student, question_order=ids,
        expires_at=now + timezone.timedelta(minutes=quiz.time_limit_minutes) if quiz.time_limit_minutes else None,
        max_score=sum((q.points for q in quiz.questions.all()), Decimal(0)),
    )


def _grade_answer(ans: Answer):
    q = ans.question
    if q.type in ("single", "multiple", "true_false"):
        correct = set(q.choices.filter(is_correct=True).values_list("id", flat=True))
        chosen = set(ans.selected_choices.values_list("id", flat=True))
        ans.is_correct = bool(chosen) and chosen == correct
        ans.points_awarded = q.points if ans.is_correct else Decimal(0)
    elif q.type == "short":
        accepted = [x.strip().lower() for x in q.correct_text.split("|") if x.strip()]
        ans.is_correct = ans.text_answer.strip().lower() in accepted
        ans.points_awarded = q.points if ans.is_correct else Decimal(0)
    else:
        ans.is_correct = None
        ans.points_awarded = None  # يدوي
    ans.save()


def submit_attempt(attempt: Attempt):
    if attempt.status != "in_progress":
        raise BusinessError("المحاولة اتسلمت قبل كده.", code="already_submitted")
    needs_manual = False
    for q in attempt.quiz.questions.all():
        ans, _ = Answer.objects.get_or_create(attempt=attempt, question=q)
        _grade_answer(ans)
        if q.type not in Question.AUTO:
            needs_manual = True
    attempt.submitted_at = timezone.now()
    attempt.score = sum((a.points_awarded or 0 for a in attempt.answers.all()), Decimal(0))
    attempt.status = "submitted" if needs_manual else "graded"
    attempt.save()
    from apps.notifications.services import notify
    if needs_manual:
        notify(attempt.quiz.owner, "attempt_needs_grading", "تسليم محتاج تصحيح",
               f"{attempt.student.full_name} — {attempt.quiz.title}", {"screen": "attempt", "id": attempt.id})
    else:
        _notify_result(attempt)
        _course_hook(attempt)
    return attempt


def _course_hook(attempt):
    from apps.courses.services import on_quiz_result
    on_quiz_result(attempt)


def _notify_result(attempt):
    from apps.notifications.services import notify
    payload = {"screen": "attempt", "id": attempt.id}
    msg = f"{attempt.quiz.title}: {attempt.score}/{attempt.max_score}"
    notify(attempt.student, "quiz_graded", "نتيجتك ظهرت 📝", msg, payload)


def finalize_manual_grading(attempt: Attempt):
    if attempt.answers.filter(points_awarded__isnull=True).exists():
        return attempt
    attempt.score = sum((a.points_awarded for a in attempt.answers.all()), Decimal(0))
    attempt.status = "graded"
    attempt.save()
    _notify_result(attempt)
    _course_hook(attempt)
    return attempt


def can_manage_quiz(user, quiz):
    return user.role in Roles.STAFF or user.is_superuser or quiz.owner_id == user.id
