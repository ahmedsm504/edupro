from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("packages", v.PackageViewSet, basename="packages")
router.register("availability", v.AvailabilityViewSet, basename="availability")
router.register("subscriptions", v.SubscriptionViewSet, basename="subscriptions")
router.register("sessions", v.SessionViewSet, basename="sessions")
router.register("reschedule-requests", v.RescheduleRequestViewSet, basename="reschedule-requests")
router.register("trials", v.TrialRequestViewSet, basename="trials")
router.register("reviews", v.ReviewViewSet, basename="reviews")

urlpatterns = [
    path("teacher/students/", v.TeacherStudentsView.as_view()),
    path("", include(router.urls)),
]
