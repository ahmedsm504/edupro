from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("courses", v.CourseViewSet, basename="courses")
router.register("my/enrollments", v.MyEnrollmentViewSet, basename="my-enrollments")
router.register("my/notes", v.MyNoteViewSet, basename="my-notes")
router.register("my/certificates", v.MyCertificateViewSet, basename="my-certificates")
router.register("instructor/courses", v.InstructorCourseViewSet, basename="instructor-courses")
router.register("instructor/sections", v.InstructorSectionViewSet, basename="instructor-sections")
router.register("instructor/lessons", v.InstructorLessonViewSet, basename="instructor-lessons")
from django.urls import path  # noqa: E402

urlpatterns = [path("courses/media/<str:token>/", v.course_media, name="course-media")] + router.urls
