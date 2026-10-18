from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from . import views as v

router = DefaultRouter()
router.register("teachers", v.PublicTeacherViewSet, basename="public-teacher")
router.register("admin/users", v.AdminUserViewSet, basename="admin-users")

urlpatterns = [
    path("auth/register/", v.RegisterView.as_view()),
    path("auth/login/", v.LoginView.as_view()),
    path("auth/token/refresh/", TokenRefreshView.as_view()),
    path("auth/logout/", v.LogoutView.as_view()),
    path("auth/otp/send/", v.OTPSendView.as_view()),
    path("auth/verify-phone/", v.VerifyPhoneView.as_view()),
    path("auth/password/reset/", v.PasswordResetView.as_view()),
    path("auth/password/change/", v.PasswordChangeView.as_view()),
    path("me/", v.MeView.as_view()),
    path("me/teacher-profile/", v.MyTeacherProfileView.as_view()),
    path("me/student-profile/", v.MyStudentProfileView.as_view()),
    path("me/teacher-documents/", v.MyTeacherDocumentsView.as_view()),
    path("", include(router.urls)),
]
