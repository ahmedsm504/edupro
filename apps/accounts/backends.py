from django.contrib.auth.backends import ModelBackend

from .models import User
from .utils import normalize_phone


class PhoneOrEmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, phone=None, **kwargs):
        identifier = (phone or username or kwargs.get("identifier") or "").strip()
        if not identifier or not password:
            return None
        if "@" in identifier:
            user = User.objects.filter(email__iexact=identifier).first()
        else:
            # اسم مستخدم (زي teacher1) أو رقم موبايل
            user = (User.objects.filter(username__iexact=identifier).first()
                    or User.objects.filter(phone=normalize_phone(identifier)).first())
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
