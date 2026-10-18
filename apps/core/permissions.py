from rest_framework.permissions import BasePermission, SAFE_METHODS


class Roles:
    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    TEACHER = "teacher"
    STUDENT = "student"
    CHOICES = [
        (ADMIN, "مدير"),
        (SUPERVISOR, "مشرف"),
        (TEACHER, "مدرس"),
        (STUDENT, "طالب"),
    ]
    STAFF = (ADMIN, SUPERVISOR)


def _role(request):
    u = request.user
    return getattr(u, "role", None) if u and u.is_authenticated else None


class IsAdmin(BasePermission):
    message = "هذه العملية متاحة للإدارة فقط."

    def has_permission(self, request, view):
        return _role(request) == Roles.ADMIN or bool(request.user and request.user.is_superuser)


class IsStaffRole(BasePermission):
    """أدمن أو مشرف"""
    message = "هذه العملية متاحة للإدارة والمشرفين فقط."

    def has_permission(self, request, view):
        return _role(request) in Roles.STAFF or bool(request.user and request.user.is_superuser)


class IsTeacher(BasePermission):
    message = "هذه العملية متاحة للمدرسين فقط."

    def has_permission(self, request, view):
        u = request.user
        return _role(request) == Roles.TEACHER and hasattr(u, "teacher_profile") and u.teacher_profile.is_approved


class IsStudent(BasePermission):
    message = "هذه العملية متاحة للطلاب فقط."

    def has_permission(self, request, view):
        return _role(request) == Roles.STUDENT




class IsTeacherOrStaff(BasePermission):
    message = "غير مسموح."

    def has_permission(self, request, view):
        return IsTeacher().has_permission(request, view) or IsStaffRole().has_permission(request, view)


class ReadOnlyOrAdmin(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return IsAdmin().has_permission(request, view)
