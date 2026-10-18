"""يضيف «البكالوريا المصرية» (المسارات الأربعة) والمواد الجديدة بتاعتها — آمن يتشغل كل مرة (start.sh).

النظام (قرارات وزارة التربية والتعليم):
- الصف الأول الثانوي: مواد مشتركة (عربي، تاريخ مصر، رياضيات، علوم متكاملة، فلسفة ومنطق، لغة أجنبية أولى، تربية دينية)
  + برمجة ولغة أجنبية تانية خارج المجموع.
- الصف الثاني: عربي + لغة أجنبية أولى + تاريخ، ومادة تخصص حسب المسار.
- الصف الثالث: تربية دينية + مادتين تخصص حسب المسار (مستوى رفيع).
المسارات: الطب وعلوم الحياة · الهندسة وعلوم الحاسب · الأعمال · الآداب والفنون.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

BAC = "البكالوريا المصرية"
COMMON_1 = ["arabic", "history", "math", "integrated-sciences", "philosophy", "english", "french", "religion", "programming-ai"]
CORE_2 = ["arabic", "english", "history"]
TRACKS = [
    # (اسم المسار, مواد تانية ثانوي (يختار واحدة), مواد تالتة ثانوي)
    ("مسار الطب وعلوم الحياة", ["physics", "math"], ["biology", "chemistry"]),
    ("مسار الهندسة وعلوم الحاسب", ["chemistry", "programming-ai"], ["math", "physics"]),
    ("مسار الأعمال", ["accounting", "business-admin"], ["economics", "math"]),
    ("مسار الآداب والفنون", ["psychology", "french"], ["geography", "statistics"]),
]
NEW_SUBJECTS = [
    # (slug, الاسم, اللون)
    ("integrated-sciences", "علوم متكاملة", "#0891B2"),
    ("programming-ai", "برمجة وذكاء اصطناعي", "#4F46E5"),
    ("accounting", "محاسبة", "#0F766E"),
    ("business-admin", "إدارة أعمال", "#9333EA"),
    ("economics", "اقتصاد", "#B45309"),
    ("statistics", "إحصاء", "#2563EB"),
    ("psychology", "علم نفس", "#DB2777"),
    ("religion", "تربية دينية", "#15803D"),
]


class Command(BaseCommand):
    help = "إضافة البكالوريا المصرية ومسارات التخصص (idempotent)"

    @transaction.atomic
    def handle(self, *args, **opts):
        from apps.catalog.models import Curriculum, Grade, Stage, Subject

        if not Subject.objects.exists():
            self.stdout.write("sync_curricula: مفيش مواد لسه — هتتعمل مع seed_showcase.")
            return
        cur, created = Curriculum.objects.get_or_create(name=BAC, defaults={"country": "EG", "order": 0})
        order = Subject.objects.order_by("-order").values_list("order", flat=True).first() or 0
        S = {s.slug: s for s in Subject.objects.all()}
        for slug, name, color in NEW_SUBJECTS:
            if slug not in S:
                order += 1
                S[slug] = Subject.objects.create(
                    name=name, slug=slug, name_en=slug, color=color, order=order,
                    description=f"حصص {name} أونلاين للثانوي (نظام البكالوريا المصرية) مع مدرسين متخصصين.",
                    meta_title=f"مدرس {name} أونلاين — بكالوريا")

        def grade(stage_name, st_order, grade_name, g_order):
            st, _ = Stage.objects.get_or_create(curriculum=cur, name=stage_name, defaults={"order": st_order})
            g, _ = Grade.objects.get_or_create(stage=st, name=grade_name, defaults={"order": g_order})
            return g

        def link(slugs, g):
            for sl in slugs:
                if sl in S:
                    S[sl].grades.add(g)

        g1 = grade("الصف الأول الثانوي", 0, "أولى ثانوي — بكالوريا", 1)
        link(COMMON_1, g1)
        for i, (track, sec2, sec3) in enumerate(TRACKS, 1):
            short = track.replace("مسار ", "")
            g2 = grade(track, i, f"تانية ثانوي — {short}", 2)
            g3 = grade(track, i, f"تالتة ثانوي — {short}", 3)
            link(CORE_2 + sec2, g2)
            link(["religion"] + sec3, g3)
        self.stdout.write(self.style.SUCCESS(
            f"sync_curricula: {BAC} {'اتضافت' if created else 'متحدّثة'} — {cur.stages.count()} مرحلة."))
