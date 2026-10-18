from django.urls import path

from .views import DashboardView, TeacherHoursReportView

urlpatterns = [
    path("dashboard/", DashboardView.as_view()),
    path("admin/reports/teacher-hours/", TeacherHoursReportView.as_view()),
]
