"""يعمل حساب الأدمن الأساسي لو مش موجود (بيتشغل مع كل نشر من start.sh).

- لو فيه أدمن باسم المستخدم ده خلاص مش بيلمسه، فلو غيّرت كلمة السر من الموقع هتفضل زي ما هي.
- كلمة السر: من المتغير ADMIN_PASSWORD لو متحط، وإلا بيستخدم البصمة (hash) المحفوظة هنا.
  البصمة مش كلمة السر نفسها، بس برضه غيّر كلمة السر من صفحتك بعد أول دخول.
"""
import os

from django.core.management.base import BaseCommand
from django.db.models import Q

# بصمة كلمة السر المتفق عليها لأول دخول (pbkdf2) — مش النص نفسه
DEFAULT_PASSWORD_HASH = "pbkdf2_sha256$1500000$P4sQXTNSs9stsFVSjTKUGp$MGVCOTNeGv1FYpF/P1N+HzemdvNMhvxide6vE95imNU="


class Command(BaseCommand):
    help = "إنشاء حساب الأدمن الأساسي لو مش موجود"

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("ADMIN_USERNAME", "admin"))
        parser.add_argument("--name", default=os.environ.get("ADMIN_FULL_NAME", "مدير المنصة"))

    def handle(self, *args, **opts):
        from apps.accounts.models import User
        from apps.core.permissions import Roles

        username = opts["username"]
        if User.objects.filter(Q(username=username) | Q(phone=username)).exists():
            self.stdout.write(f"ensure_admin: «{username}» موجود بالفعل.")
            return
        user = User(username=username, phone=username, full_name=opts["name"], role=Roles.ADMIN,
                    is_staff=True, is_superuser=True, email=os.environ.get("ADMIN_EMAIL") or None)
        raw = os.environ.get("ADMIN_PASSWORD")
        if raw:
            user.set_password(raw)
        else:
            user.password = DEFAULT_PASSWORD_HASH
        user.save()
        self.stdout.write(self.style.SUCCESS(f"ensure_admin: اتعمل حساب الأدمن «{username}»."))
