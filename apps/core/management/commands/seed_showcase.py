"""محتوى بداية حقيقي للموقع المنشور (من غير حسابات أو تقييمات وهمية).

بيعمل:
- المناهج والمراحل والصفوف والمواد والباقات (لو مفيش مواد خالص).
- حساب تحريري «فريق EduPro التعليمي» (من غير كلمة سر — مبيدخلش) يبقى كاتب المقالات وبنك الأسئلة.
- تصنيفات ومقالات المدونة بصور غلاف، وأسئلة وإجابات تعليمية، وأسئلة شائعة، وصفحات من نحن/الشروط/الخصوصية.

مش بيعمل مدرسين ولا طلاب ولا آراء عملاء ولا تقييمات — دي لازم تيجي من ناس حقيقيين.

الاستخدام:
    python manage.py seed_showcase             # بيكمّل اللي ناقص بس
    python manage.py seed_showcase --if-empty  # يشتغل بس لو مفيش مقالات خالص (ده اللي في start.sh)
"""
import datetime as dt
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

COVERS = Path(settings.BASE_DIR) / "demo_assets" / "covers"
INLINE = Path(settings.BASE_DIR) / "demo_assets" / "inline"
ARTICLES_VERSION = "v2"  # لما المحتوى يتحدّث: غيّر الرقم و start.sh هيحدّث مقالات الفريق مرة واحدة
EDITOR_USERNAME = "edupro-team"

COVER_FILES = ["math-plan.jpg", "quran-kids.jpg", "tajweed.jpg", "english-30-days.jpg",
               "organic-chemistry.jpg", "scratch-python.jpg", "pomodoro.jpg", "present-perfect.jpg"]
COVER_ALTS = ["رسم بياني لدالة تربيعية ومعادلات تفاضل وتكامل على سبورة", "هلال ونجوم فوق مصحف مفتوح",
              "زخرفة إسلامية على شكل نجمة ثمانية", "جدول 30 يوم لتعلم الإنجليزي",
              "حلقة بنزين ومعادلات كيمياء عضوية", "بلوكات سكراتش بجانب كود بايثون",
              "مؤقت بومودورو 25 دقيقة", "خط زمني يشرح المضارع التام"]

# إجابات للأسئلة اللي ملهاش إجابة في المحتوى الأساسي
EXTRA_ANSWERS = {
    "إيه الفرق بين التنفس والتنفس الخلوي؟":
        "التنفس (الخارجي) هو تبادل الغازات: بندخّل أكسجين ونطلّع ثاني أكسيد الكربون عن طريق الرئتين.\n\n"
        "التنفس الخلوي بيحصل جوه كل خلية في الميتوكوندريا: الجلوكوز بيتكسر بوجود الأكسجين ويطلع طاقة (ATP) + ثاني أكسيد الكربون + ماء.\n\n"
        "يعني التنفس الخارجي بيوصّل الأكسجين، والتنفس الخلوي هو اللي بيستخدمه فعلاً عشان يطلع طاقة.",
    "إزاي أحل معادلة من الدرجة التانية بالقانون العام؟":
        "لو المعادلة على الصورة ax² + bx + c = 0 يبقى:\n\nx = (-b ± √(b² - 4ac)) / 2a\n\n"
        "مثال: x² - 5x + 6 = 0 ← a = 1 و b = -5 و c = 6\n"
        "المميز = 25 - 24 = 1 ← x = (5 ± 1) / 2 ← x = 3 أو x = 2\n\n"
        "ابدأ دايماً بحساب المميز (b² - 4ac): لو موجب فيه حلين، لو صفر حل واحد، لو سالب مفيش حلول حقيقية.",
    "يعني إيه الحث الكهرومغناطيسي ببساطة؟":
        "لما الفيض المغناطيسي اللي بيعدي خلال ملف يتغير، بيتولد في الملف قوة دافعة كهربية (تيار لو الدائرة مقفولة).\n\n"
        "التغيير ممكن يكون بتحريك مغناطيس جوه الملف، أو تحريك الملف، أو تغيير التيار في ملف جنبه.\n\n"
        "قانون فاراداي: emf = -N × (ΔΦ / Δt) — والسالب معناه إن التيار المتولد بيقاوم التغيير (قاعدة لنز). وده أساس عمل المولد الكهربي والمحول.",
    "إزاي الإنزيمات بتسرّع التفاعلات؟":
        "الإنزيم بيقلل طاقة التنشيط اللازمة عشان التفاعل يبدأ، من غير ما يتغير هو نفسه.\n\n"
        "المادة المتفاعلة بتدخل في الموقع النشط للإنزيم زي المفتاح في القفل، فبيتكوّن معقد (إنزيم - مادة تفاعل) بيسهّل كسر أو تكوين الروابط.\n\n"
        "وعشان كده الإنزيم بيتأثر بدرجة الحرارة والـ pH: لو اتغيروا أوي شكل الموقع النشط بيتغير والإنزيم يبطل يشتغل.",
}

FAQS = [
    ("الحصص بتكون إزاي؟", "حصص لايف فردية بالصوت والصورة جوه الموقع أو التطبيق — من غير أي برنامج تاني — وفيها سبورة ومشاركة شاشة، والمدرس بيكتب تقرير بعد كل حصة."),
    ("أعمل حساب إزاي؟", "دوس «ابدأ مجاناً» فوق، واكتب اسمك ورقم موبايلك وكلمة سر واختار صفك. إنشاء الحساب مجاني ومفيش دفع لحد ما تختار باقة أو كورس."),
    ("أقدر أجرب قبل ما أدفع؟", "أيوه، تقدر تطلب حصة تجريبية مجانية في المادة اللي تحبها قبل أي اشتراك."),
    ("إزاي أدفع؟", "بالكارت (فيزا/ماستركارد) أو المحافظ الإلكترونية من صفحة الباقات جوه حسابك."),
    ("لو عندي سؤال بين الحصص؟", "اسأله في بنك الأسئلة والأجوبة والمدرسين المتخصصين بيردوا عليه، أو ابعته لمدرسك في الشات."),
    ("لو فاتتني حصة؟", "لو المدرس هو اللي غاب أو لغى بتتعوض، ولو انت لغيت قبل الميعاد بوقت كافي مش بتتخصم من باقتك."),
    ("أنا مدرس، أنضم إزاي؟", "دوس «انضم كمدرس» واملا بياناتك والمواد اللي بتدرّسها، وبعدها ارفع شهاداتك من صفحتك. الإدارة بتراجع الطلب وأول ما يتقبل تقدر تفتح مواعيدك وترفع كورساتك."),
]

PAGES = {
    "about": ("من نحن", "منصة تعليم أونلاين بتجمع الطالب بمدرس متخصص في كل المواد: حصص لايف، كورسات مسجلة، واجبات وامتحانات، وبنك أسئلة.", """
<p>{site} منصة تعليم أونلاين هدفها إن كل طالب يلاقي مدرس متخصص في المادة اللي محتاجها، ويذاكر معاه من بيته في الميعاد اللي يناسبه.</p>
<h2>بنقدّم إيه؟</h2>
<ul>
<li><strong>حصص لايف فردية</strong> بالصوت والصورة جوه الموقع، فيها سبورة ومشاركة شاشة، وتقرير بعد كل حصة.</li>
<li><strong>كورسات مسجلة</strong> تذاكرها في أي وقت وتكمّل من مكان ما وقفت.</li>
<li><strong>واجبات وامتحانات</strong> بتتصحح تلقائياً، وشهادة إتمام لما تخلّص الكورس.</li>
<li><strong>بنك أسئلة وأجوبة</strong> مفتوح للكل، بيرد عليه مدرسين متخصصين.</li>
<li><strong>مدونة تعليمية</strong> فيها خطط مذاكرة وشروحات مبسطة.</li>
</ul>
<h2>المدرسين</h2>
<p>كل مدرس بيقدّم طلب انضمام ويرفع مؤهلاته، والإدارة بتراجعها قبل ما يبدأ يستقبل طلاب، وبتتابع جودة الحصص بعد كده.</p>
<h2>تواصل معانا</h2>
<p>لأي استفسار ابعتلنا من الشات جوه حسابك.</p>
"""),
    "terms": ("الشروط والأحكام", "شروط استخدام المنصة للطلاب والمدرسين.", """
<p>باستخدامك للمنصة انت موافق على الشروط دي. لو مش موافق عليها متستخدمش الخدمة.</p>
<h2>الحساب</h2>
<ul><li>انت مسؤول عن صحة بياناتك وعن سرية كلمة السر بتاعتك.</li>
<li>ممنوع تعمل أكتر من حساب لنفس الشخص أو تستخدم حساب حد تاني.</li></ul>
<h2>الحصص والباقات</h2>
<ul><li>الباقة صالحة للمدة المكتوبة عليها، والحصص اللي متتاخدش خلال المدة بتنتهي معاها.</li>
<li>إلغاء الحصة لازم يكون قبل ميعادها بوقت كافي حسب سياسة المنصة، وإلا بتتحسب.</li>
<li>لو المدرس غاب أو لغى الحصة بتتعوض للطالب.</li></ul>
<h2>السلوك</h2>
<ul><li>ممنوع تبادل أرقام التليفون أو وسائل تواصل خارج المنصة في الشات أو الحصص.</li>
<li>ممنوع أي محتوى مسيء أو مخالف، والإدارة من حقها توقف أي حساب مخالف.</li></ul>
<h2>المحتوى</h2>
<p>الكورسات والفيديوهات ملك أصحابها، وممنوع تحميلها أو نشرها خارج المنصة.</p>
<h2>المدفوعات</h2>
<p>الدفع بيتم عن طريق بوابة دفع آمنة، وطلبات الاسترداد بتتراجع من الإدارة حسب حالة كل طلب.</p>
<p>المنصة من حقها تعدّل الشروط دي، وأي تعديل بيتنشر في الصفحة دي.</p>
"""),
    "privacy": ("سياسة الخصوصية", "إزاي بنجمع بياناتك ونستخدمها ونحميها.", """
<p>خصوصيتك مهمة لينا. الصفحة دي بتوضح البيانات اللي بنجمعها وبنعمل بيها إيه.</p>
<h2>البيانات اللي بنجمعها</h2>
<ul><li>بيانات الحساب: الاسم، رقم الموبايل، الإيميل (اختياري)، والصف الدراسي.</li>
<li>بيانات المدرسين: المؤهلات والمستندات اللي بيرفعوها للمراجعة.</li>
<li>بيانات الاستخدام: الحصص، الواجبات، الرسائل، وتقدمك في الكورسات.</li></ul>
<h2>بنستخدمها في إيه</h2>
<ul><li>تشغيل الخدمة: الحجز، الحصص، الإشعارات، والدفع.</li>
<li>متابعة الجودة والأمان ومنع المخالفات.</li></ul>
<h2>مشاركة البيانات</h2>
<p>مش بنبيع بياناتك. بنشاركها بس مع الخدمات اللازمة للتشغيل (زي بوابة الدفع وخدمة الإشعارات) وبالقدر اللازم.</p>
<h2>حقوقك</h2>
<p>تقدر تعدّل بياناتك من صفحتك، أو تطلب مسح حسابك من الشات مع الإدارة.</p>
"""),
}


class Command(BaseCommand):
    help = "محتوى بداية حقيقي (مقالات بصور، أسئلة وأجوبة، صفحات) من غير حسابات وهمية"

    def add_arguments(self, parser):
        parser.add_argument("--if-empty", action="store_true", help="يشتغل بس لو مفيش مقالات منشورة")
        parser.add_argument("--refresh-articles", action="store_true",
                            help="حدّث مقالات «فريق المنصة» للنسخة الأحدث (مرة واحدة لكل نسخة)")

    def handle(self, *args, **opts):
        from apps.seo.models import Article
        if opts["refresh_articles"]:
            return self._refresh()
        if opts["if_empty"] and Article.objects.exists():
            self.stdout.write("seed_showcase: فيه محتوى بالفعل — مفيش حاجة اتعملت.")
            return
        with transaction.atomic():
            S = self._catalog()
            editor = self._editor()
            self._pages_and_faq()
            n_art = self._articles(S, editor)
            n_q = self._questions(S, editor)
        self.stdout.write(self.style.SUCCESS(f"seed_showcase: {n_art} مقال و {n_q} سؤال."))

    def _repair_media(self):
        """لو السيرفر من غير Volume الملفات بتتمسح مع كل نشر: نرجّع صور مقالات الفريق من demo_assets."""
        from django.core.files.storage import default_storage
        from apps.seo.models import Article

        from ._showcase_articles import ARTICLES
        covers = {a["title"]: a.get("cover") for a in ARTICLES}
        fixed = 0
        for art in Article.objects.filter(title__in=covers.keys()).exclude(cover=""):
            name = covers.get(art.title)
            if art.cover and not default_storage.exists(art.cover.name) and name and (COVERS / name).exists():
                with open(COVERS / name, "rb") as fh:
                    saved = default_storage.save(art.cover.name, File(fh))
                if saved != art.cover.name:
                    Article.objects.filter(pk=art.pk).update(cover=saved)
                fixed += 1
        for f in INLINE.glob("*.png"):
            if not default_storage.exists(f"blog/inline/{f.name}"):
                self._inline_url(f.name)
                fixed += 1
        if fixed:
            self.stdout.write(f"seed_showcase: رجّعت {fixed} صورة كانت ناقصة من التخزين.")

    def _refresh(self):
        self._repair_media()
        marker = Path(settings.MEDIA_ROOT).parent / f".showcase_articles_{ARTICLES_VERSION}"
        if marker.exists():
            self.stdout.write(f"seed_showcase: المقالات على النسخة {ARTICLES_VERSION} بالفعل.")
            return
        from apps.catalog.models import Subject
        with transaction.atomic():
            S = {x.slug: x for x in Subject.objects.all()}
            n = self._articles(S, self._editor(), refresh=True) if S else 0
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text(ARTICLES_VERSION)
        except OSError:
            pass
        self.stdout.write(self.style.SUCCESS(f"seed_showcase: اتحدّث {n} مقال للنسخة {ARTICLES_VERSION}."))

    # ---------------------------------------------------------------
    def _catalog(self):
        from apps.catalog.models import Curriculum, Grade, Stage, Subject
        from apps.tutoring.models import Package
        if Subject.objects.exists():
            return {s.slug: s for s in Subject.objects.all()}
        eg = Curriculum.objects.create(name="المنهج المصري", country="EG", order=1)
        azhar = Curriculum.objects.create(name="المنهج الأزهري", country="EG", order=2)
        general = Curriculum.objects.create(name="عام (لغات وقرآن ومهارات)", order=3)
        eg_grades = []
        for cur, stages in [(eg, {"ابتدائي": 6, "إعدادي": 3, "ثانوي": 3}), (azhar, {"إعدادي": 3, "ثانوي": 3})]:
            for i, (sname, n) in enumerate(stages.items()):
                st = Stage.objects.create(curriculum=cur, name=sname, order=i)
                for g in range(1, n + 1):
                    gr = Grade.objects.create(stage=st, name=f"الصف {g} {sname}", order=g)
                    if cur == eg:
                        eg_grades.append(gr)
        gst = Stage.objects.create(curriculum=general, name="كل الأعمار", order=0)
        all_ages = Grade.objects.create(stage=gst, name="كل المستويات", order=0)
        defs = [("رياضيات", "math", "#2563EB"), ("فيزياء", "physics", "#7C3AED"), ("كيمياء", "chemistry", "#0891B2"),
                ("أحياء", "biology", "#16A34A"), ("لغة عربية", "arabic", "#B45309"), ("لغة إنجليزية", "english", "#DC2626"),
                ("لغة فرنسية", "french", "#1D4ED8"), ("تاريخ", "history", "#92400E"), ("جغرافيا", "geography", "#0E7490"),
                ("فلسفة ومنطق", "philosophy", "#6D28D9"), ("علوم", "science", "#15803D"),
                ("قرآن كريم وتجويد", "quran", "#0F766E"), ("برمجة للأطفال", "coding", "#EA580C"),
                ("دراسات اجتماعية", "social-studies", "#A16207")]
        S = {}
        for i, (n, en, color) in enumerate(defs):
            s = Subject.objects.create(name=n, name_en=en, slug=en, order=i, color=color, is_featured=i < 8,
                                       description=f"حصص {n} أونلاين مع مدرسين متخصصين، بمتابعة وتقرير بعد كل حصة.",
                                       meta_title=f"مدرس {n} أونلاين")
            s.grades.set([all_ages] if en in ("quran", "coding", "english", "french") else eg_grades)
            S[en] = s
        if not Package.objects.exists():
            Package.objects.create(name="باقة أساسية", sessions_count=4, session_duration=60, price=400, order=1,
                                   description="4 حصص في الشهر — حصة كل أسبوع")
            Package.objects.create(name="باقة شهرية", sessions_count=8, session_duration=60, price=750, is_featured=True,
                                   order=2, description="8 حصص في الشهر — حصتين كل أسبوع")
            Package.objects.create(name="باقة مكثفة", sessions_count=12, session_duration=60, price=1050, order=3,
                                   description="12 حصة — 3 حصص كل أسبوع")
        return S

    def _editor(self):
        from apps.accounts.models import User
        from apps.core.permissions import Roles
        u = User.objects.filter(username=EDITOR_USERNAME).first()
        if u:
            return u
        u = User(username=EDITOR_USERNAME, phone=EDITOR_USERNAME, full_name=f"فريق {settings.SITE_NAME} التعليمي",
                 role=Roles.SUPERVISOR, is_staff=False)
        u.set_unusable_password()
        u.save()
        return u

    def _pages_and_faq(self):
        from apps.seo.models import FAQ, Page
        for slug, (title, meta, body) in PAGES.items():
            p = Page.objects.filter(slug=slug).first()
            body = body.strip().replace("{site}", settings.SITE_NAME)
            if not p:
                Page.objects.create(slug=slug, title=title, meta_description=meta, body=body)
            elif p.body.startswith("<p>محتوى صفحة"):  # محتوى placeholder قديم
                p.body, p.meta_description = body, meta
                p.save()
        if not FAQ.objects.exists():
            for i, (q, a) in enumerate(FAQS):
                FAQ.objects.create(question=q, answer=a, order=i)

    def _inline_url(self, name):
        """صور جوه المقالات: بتترفع مرة واحدة على التخزين وبيرجع رابطها."""
        from django.core.files.storage import default_storage
        key = f"blog/inline/{name}"
        src = INLINE / name
        if not default_storage.exists(key) and src.exists():
            with open(src, "rb") as fh:
                key = default_storage.save(key, File(fh))
        return default_storage.url(key)

    def _render_body(self, body):
        import re
        return re.sub(r"__IMG__/([\w.-]+)", lambda m: self._inline_url(m.group(1)), body.strip())

    def _articles(self, S, editor, refresh=False):
        from apps.seo.models import Article, BlogCategory, Tag

        from ._demo_content import CATEGORIES
        from ._showcase_articles import ARTICLES
        now = timezone.now()
        cats = {}
        for i, (name, slug, desc, subj) in enumerate(CATEGORIES):
            cats[slug] = BlogCategory.objects.get_or_create(
                slug=slug, defaults={"name": name, "description": desc, "order": i, "subject": S.get(subj) if subj else None})[0]
        made = 0
        for i, a in enumerate(ARTICLES):
            art = Article.objects.filter(title=a["title"]).first()
            if art and not (refresh and art.author_id == editor.id):
                continue
            fields = dict(category=cats[a["cat"]], subject=S.get(a["subject"]) if a["subject"] else None,
                          body=self._render_body(a["body"]), faq=a["faq"], meta_description=a["meta"],
                          focus_keyword=a["keyword"], is_featured=a["featured"], excerpt="",
                          cover_alt=COVER_ALTS[i] if i < len(COVER_ALTS) else "")
            new = art is None
            if new:
                art = Article(title=a["title"], author=editor, status="published", **fields)
            else:
                for k, v in fields.items():
                    setattr(art, k, v)
            cover = COVERS / a.get("cover", "")
            if (new or not art.cover) and a.get("cover") and cover.exists():
                with open(cover, "rb") as fh:
                    art.cover.save(a["cover"], File(fh), save=False)
            art.save()
            if new:
                Article.objects.filter(pk=art.pk).update(published_at=now - dt.timedelta(days=2 + i * 4))
            art.tags.set([Tag.objects.get_or_create(name=t)[0] for t in a["tags"]])
            made += 1
        return made

    def _questions(self, S, editor):
        from apps.qa.models import Answer, Question

        from ._demo_content import QUESTIONS
        now = timezone.now()
        made = 0
        for k, (_asker, subj, title, body, answers, _acc, _score) in enumerate(QUESTIONS):
            if subj not in S or Question.objects.filter(title=title).exists():
                continue
            text = answers[0][1] if answers else EXTRA_ANSWERS.get(title)
            q = Question.objects.create(author=editor, subject=S[subj], title=title, body=body)
            created = now - dt.timedelta(days=40 - k * 2, hours=k)
            if text:
                an = Answer.objects.create(question=q, author=editor, body=text)
                Answer.objects.filter(pk=an.pk).update(created_at=created + dt.timedelta(hours=2))
                q.accepted_answer = an
                q.answers_count = 1
                q.save()
            Question.objects.filter(pk=q.pk).update(created_at=created, last_activity_at=created + dt.timedelta(hours=2))
            made += 1
        return made
