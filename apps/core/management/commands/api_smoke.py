"""
فحص سريع لكل الـ APIs بكل الأدوار:
    python manage.py api_smoke            # كل الـ GET endpoints لكل دور + صفحات الموقع
    python manage.py api_smoke --verbose  # يطبع كل طلب

بيقرا مسارات الـ API من الـ OpenAPI schema، ولكل مسار فيه {id} أو {slug} بياخد أول عنصر من القائمة بتاعته.
أي رد 500 = مشكلة. الردود 403/404 طبيعية لما الدور مش مسموح له.
"""
import re
from collections import Counter

from django.core.management.base import BaseCommand
from django.test import Client
from django.test.utils import override_settings

ROLES = ["admin", "supervisor", "teacher1", "student1", "pending1"]
SKIP = ("/payments/paymob/webhook/",)


class Command(BaseCommand):
    help = "Hit every GET endpoint as every demo role and report failures"

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")

    @override_settings(ALLOWED_HOSTS=["*"])
    def handle(self, *args, **opts):
        import logging
        # الـ 403 هنا متوقعة (بنجرب كل endpoint بكل دور) — مش محتاجين سطر لكل واحدة
        logging.getLogger("django.request").setLevel(logging.ERROR)
        from drf_spectacular.generators import SchemaGenerator
        schema = SchemaGenerator().get_schema(request=None, public=True)
        paths = [p for p, ops in schema["paths"].items() if "get" in ops and not p.startswith(SKIP)]
        from django.core.cache import cache
        cache.clear()
        anon = Client()
        failures, total = [], Counter()

        for url in ["/", "/login/", "/app/", "/subjects/", "/subjects/math/", "/teachers/", "/courses/", "/blog/", "/sitemap.xml", "/robots.txt", "/api/docs/", "/api/schema/"]:
            r = anon.get(url)
            total[r.status_code] += 1
            if r.status_code >= 400:
                failures.append(("anon", url, r.status_code))

        for user in ROLES:
            c = Client()
            r = c.post("/api/v1/auth/login/", {"identifier": user, "password": "admin12345"}, content_type="application/json")
            if r.status_code != 200:
                self.stdout.write(self.style.ERROR(f"login failed for {user}: {r.status_code}"))
                failures.append((user, "login", r.status_code))
                continue
            h = {"HTTP_AUTHORIZATION": f"Bearer {r.json()['access']}"}
            ids = {}
            ok = 0
            for p in sorted(paths, key=lambda x: x.count("{")):
                url = p
                params = re.findall(r"\{(\w+)\}", p)
                if params:
                    base = p.split("{")[0]
                    if base not in ids:
                        lr = c.get(base, **h)
                        data = lr.json() if lr.status_code == 200 else None
                        items = data.get("results", []) if isinstance(data, dict) else (data or [])
                        ids[base] = items[0] if items and isinstance(items[0], dict) else None
                    item = ids[base]
                    if not item:
                        continue
                    for prm in params:
                        val = item.get(prm) or item.get("id") if prm in ("id",) else item.get(prm) or item.get("slug") or item.get("id")
                        if prm == "lesson_id":
                            lessons = [l for s in (c.get(f"/api/v1/courses/{item.get('slug')}/", **h).json().get("sections", [])) for l in s["lessons"]]
                            val = lessons[0]["id"] if lessons else None
                        if val is None:
                            url = None
                            break
                        url = url.replace("{" + prm + "}", str(val))
                    if not url:
                        continue
                r = c.get(url, **h)
                total[r.status_code] += 1
                if opts["verbose"]:
                    self.stdout.write(f"  {user:<11} {r.status_code} {url}")
                if r.status_code >= 500:
                    failures.append((user, url, r.status_code))
                elif r.status_code < 300:
                    ok += 1
            self.stdout.write(f"{user:<11} ✓ {ok} endpoint شغالين")

        self.stdout.write(f"\nإجمالي الطلبات حسب الحالة: {dict(sorted(total.items()))}")
        if failures:
            self.stdout.write(self.style.ERROR(f"\n{len(failures)} مشكلة:"))
            for f in failures:
                self.stdout.write(f"  {f}")
        else:
            self.stdout.write(self.style.SUCCESS("كل الـ APIs شغالة ✅ (مفيش ولا رد 500)"))
