from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("teacher/quizzes", v.QuizManageViewSet, basename="teacher-quizzes")
router.register("teacher/questions", v.QuestionViewSet, basename="teacher-questions")
router.register("quizzes", v.StudentQuizViewSet, basename="quizzes")
router.register("attempts", v.AttemptViewSet, basename="attempts")
urlpatterns = router.urls
