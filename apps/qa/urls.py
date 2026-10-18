from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("qa/questions", v.QuestionViewSet, basename="qa-questions")
router.register("qa/answers", v.AnswerViewSet, basename="qa-answers")

urlpatterns = [
    path("qa/moderation/", v.ModerationView.as_view()),
    path("qa/stats/", v.QAStatsView.as_view()),
    path("", include(router.urls)),
]
