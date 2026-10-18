"""
بيانات تجريبية كبيرة للتجربة:
    python manage.py seed_demo           # يضيف البيانات لو مش موجودة
    python manage.py seed_demo --reset   # يمسح كل البيانات ويعيد التوليد

كل الحسابات كلمة سرها: admin12345
أسماء الدخول: admin, supervisor, supervisor2, teacher1..teacher12, student1..student30,
pending1, pending2 (مدرسين قيد المراجعة)
"""
import datetime as dt
import random
from pathlib import Path
from decimal import Decimal

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

PASSWORD = "admin12345"
VIDEO = "https://www.youtube.com/watch?v=aircAruvnKk"
# فيديوهات يوتيوب للتجربة (بأشكال روابط مختلفة عشان نجرّب الفهم التلقائي)
YT = ["https://youtu.be/WUvTyaaNkzM", "https://www.youtube.com/watch?v=fNk_zzaMoSs", "https://www.youtube.com/watch?v=aircAruvnKk&t=10s",
      "https://youtube.com/shorts/kYB8IZa5AuE"]
# منهج حقيقي لكل كورس: وحدات وجواها دروس
CURRICULUM = {
    "math": [("التفاضل: الأساسيات", ["فكرة المشتقة ببساطة", "قواعد الاشتقاق", "مشتقة الدوال المثلثية"]),
             ("تطبيقات التفاضل", ["معادلة المماس والعمودي", "القيم العظمى والصغرى", "المعدلات الزمنية المرتبطة"]),
             ("التكامل", ["التكامل غير المحدد", "التكامل بالتعويض", "المساحات والحجوم"])],
    "english": [("Getting started", ["الحروف والأصوات", "تقديم نفسك بالإنجليزي", "الأرقام والألوان"]),
                ("Grammar basics", ["Verb to be", "Present simple", "Questions & negatives"]),
                ("Speaking", ["حوارات يومية", "في المطعم والسوق", "إزاي تطوّر نطقك"])],
    "quran": [("أحكام النون الساكنة", ["الإظهار", "الإدغام", "الإقلاب والإخفاء"]),
              ("أحكام الميم الساكنة", ["الإخفاء الشفوي", "الإدغام الشفوي", "الإظهار الشفوي"]),
              ("المدود", ["المد الطبيعي", "المد المتصل والمنفصل", "المد اللازم"])],
    "chemistry": [("مدخل للكيمياء العضوية", ["يعني إيه مركب عضوي", "الروابط والتهجين", "التسمية IUPAC"]),
                  ("الهيدروكربونات", ["الألكانات", "الألكينات والألكاينات", "البنزين والمركبات الأروماتية"]),
                  ("المجموعات الوظيفية", ["الكحولات", "الأحماض الكربوكسيلية", "الإسترات"])],
    "coding": [("أول خطوة في سكراتش", ["الواجهة والكائنات", "الحركة والأصوات", "أول لعبة بسيطة"]),
               ("المنطق والتكرار", ["الحلقات التكرارية", "الشروط إذا/وإلا", "المتغيرات والنقاط"]),
               ("مشروع كامل", ["تصميم لعبة المتاهة", "إضافة المستويات", "نشر مشروعك"])],
    "physics": [("التيار الكهربي", ["شدة التيار وفرق الجهد", "قانون أوم", "المقاومة النوعية"]),
                ("توصيل المقاومات", ["التوصيل على التوالي", "التوصيل على التوازي", "مسائل مركبة"]),
                ("قانونا كيرشوف", ["قانون كيرشوف الأول", "قانون كيرشوف الثاني", "حل الدوائر خطوة بخطوة"])],
    "arabic": [("الجملة الاسمية", ["المبتدأ والخبر", "كان وأخواتها", "إن وأخواتها"]),
               ("الجملة الفعلية", ["الفعل والفاعل", "المفعول به", "نائب الفاعل"]),
               ("الأساليب", ["أسلوب الاستفهام", "أسلوب الشرط", "أسلوب التعجب"])],
    "biology": [("أساسيات الوراثة", ["تجارب مندل", "الجينات والصفات", "مربع بانيت"]),
                ("الوراثة المتقدمة", ["السيادة غير التامة", "الصفات المرتبطة بالجنس", "فصائل الدم"]),
                ("الوراثة الجزيئية", ["تركيب DNA", "تضاعف DNA", "تخليق البروتين"])],
}
ASSETS = Path(__file__).resolve().parent / "demo_assets"

TEACHERS = [
    # (username, name, gender, subjects, headline, years)
    ("teacher1", "أ. أحمد سامي", "male", ["math", "physics"], "مدرس رياضيات وفيزياء للثانوية العامة", 12),
    ("teacher2", "أ. سارة محمود", "female", ["english", "french"], "مدرسة لغات — IELTS وتأسيس", 10),
    ("teacher3", "الشيخ محمد علي", "male", ["quran", "arabic"], "محفّظ قرآن بالإجازة ومدرس لغة عربية", 15),
    ("teacher4", "د. خالد حسن", "male", ["chemistry", "biology"], "دكتوراه كيمياء — مدرس ثانوي", 9),
    ("teacher5", "أ. منة الله فتحي", "female", ["math", "science"], "رياضيات وعلوم للإعدادي والابتدائي", 7),
    ("teacher6", "أ. يوسف إبراهيم", "male", ["history", "geography", "social-studies"], "دراسات اجتماعية بأسلوب القصة", 8),
    ("teacher7", "أ. نور الهدى", "female", ["quran"], "تحفيظ القرآن للأطفال والسيدات", 6),
    ("teacher8", "م. عمر الشريف", "male", ["coding", "math"], "مهندس برمجيات — برمجة للأطفال وسكراتش وبايثون", 5),
    ("teacher9", "أ. ريهام عادل", "female", ["arabic"], "لغة عربية — نحو وبلاغة للثانوية", 11),
    ("teacher10", "أ. كريم مصطفى", "male", ["physics"], "فيزياء ثانوي وتأسيس جامعي", 6),
    ("teacher11", "أ. دينا سمير", "female", ["english"], "إنجليزي محادثة وتأسيس للصغار", 4),
    ("teacher12", "د. هالة رشاد", "female", ["biology", "philosophy"], "أحياء وفلسفة — ثانوية عامة", 13),
]

FIRST_M = ["يوسف", "عمر", "آدم", "مالك", "زياد", "حمزة", "علي", "مصطفى", "كريم", "سيف", "إياد", "أنس", "ياسين", "معاذ", "مازن"]
FIRST_F = ["مريم", "جنى", "ملك", "فريدة", "نور", "سلمى", "هنا", "لوجين", "رقية", "حبيبة", "تقى", "روان", "ليلى", "شهد", "جودي"]
LAST = ["أحمد", "محمد", "خالد", "طارق", "حسن", "سامي", "عادل", "إبراهيم", "فتحي", "مصطفى", "رشاد", "عبدالله", "منصور", "جمال"]

TOPICS = {
    "math": ["التفاضل — قواعد الاشتقاق", "المعادلات من الدرجة الثانية", "حساب المثلثات", "المتتابعات", "الهندسة الفراغية"],
    "physics": ["قوانين نيوتن", "الكهربية التيارية", "الحث الكهرومغناطيسي", "الموجات", "الفيزياء الحديثة"],
    "english": ["Present perfect", "Reading comprehension", "Essay writing", "Vocabulary — unit 4", "Listening practice"],
    "french": ["Le passé composé", "Les articles", "La compréhension écrite"],
    "quran": ["مراجعة سورة الملك", "حفظ سورة القلم", "أحكام النون الساكنة", "تسميع جزء عم", "المدود"],
    "arabic": ["الممنوع من الصرف", "البلاغة — التشبيه", "القصة القصيرة", "إعراب الجملة"],
    "chemistry": ["الكيمياء العضوية", "الاتزان الكيميائي", "الأحماض والقواعد", "الكيمياء الكهربية"],
    "biology": ["الدعامة والحركة", "التكاثر", "الجهاز العصبي", "الوراثة"],
    "science": ["المادة وتركيبها", "الطاقة", "التنفس في الكائنات"],
    "history": ["الحملة الفرنسية", "ثورة 1919", "الدولة العثمانية"],
    "geography": ["المناخ", "السكان", "الموارد الطبيعية"],
    "social-studies": ["خريطة مصر", "الحضارة الفرعونية"],
    "coding": ["Scratch — الحلقات", "Python — المتغيرات", "مشروع لعبة بسيطة"],
    "philosophy": ["المنطق الصوري", "فلسفة الأخلاق"],
}

COURSES = [
    ("teacher1", "math", "مراجعة التفاضل والتكامل — ثالثة ثانوي", 299, 399, True),
    ("teacher2", "english", "أساسيات الإنجليزي للمبتدئين", 0, None, True),
    ("teacher3", "quran", "أحكام التجويد للمبتدئين", 0, None, True),
    ("teacher4", "chemistry", "الكيمياء العضوية من الصفر", 249, None, False),
    ("teacher8", "coding", "برمجة للأطفال بسكراتش", 199, 249, True),
    ("teacher10", "physics", "الكهربية — شرح وحل مسائل", 179, None, False),
    ("teacher9", "arabic", "النحو في 10 ساعات", 149, 199, False),
    ("teacher12", "biology", "الوراثة بالتفصيل", 0, None, False),
]


class Command(BaseCommand):
    help = "Seed rich demo data (password: admin12345)"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="امسح كل البيانات الحالية الأول")

    def handle(self, *args, **opts):
        from apps.accounts.models import User
        if opts["reset"]:
            self._reset()
        elif User.objects.filter(username="admin").exists():
            self.stdout.write(self.style.WARNING("البيانات التجريبية موجودة. استخدم --reset عشان تمسحها وتعيدها."))
            return
        random.seed(7)
        self.stdout.write("جاري توليد البيانات التجريبية (ممكن ياخد دقيقة)…")
        with transaction.atomic():
            self._seed()
        self._print_accounts()

    # ------------------------------------------------------------------
    def _reset(self):
        from django.apps import apps
        from django.db import connection
        labels = ["qa", "payments", "chat", "notifications", "assessments", "courses", "tutoring", "seo", "accounts", "catalog"]
        with transaction.atomic():
            for label in labels:
                for model in reversed(list(apps.get_app_config(label).get_models())):
                    model.objects.all().delete()
            from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
            BlacklistedToken.objects.all().delete()
            OutstandingToken.objects.all().delete()
        import shutil
        from django.conf import settings
        for sub in ("videos", "attachments"):  # ملفات الدروس التجريبية القديمة
            shutil.rmtree(settings.PRIVATE_MEDIA_ROOT / sub, ignore_errors=True)
        self.stdout.write("تم مسح البيانات القديمة.")

    def _seed(self):
        from apps.accounts.models import StudentProfile, TeacherDocument, TeacherProfile, User
        from apps.catalog.models import Curriculum, Grade, Stage, Subject
        from apps.notifications.models import Notification
        from apps.tutoring.models import (Package, RescheduleRequest, Review, Session, SessionEvaluation, SessionReport,
                                          Subscription, TeacherAvailability, TrialRequest, WeeklySlot)
        from apps.tutoring.services import activate_subscription, refresh_teacher_rating

        now = timezone.now()
        today = timezone.localdate()
        tz = timezone.get_current_timezone()

        # ================= Catalog =================
        eg = Curriculum.objects.create(name="المنهج المصري", country="EG", order=1)
        azhar = Curriculum.objects.create(name="المنهج الأزهري", country="EG", order=2)
        general = Curriculum.objects.create(name="عام (لغات وقرآن ومهارات)", order=3)
        grades = {}
        for cur, stages in [(eg, {"ابتدائي": 6, "إعدادي": 3, "ثانوي": 3}), (azhar, {"إعدادي": 3, "ثانوي": 3})]:
            for i, (sname, n) in enumerate(stages.items()):
                st = Stage.objects.create(curriculum=cur, name=sname, order=i)
                for g in range(1, n + 1):
                    grades[(cur.slug, sname, g)] = Grade.objects.create(stage=st, name=f"الصف {g} {sname}", order=g)
        gst = Stage.objects.create(curriculum=general, name="كل الأعمار", order=0)
        all_ages = Grade.objects.create(stage=gst, name="كل المستويات", order=0)
        eg_grades = [g for k, g in grades.items() if k[0] == eg.slug]

        subj_defs = [("رياضيات", "math", "#2563EB"), ("فيزياء", "physics", "#7C3AED"), ("كيمياء", "chemistry", "#059669"),
                     ("أحياء", "biology", "#16A34A"), ("لغة عربية", "arabic", "#B45309"), ("لغة إنجليزية", "english", "#DC2626"),
                     ("لغة فرنسية", "french", "#1D4ED8"), ("تاريخ", "history", "#92400E"), ("جغرافيا", "geography", "#0E7490"),
                     ("فلسفة ومنطق", "philosophy", "#6D28D9"), ("علوم", "science", "#15803D"),
                     ("قرآن كريم وتجويد", "quran", "#0F766E"), ("برمجة للأطفال", "coding", "#EA580C"),
                     ("دراسات اجتماعية", "social-studies", "#A16207")]
        S = {}
        for i, (n, en, color) in enumerate(subj_defs):
            s = Subject.objects.create(name=n, name_en=en, slug=en, order=i, color=color, is_featured=i < 8,
                                       description=f"حصص {n} أونلاين مع مدرسين متخصصين، بمتابعة وتقرير بعد كل حصة يوصل لولي الأمر.",
                                       meta_title=f"مدرس {n} أونلاين")
            s.grades.set([all_ages] if en in ("quran", "coding", "english", "french") else eg_grades)
            S[en] = s

        # ================= Packages =================
        P = {
            "basic": Package.objects.create(name="باقة أساسية", sessions_count=4, session_duration=60, price=400, order=1,
                                            description="4 حصص في الشهر — حصة كل أسبوع"),
            "monthly": Package.objects.create(name="باقة شهرية", sessions_count=8, session_duration=60, price=750, old_price=800,
                                              is_featured=True, order=2, description="8 حصص في الشهر — حصتين كل أسبوع"),
            "intensive": Package.objects.create(name="باقة مكثفة", sessions_count=12, session_duration=60, price=1050, order=3,
                                                description="12 حصة — 3 حصص كل أسبوع"),
            "quran": Package.objects.create(name="باقة القرآن", subject=S["quran"], sessions_count=12, session_duration=30,
                                            price=500, order=4, description="12 حصة × نص ساعة"),
        }

        # ================= Users =================
        seq = iter(range(1, 10_000))

        from django.contrib.auth.hashers import make_password
        hashed = make_password(PASSWORD)  # تشفير مرة واحدة بدل 57 مرة (أسرع بكتير)

        def mk(username, name, role, **kw):
            n = next(seq)
            u = User(phone=f"+2010{n:08d}", username=username, full_name=name, role=role, is_phone_verified=True,
                     password=hashed, **kw)
            u.save()
            return u

        admin = mk("admin", "مدير المنصة", "admin", is_staff=True, is_superuser=True, email="admin@demo.com")
        sup1 = mk("supervisor", "أ. منى المشرفة", "supervisor", gender="female", email="supervisor@demo.com")
        sup2 = mk("supervisor2", "أ. حسام المشرف", "supervisor", gender="male")

        teachers = []
        for i, (uname, name, gender, subs, head, years) in enumerate(TEACHERS):
            u = mk(uname, name, "teacher", gender=gender)
            tp = TeacherProfile.objects.create(
                user=u, headline=head, experience_years=years, hourly_rate=120 + years * 10, approval_status="approved",
                bio=f"{head}. بحب أبسّط المعلومة وأربطها بالواقع، وبتابع كل طالب لوحده بخطة مناسبة لمستواه.",
                qualifications="بكالوريوس تربية — دبلومة مهنية في طرق التدريس", supervisor=sup1 if i % 2 == 0 else sup2,
                is_featured=i < 4, teaches_gender="female" if uname == "teacher7" else "all")
            tp.subjects.set([S[x] for x in subs])
            tp.grades.set(eg_grades if "quran" not in subs else [all_ages])
            for wd in range(7):
                if wd == 4:  # الجمعة إجازة
                    continue
                TeacherAvailability.objects.create(teacher=u, weekday=wd, start_time=dt.time(15), end_time=dt.time(23))
            teachers.append(u)
        T = {t.username: t for t in teachers}

        for uname, name, sub in [("pending1", "أ. محمود جمال (قيد المراجعة)", "history"), ("pending2", "أ. آية سعيد (قيد المراجعة)", "english")]:
            u = mk(uname, name, "teacher")
            tp = TeacherProfile.objects.create(user=u, headline=f"مدرس {S[sub].name}", bio="خبرة 3 سنين في المدارس الخاصة.",
                                               experience_years=3)
            tp.subjects.set([S[sub]])
            TeacherDocument.objects.create(teacher=tp, title="السيرة الذاتية", file="teachers/docs/cv.pdf")

        sec3 = grades[(eg.slug, "ثانوي", 3)]
        students = []
        for i in range(1, 31):
            female = i % 2 == 0
            first = (FIRST_F if female else FIRST_M)[(i // 2) % 15]
            name = f"{first} {LAST[i % len(LAST)]}"
            u = mk(f"student{i}", name, "student", gender="female" if female else "male")
            g = sec3 if i <= 10 else random.choice(eg_grades)
            StudentProfile.objects.create(user=u, grade=g, school=random.choice(["مدرسة النصر", "مدرسة الأورمان", "مدرسة المستقبل", "مدرسة الشهيد"]))
            students.append(u)
        ST = {s.username: s for s in students}

        # ================= Subscriptions + sessions =================
        def teacher_for(subject):
            return [t for t in teachers if t.teacher_profile.subjects.filter(slug=subject).exists()]

        plan = []  # (student, teacher, subject, package)
        plan += [(ST["student1"], T["teacher1"], "math", "monthly"), (ST["student1"], T["teacher4"], "chemistry", "monthly"),
                 (ST["student1"], T["teacher2"], "english", "basic"), (ST["student2"], T["teacher2"], "english", "monthly"),
                 (ST["student2"], T["teacher3"], "quran", "quran"), (ST["student3"], T["teacher1"], "physics", "intensive")]
        subjects_cycle = ["math", "physics", "english", "arabic", "chemistry", "biology", "quran", "coding", "history", "science"]
        for i, st in enumerate(students[3:25], start=3):
            subj = subjects_cycle[i % len(subjects_cycle)]
            cands = teacher_for(subj)
            pkg = "quran" if subj == "quran" else random.choice(["basic", "monthly", "monthly", "intensive"])
            plan.append((st, cands[i % len(cands)], subj, pkg))

        active_subs = []
        for k, (st, t, subj, pkg) in enumerate(plan):
            package = P[pkg]
            sub = Subscription.objects.create(student=st, teacher=t, preferred_teacher=t, subject=S[subj], package=package,
                                              status="pending_assignment", sessions_total=package.sessions_count,
                                              session_duration=package.session_duration, price_paid=package.price)
            per_week = max(1, package.sessions_count // 4)
            days = random.sample([0, 1, 2, 3, 5, 6], per_week)
            hour = 16 + (k % 6)
            for d in days:
                WeeklySlot.objects.create(subscription=sub, weekday=d, start_time=dt.time(hour))
            start = today - dt.timedelta(days=14 + (k % 7))
            activate_subscription(sub, start_date=start)
            active_subs.append(sub)

            # حصص سابقة (اتعملت قبل كده)
            topics = TOPICS.get(subj, ["مراجعة عامة"])
            for j in range(random.randint(3, 5)):
                at = timezone.make_aware(dt.datetime.combine(start + dt.timedelta(days=2 + j * 3), dt.time(hour)), tz)
                if at >= now - dt.timedelta(hours=3):
                    break
                status = random.choices(["completed", "student_absent", "cancelled", "teacher_absent"], weights=[14, 2, 2, 1], k=1)[0]
                s = Session.objects.create(subscription=sub, teacher=t, student=st, subject=S[subj], scheduled_at=at,
                                           duration=sub.session_duration, status=status,
                                           started_at=at if status == "completed" else None,
                                           ended_at=at + dt.timedelta(minutes=sub.session_duration) if status in ("completed", "student_absent") else None,
                                           teacher_joined_at=at if status in ("completed", "student_absent") else None,
                                           student_joined_at=at if status == "completed" else None,
                                           counted=status in ("completed", "student_absent"),
                                           cancel_reason="ظرف طارئ" if status == "cancelled" else "",
                                           cancelled_by=st if status == "cancelled" else None, reminder_sent=True)
                if s.counted:
                    sub.sessions_used += 1
                if status == "completed" and random.random() < 0.85:
                    SessionReport.objects.create(session=s, topics=topics[j % len(topics)],
                                                 homework=f"حل تمارين صفحة {random.randint(20, 120)}",
                                                 performance=random.randint(3, 5), behavior=random.randint(3, 5),
                                                 notes_for_student=random.choice(["مستواك بيتحسن، كمّل", "ركّز أكتر في الواجبات", "ممتاز ومتفاعل"]),
                                                 private_notes="متابعة عادية")
                    if random.random() < 0.4:
                        SessionEvaluation.objects.create(session=s, supervisor=t.teacher_profile.supervisor,
                                                         score=random.randint(7, 10), notes="شرح واضح والتزام بالوقت")
                if status == "student_absent":
                    SessionReport.objects.create(session=s, attendance="absent", topics="الطالب لم يحضر", performance=1, behavior=3)
            sub.save(update_fields=["sessions_used"])

        # حصص "دلوقتي" عشان تجرب الدخول فوراً
        nowish = Session.objects.create(subscription=active_subs[0], teacher=T["teacher1"], student=ST["student1"], subject=S["math"],
                                        title="حصة تجربة — تقدر تدخلها دلوقتي", scheduled_at=now + dt.timedelta(minutes=5), duration=60)
        Session.objects.create(subscription=active_subs[3], teacher=T["teacher2"], student=ST["student2"], subject=S["english"],
                               title="حصة شغالة دلوقتي", scheduled_at=now - dt.timedelta(minutes=10), duration=60, status="live",
                               started_at=now - dt.timedelta(minutes=9), teacher_joined_at=now - dt.timedelta(minutes=9))
        Session.objects.create(teacher=T["teacher3"], student=ST["student4"], subject=S["quran"], is_trial=True, title="حصة تجريبية",
                               scheduled_at=now + dt.timedelta(minutes=30), duration=30)
        # حصة خلصت من غير تقرير (عشان المدرس يجرب كتابة التقرير)
        Session.objects.create(subscription=active_subs[0], teacher=T["teacher1"], student=ST["student1"], subject=S["math"],
                               scheduled_at=now - dt.timedelta(hours=5), duration=60, status="completed", counted=True,
                               started_at=now - dt.timedelta(hours=5), ended_at=now - dt.timedelta(hours=4),
                               teacher_joined_at=now - dt.timedelta(hours=5), student_joined_at=now - dt.timedelta(hours=5))

        # اشتراكات بحالات مختلفة
        for st, subj, pkg, status in [(ST["student26"], "physics", "monthly", "pending_payment"),
                                      (ST["student27"], "math", "basic", "pending_payment"),
                                      (ST["student1"], "arabic", "basic", "pending_payment"),
                                      (ST["student28"], "english", "monthly", "pending_assignment"),
                                      (ST["student29"], "biology", "intensive", "pending_assignment"),
                                      (ST["student30"], "coding", "monthly", "pending_assignment"),
                                      (ST["student5"], "arabic", "basic", "pending_assignment"),
                                      (ST["student6"], "history", "basic", "expired"),
                                      (ST["student7"], "geography", "basic", "paused"),
                                      (ST["student8"], "math", "monthly", "cancelled")]:
            package = P[pkg]
            t = teacher_for(subj)[0] if status in ("expired", "paused", "cancelled") else None
            sub = Subscription.objects.create(student=st, teacher=t, preferred_teacher=teacher_for(subj)[0], subject=S[subj],
                                              package=package, status=status, sessions_total=package.sessions_count,
                                              session_duration=package.session_duration,
                                              price_paid=0 if status == "pending_payment" else package.price,
                                              preferred_times="بعد الساعة 5 العصر",
                                              sessions_used=package.sessions_count if status == "expired" else 0,
                                              start_date=today - dt.timedelta(days=40) if t else None,
                                              end_date=today - dt.timedelta(days=10) if t else None)
            if status == "paused":
                WeeklySlot.objects.create(subscription=sub, weekday=1, start_time=dt.time(18))

        # ================= Trials / reschedules / reviews =================
        for st, subj in [(ST["student26"], "math"), (ST["student27"], "english"), (ST["student28"], "quran"),
                         (ST["student29"], "physics"), (ST["student30"], "coding")]:
            TrialRequest.objects.create(student=st, subject=S[subj], preferred_teacher=teacher_for(subj)[0],
                                        preferred_times="أي يوم بعد المغرب", notes="عايز أتعرف على المدرس")
        trial_sess = Session.objects.filter(is_trial=True).first()
        TrialRequest.objects.create(student=ST["student4"], subject=S["quran"], status="scheduled", session=trial_sess)

        upcoming = list(Session.objects.filter(status="scheduled", scheduled_at__gt=now + dt.timedelta(days=1))[:4])
        for s in upcoming[:3]:
            RescheduleRequest.objects.create(session=s, requested_by=s.student, proposed_time=s.scheduled_at + dt.timedelta(days=1),
                                             reason="عندي امتحان في المدرسة")

        comments = ["شرح ممتاز وصبور جداً", "ابني اتحسن مستواه كتير", "أسلوب سهل ومنظم", "ملتزم بالمواعيد",
                    "أحسن مدرس اتعاملت معاه", "محتاج يدي واجبات أكتر", ""]
        for sub in active_subs:
            if Session.objects.filter(subscription=sub, status="completed").exists() and random.random() < 0.75:
                Review.objects.get_or_create(teacher=sub.teacher, student=sub.student,
                                             defaults={"rating": random.choice([4, 5, 5, 5, 3]), "comment": random.choice(comments)})
        for t in teachers:
            refresh_teacher_rating(t)

        self._seed_courses(S, T, ST, students, sec3)
        self._seed_quizzes(S, T, ST, students)
        self._seed_chat(T, ST, admin)
        self._seed_payments(ST, students, P, S)
        self._seed_content(S, T)

        # إشعارات إضافية متنوعة
        for st in students[:10]:
            Notification.objects.create(user=st, type="session_reminder", title="حصتك هتبدأ كمان شوية ⏰",
                                        body="رياضيات — 6:00 م", data={"screen": "session", "id": nowish.id})
        Notification.objects.create(user=admin, type="teacher_application", title="طلب انضمام مدرس جديد",
                                    body="أ. محمود جمال", data={})

    # ------------------------------------------------------------------
    def _seed_courses(self, S, T, ST, students, sec3):
        from apps.courses.models import Course, CourseReview, Enrollment, Lesson, LessonProgress, Section
        from apps.courses.services import recalc_progress, refresh_course_rating
        now = timezone.now()
        made = []
        for k, (tu, subj, title, price, old, featured) in enumerate(COURSES):
            c = Course.objects.create(
                instructor=T[tu], subject=S[subj], grade=sec3 if subj in ("math", "physics", "chemistry", "biology", "arabic") else None,
                title=title, short_description=f"كورس مسجل في {S[subj].name} بشرح مبسط وأمثلة محلولة",
                description="الكورس مقسم لوحدات قصيرة، كل درس فيه فيديو وملخص، وفي آخر كل وحدة اختبار سريع تقيس بيه فهمك.",
                price=price, old_price=old, status="published", published_at=now - dt.timedelta(days=30 - k), is_featured=featured,
                level=random.choice(["beginner", "intermediate", "all"]),
                what_you_learn=["فهم الأساسيات خطوة بخطوة", "حل مسائل على كل جزء", "مراجعة نهائية قبل الامتحان"],
                requirements=["موبايل أو كمبيوتر", "كشكول للملاحظات"])
            if subj == "math":  # كورس مدرس 1: مفتوح لطلاب اشتراك الحصص اللايف معاه
                c.included_in_subscription = True
                c.save(update_fields=["included_in_subscription"])
            yt = 0
            for si, (unit, titles) in enumerate(CURRICULUM[subj], 1):
                sec = Section.objects.create(course=c, title=unit, order=si)
                for li, lt in enumerate(titles, 1):
                    # أول درس في الكورس: مجاني للكل — تاني درس: للمسجلين — الباقي بعد الدفع
                    access = "free" if (si, li) == (1, 1) else "members" if (si, li) == (1, 2) else "paid"
                    les = Lesson(section=sec, title=lt, type="video", access=access, order=li,
                                 duration_seconds=random.randint(7, 22) * 60,
                                 content="ملخص سريع للي اتشرح في الدرس ومسائل للتدريب في الملف المرفق.")
                    if (si, li) == (1, 3):  # درس مرفوع مباشرة (مش يوتيوب) عشان نجرب المشغل المحمي
                        with open(ASSETS / "sample.mp4", "rb") as f:
                            les.video_file.save("demo-lesson.mp4", File(f), save=False)
                        les.duration_seconds = 45
                    else:
                        les.video_url = YT[yt % len(YT)]
                        yt += 1
                    les.save()
                with open(ASSETS / "summary.pdf", "rb") as f:
                    summ = Lesson(section=sec, title=f"ملخص {unit} (PDF)", type="pdf", access="paid", order=len(titles) + 1,
                                  content="ملخص الوحدة كلها في ورقة واحدة — اطبعه وذاكر منه.")
                    summ.attachment.save("summary.pdf", File(f), save=False)
                    summ.save()
            made.append(c)
        Course.objects.create(instructor=T["teacher5"], subject=S["science"], title="العلوم للصف الأول الإعدادي", price=150,
                              status="pending_review", short_description="مستني مراجعة الإدارة")
        Course.objects.create(instructor=T["teacher6"], subject=S["history"], title="تاريخ مصر الحديث", price=120,
                              status="pending_review", short_description="مستني مراجعة الإدارة")
        Course.objects.create(instructor=T["teacher1"], subject=S["math"], title="الجبر — مسودة", price=0, status="draft")

        for c in made:
            for st in random.sample(students, random.randint(4, 12)):
                enr = Enrollment.objects.create(student=st, course=c, source="free" if c.price == 0 else "purchase")
                lessons = list(Lesson.objects.filter(section__course=c).order_by("section__order", "order"))
                done = random.randint(0, len(lessons))
                for les in lessons[:done]:
                    LessonProgress.objects.create(enrollment=enr, lesson=les, completed=True, position_seconds=les.duration_seconds)
                enr.last_lesson = lessons[done - 1] if done else None
                recalc_progress(enr)
                if done > 3 and random.random() < 0.6:
                    CourseReview.objects.get_or_create(course=c, student=st, defaults={
                        "rating": random.choice([4, 5, 5]), "comment": random.choice(["كورس مفيد جداً", "الشرح واضح", "يستاهل"])})
            c.students_count = c.enrollments.count()
            c.save(update_fields=["students_count"])
            refresh_course_rating(c)
        # student1 مشترك في كورس الرياضيات
        Enrollment.objects.get_or_create(student=ST["student1"], course=made[0], defaults={"source": "purchase"})

    def _seed_quizzes(self, S, T, ST, students):
        from apps.assessments.models import Answer, Attempt, Choice, Question, Quiz, QuizAssignment
        from apps.assessments.services import submit_attempt
        now = timezone.now()

        def mcq(quiz, text, options, correct, points=1):
            q = Question.objects.create(quiz=quiz, type="single", text=text, points=points, order=quiz.questions.count() + 1,
                                        explanation="راجع الدرس لو الإجابة غلط.")
            for i, o in enumerate(options):
                Choice.objects.create(question=q, text=o, is_correct=(i == correct), order=i)
            return q

        def tf(quiz, text, is_true, points=1):
            q = Question.objects.create(quiz=quiz, type="true_false", text=text, points=points, order=quiz.questions.count() + 1)
            Choice.objects.create(question=q, text="صح", is_correct=is_true, order=0)
            Choice.objects.create(question=q, text="غلط", is_correct=not is_true, order=1)
            return q

        q1 = Quiz.objects.create(owner=T["teacher1"], subject=S["math"], kind="homework", title="واجب الاشتقاق 1",
                                 time_limit_minutes=20, max_attempts=2, is_published=True)
        mcq(q1, "مشتقة x² هي؟", ["2x", "x", "x²", "2"], 0, 2)
        tf(q1, "مشتقة الثابت = صفر", True)
        Question.objects.create(quiz=q1, type="short", text="مشتقة sin(x)؟", correct_text="cos(x)|cosx|cos x", points=1, order=3)
        Question.objects.create(quiz=q1, type="essay", text="اشرح قاعدة السلسلة بمثال", points=3, order=4)

        q2 = Quiz.objects.create(owner=T["teacher1"], subject=S["physics"], kind="quiz", title="اختبار قوانين نيوتن",
                                 time_limit_minutes=15, max_attempts=1, is_published=True)
        mcq(q2, "وحدة قياس القوة هي؟", ["نيوتن", "جول", "وات", "باسكال"], 0)
        mcq(q2, "القانون الأول لنيوتن يسمى قانون؟", ["القصور الذاتي", "الجاذبية", "الطاقة", "الحركة الدائرية"], 0)
        tf(q2, "القوة = الكتلة × العجلة", True)
        tf(q2, "لكل فعل رد فعل مساو له في المقدار وفي نفس الاتجاه", False)

        q3 = Quiz.objects.create(owner=T["teacher2"], subject=S["english"], kind="quiz", title="Present Perfect Quiz",
                                 time_limit_minutes=10, max_attempts=3, is_published=True)
        mcq(q3, "I ___ my homework already.", ["have finished", "finished", "finish", "am finishing"], 0)
        mcq(q3, "She has lived here ___ 2015.", ["since", "for", "from", "at"], 0)
        multi = Question.objects.create(quiz=q3, type="multiple", text="Choose all correct sentences", points=2, order=3)
        for i, (t, ok) in enumerate([("I have seen it", True), ("I have saw it", False), ("He has gone", True), ("They has eaten", False)]):
            Choice.objects.create(question=multi, text=t, is_correct=ok, order=i)

        q4 = Quiz.objects.create(owner=T["teacher3"], subject=S["quran"], kind="homework", title="أحكام النون الساكنة",
                                 max_attempts=0, is_published=True, is_public=True)
        mcq(q4, "حروف الإظهار الحلقي عددها؟", ["6", "4", "2", "15"], 0)
        mcq(q4, "الإدغام بغنة حروفه؟", ["ينمو", "يرملون", "أ ه ع ح غ خ", "ب"], 0)
        tf(q4, "الإقلاب حرفه الباء", True)

        q5 = Quiz.objects.create(owner=T["teacher4"], subject=S["chemistry"], kind="exam", title="امتحان الشهر — كيمياء",
                                 time_limit_minutes=45, max_attempts=1, is_published=True,
                                 available_until=now + dt.timedelta(days=7))
        mcq(q5, "الرقم الهيدروجيني للماء النقي؟", ["7", "1", "14", "0"], 0, 2)
        tf(q5, "الأحماض تحول ورقة عباد الشمس للأحمر", True, 2)
        Question.objects.create(quiz=q5, type="file", text="ارفع صورة حل المسألة 5", points=4, order=3)

        Quiz.objects.create(owner=T["teacher1"], subject=S["math"], kind="quiz", title="اختبار المتتابعات (مسودة)", is_published=False)

        due = now + dt.timedelta(days=3)
        assign = {q1: ["student1", "student3"], q2: ["student1", "student3"], q3: ["student1", "student2"],
                  q5: ["student1"]}
        for quiz, names in assign.items():
            for n in names:
                QuizAssignment.objects.create(quiz=quiz, student=ST[n], due_at=due)

        # محاولات خلصت: student3 حل q1 (مستني تصحيح المقالي) و q2 (اتصحح)، student2 حل q3
        def solve(quiz, student, right_ratio=0.8):
            att = Attempt.objects.create(quiz=quiz, student=student, question_order=list(quiz.questions.values_list("id", flat=True)),
                                         max_score=sum(q.points for q in quiz.questions.all()))
            for q in quiz.questions.all():
                a = Answer.objects.create(attempt=att, question=q, text_answer="cos x" if q.type == "short" else
                                          ("شرح قاعدة السلسلة..." if q.type == "essay" else ""))
                if q.type in ("single", "true_false", "multiple"):
                    good = random.random() < right_ratio
                    chosen = q.choices.filter(is_correct=good)[:1] if q.type != "multiple" else q.choices.filter(is_correct=True)
                    a.selected_choices.set(chosen)
            submit_attempt(att)
            return att
        solve(q1, ST["student3"])
        solve(q2, ST["student3"])
        solve(q3, ST["student2"], 0.6)
        solve(q3, ST["student1"], 0.9)
        for st in students[10:20]:
            solve(q4, st, random.random())

    def _seed_chat(self, T, ST, admin):
        from apps.chat.models import ContactViolation, Conversation, Message, Participant
        now = timezone.now()

        def conv(a, b, lines):
            c = Conversation.objects.create(type="direct")
            Participant.objects.create(conversation=c, user=a, last_read_at=now)
            Participant.objects.create(conversation=c, user=b, last_read_at=now - dt.timedelta(hours=3))
            t0 = now - dt.timedelta(hours=len(lines))
            for i, (who, text, flagged) in enumerate(lines):
                sender = a if who == 0 else b
                m = Message.objects.create(conversation=c, sender=sender, text="كلمني على *** أسهل" if flagged else text,
                                           original_text=text if flagged else "", is_flagged=flagged,
                                           flag_reasons=["phone", "keyword:واتس"] if flagged else [])
                Message.objects.filter(pk=m.pk).update(created_at=t0 + dt.timedelta(minutes=17 * i))
                if flagged:
                    ContactViolation.objects.create(message=m, user=sender, reasons=m.flag_reasons)
            c.last_message_at = t0 + dt.timedelta(minutes=17 * (len(lines) - 1))
            c.save(update_fields=["last_message_at"])
            return c

        conv(T["teacher1"], ST["student1"], [
            (1, "السلام عليكم يا مستر، حليت الواجب بس عندي سؤال في المسألة 3", False),
            (0, "وعليكم السلام، ابعتلي صورة الحل وأنا أشوفه", False),
            (1, "تمام، هبعتها دلوقتي", False),
            (0, "الحل صح بس انتبه لإشارة السالب في الخطوة التانية 👍", False),
            (1, "شكراً يا مستر", False),
        ])
        conv(T["teacher2"], ST["student2"], [
            (1, "Miss, can we move tomorrow's class?", False),
            (0, "اعملي طلب تغيير ميعاد من صفحة الحصة والإدارة هتوافق", False),
            (1, "ممكن رقمك أكلمك واتس أسهل؟ 01012345678", True),
        ])
        conv(T["teacher1"], ST["student3"], [
            (1, "يا مستر الحصة الجاية هنبدأ الفيزياء الحديثة؟", False),
            (0, "أيوه، راجع قوانين الموجات قبلها", False),
        ])
        conv(T["teacher4"], ST["student1"], [(0, "متنساش امتحان الشهر يوم الخميس", False)])
        sup = Conversation.objects.create(type="support")
        Participant.objects.create(conversation=sup, user=ST["student5"])
        Participant.objects.create(conversation=sup, user=admin)
        Message.objects.create(conversation=sup, sender=ST["student5"], text="دفعت ولسه الاشتراك متفعلش")
        Message.objects.create(conversation=sup, sender=admin, text="هنراجعه حالاً ونرد عليك")
        sup.last_message_at = now
        sup.save(update_fields=["last_message_at"])

    def _seed_payments(self, ST, students, P, S):
        from apps.courses.models import Course
        from apps.payments.models import Coupon, Order
        from apps.tutoring.models import Subscription
        now = timezone.now()
        Coupon.objects.create(code="WELCOME20", percent_off=20, max_uses=100, used_count=12)
        Coupon.objects.create(code="FREE100", percent_off=100, max_uses=50, used_count=3)
        Coupon.objects.create(code="RAMADAN", amount_off=100, applies_to="subscription", is_active=False)
        for sub in Subscription.objects.exclude(status="pending_payment"):
            months_ago = random.randint(0, 5)
            o = Order.objects.create(user=sub.student, student=sub.student, kind="subscription", subscription=sub,
                                     amount=sub.package.price, total=sub.package.price, status="paid",
                                     method=random.choice(["paymob", "paymob", "manual"]))
            Order.objects.filter(pk=o.pk).update(paid_at=now - dt.timedelta(days=30 * months_ago + random.randint(0, 20)))
        for c in Course.objects.filter(status="published", price__gt=0):
            for enr in c.enrollments.all()[:5]:
                o = Order.objects.create(user=enr.student, student=enr.student, kind="course", course=c, amount=c.price,
                                         total=c.price, status="paid")
                Order.objects.filter(pk=o.pk).update(paid_at=now - dt.timedelta(days=random.randint(0, 150)))
        for sub in Subscription.objects.filter(status="pending_payment")[:2]:
            Order.objects.create(user=sub.student, student=sub.student, kind="subscription", subscription=sub,
                                 amount=sub.package.price, total=sub.package.price,
                                 status=random.choice(["pending", "failed"]))

    def _seed_content(self, S, T):
        from apps.accounts.models import User
        from apps.qa import services as qa
        from apps.qa.models import Answer, Question, Vote
        from apps.seo.models import FAQ, Article, BlogCategory, Page, Tag, Testimonial

        from ._demo_content import ARTICLES, CATEGORIES, FLAGGED_ANSWER, FLAGGED_QUESTION, QUESTIONS
        now = timezone.now()
        for i, (q, a) in enumerate([
            ("الحصص بتكون إزاي؟", "حصص لايف فردية بالصوت والصورة جوه التطبيق أو الموقع، والمدرس بيكتب تقرير بعد كل حصة."),
            ("أقدر أجرب قبل ما أدفع؟", "أيوه، الحصة التجريبية الأولى مجانية في كل مادة."),
            ("إزاي أدفع؟", "بالفيزا/ماستركارد، المحافظ الإلكترونية، أو فوري."),
            ("لو عندي سؤال بين الحصص؟", "اسأله في بنك الأسئلة والأجوبة، والمدرسين المتخصصين بيردوا عليه، أو ابعته لمدرسك في الشات."),
            ("لو فاتتني حصة؟", "لو المدرس هو اللي غاب أو لغى بتتعوض تلقائياً، ولو إنت لغيت قبلها بساعتين مش بتتخصم."),
            ("ينفع أغير المدرس؟", "أيوه، كلم الدعم من الشات والإدارة هتغيره وتحافظ على مواعيدك."),
        ]):
            FAQ.objects.create(question=q, answer=a, order=i)
        for n, r, t in [("يوسف", "طالب ثالثة ثانوي", "التقرير بعد كل حصة بيخليني أعرف أنا فين بالظبط."),
                        ("مريم", "طالبة ثانوية عامة", "أخيراً فهمت الكيمياء العضوية!"),
                        ("آدم", "طالب ابتدائي", "حفظت جزء عم في 3 شهور مع الشيخ.")]:
            Testimonial.objects.create(name=n, role=r, text=t)
        for slug, title in [("about", "من نحن"), ("terms", "الشروط والأحكام"), ("privacy", "سياسة الخصوصية")]:
            Page.objects.create(slug=slug, title=title, body=f"<p>محتوى صفحة {title}.</p>")

        # ---------- المدونة
        cats = {}
        for i, (name, slug, desc, subj) in enumerate(CATEGORIES):
            cats[slug] = BlogCategory.objects.create(name=name, slug=slug, description=desc, order=i, subject=S.get(subj) if subj else None)
        for i, a in enumerate(ARTICLES):
            art = Article.objects.create(
                title=a["title"], category=cats[a["cat"]], subject=S.get(a["subject"]) if a["subject"] else None,
                author=T[a["author"]], body=a["body"], faq=a["faq"], meta_description=a["meta"], focus_keyword=a["keyword"],
                is_featured=a["featured"], status="published", views_count=random.randint(80, 2400))
            Article.objects.filter(pk=art.pk).update(published_at=now - dt.timedelta(days=3 + i * 5))
            art.tags.set([Tag.objects.get_or_create(name=t)[0] for t in a["tags"]])
        d = Article.objects.create(title="مسودة: أخطاء شائعة في الفيزياء", author=T["teacher10"], subject=S["physics"],
                                   body="<p>مقال لسه بيتكتب...</p>", status="draft", category=cats["thanaweya"])
        Article.objects.create(title="خطة مراجعة الأحياء في آخر شهر", author=T["teacher12"], subject=S["biology"], category=cats["thanaweya"],
                               status="pending_review",
                               body="<p>" + "المراجعة الذكية بتبدأ بالأبواب الأكبر وزناً في الامتحان. " * 40 + "</p><h2>الأسبوع الأول</h2><p>الوراثة والتكاثر.</p>")

        # ---------- بنك الأسئلة
        users = {u.username: u for u in User.objects.filter(role__in=["student", "teacher"])}
        for k, (asker, subj, title, body, answers, acc, qscore) in enumerate(QUESTIONS):
            q = Question.objects.create(author=users[asker], subject=S[subj], title=title, body=body, score=qscore,
                                        views_count=random.randint(20, 900))
            created = now - dt.timedelta(days=60 - k * 2, hours=k)
            made = []
            for j, (who, text, sc) in enumerate(answers):
                an = Answer.objects.create(question=q, author=users[who], body=text, score=sc)
                Answer.objects.filter(pk=an.pk).update(created_at=created + dt.timedelta(hours=3 + j * 5))
                made.append(an)
            voters = random.sample([u for n, u in users.items() if n.startswith("student") and n != asker], k=min(4, max(qscore, 0)))
            for v in voters:
                Vote.objects.create(user=v, question=q, value=1)
            q.accepted_answer = made[acc] if acc is not None else None
            q.answers_count = len(made)
            q.save()
            Question.objects.filter(pk=q.pk).update(created_at=created, last_activity_at=created + dt.timedelta(hours=3 + len(made) * 5))
            if subj in ("math", "physics"):
                q.tags.set([Tag.objects.get_or_create(name="ثانوية عامة")[0]])
        asker, subj, title, body = FLAGGED_QUESTION
        qa.ask(users[asker], {"subject": S[subj], "title": title, "body": body})
        who, q_author, text = FLAGGED_ANSWER
        target = Question.objects.filter(author=users[q_author]).first()
        qa.answer(users[who], target, text)

    def _print_accounts(self):
        self.stdout.write(self.style.SUCCESS("\nتم توليد البيانات التجريبية ✅  — كلمة السر لكل الحسابات: admin12345\n"))
        rows = [("أدمن", "admin"), ("مشرف", "supervisor  /  supervisor2"), ("مدرس", "teacher1 … teacher12"),
                ("مدرس قيد المراجعة", "pending1  /  pending2"), ("طالب", "student1 … student30")]
        for role, names in rows:
            self.stdout.write(f"  {role:<20} {names}")
        self.stdout.write("\nافتح: http://localhost:8000/login/\n")
