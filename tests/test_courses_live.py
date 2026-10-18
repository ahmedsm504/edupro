"""الكورسات المسجلة (فيديوهات محمية + مجاني/مدفوع) وغرفة الحصة:  python manage.py test tests.test_courses_live"""
import datetime as dt
import re
from pathlib import Path

from django.core import signing
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.courses.models import Certificate, Course, Enrollment, Lesson
from apps.courses.video import parse_video_url
from apps.tutoring.models import Session, Subscription

PWD = "admin12345"
SAMPLE = Path(__file__).resolve().parent.parent / "apps/core/management/commands/demo_assets/sample.mp4"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        cache.clear()
        self.course = Course.objects.get(subject__slug="math", status="published")
        self.lessons = list(Lesson.objects.filter(section__course=self.course).order_by("section__order", "order"))

    def login(self, username):
        c = APIClient()
        r = c.post("/api/v1/auth/login/", {"identifier": username, "password": PWD}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c

    def outsider(self):
        """طالب مش مشترك في الكورس ولا عنده اشتراك حصص مع المدرس."""
        subs = Subscription.objects.filter(teacher=self.course.instructor, status="active").values("student")
        u = (User.objects.filter(role="student").exclude(enrollments__course=self.course).exclude(pk__in=subs).first())
        return u


class VideoLinkTests(TestCase):
    def test_parse_any_youtube_link(self):
        for url in ["https://youtu.be/WUvTyaaNkzM", "https://www.youtube.com/watch?v=WUvTyaaNkzM&t=3s", "youtube.com/shorts/WUvTyaaNkzM",
                    "https://m.youtube.com/watch?v=WUvTyaaNkzM", "https://www.youtube.com/embed/WUvTyaaNkzM", "https://youtube.com/live/WUvTyaaNkzM"]:
            self.assertEqual(parse_video_url(url), ("youtube", "WUvTyaaNkzM"), url)
        self.assertEqual(parse_video_url("https://vimeo.com/76979871"), ("vimeo", "76979871"))
        self.assertEqual(parse_video_url("https://cdn.x.com/a.mp4")[0], "direct")
        self.assertEqual(parse_video_url("https://youtube.com/watch?v=bad")[0], "other")


class AccessTests(Base):
    def test_free_members_paid_levels(self):
        free, members, paid = self.lessons[0], self.lessons[1], self.lessons[3]
        self.assertEqual((free.access, members.access, paid.access), ("free", "members", "paid"))
        anon = APIClient()
        d = anon.get(f"/api/v1/courses/{self.course.slug}/").data
        flat = [l for s in d["sections"] for l in s["lessons"]]
        self.assertEqual([(l["locked"], l["lock_reason"]) for l in flat[:3]], [(False, None), (True, "login"), (True, "payment")])
        self.assertEqual(anon.get(f"/api/v1/courses/{self.course.slug}/lessons/{free.id}/").status_code, 200)
        self.assertEqual(anon.get(f"/api/v1/courses/{self.course.slug}/lessons/{members.id}/").data["error"]["code"], "login_required")
        st = self.login(self.outsider().username)
        self.assertEqual(st.get(f"/api/v1/courses/{self.course.slug}/lessons/{members.id}/").status_code, 200)
        r = st.get(f"/api/v1/courses/{self.course.slug}/lessons/{paid.id}/")
        self.assertEqual((r.status_code, r.data["error"]["code"]), (403, "lesson_locked"))

    def test_live_subscription_unlocks_course(self):
        sub = Subscription.objects.filter(teacher=self.course.instructor, status="active").first()
        Enrollment.objects.filter(student=sub.student, course=self.course).delete()
        st = self.login(sub.student.username)
        d = st.get(f"/api/v1/courses/{self.course.slug}/").data
        self.assertEqual(d["access"], {"full": True, "via": "subscription"})
        self.assertIn(self.course.slug, [c["slug"] for c in st.get("/api/v1/courses/?for_me=true").data["results"]])
        self.assertEqual(st.get(f"/api/v1/courses/{self.course.slug}/lessons/{self.lessons[3].id}/").status_code, 200)
        # لو الاشتراك وقف، الكورس يتقفل تاني
        Subscription.objects.filter(student=sub.student, teacher=self.course.instructor).update(status="expired")
        self.assertEqual(st.get(f"/api/v1/courses/{self.course.slug}/lessons/{self.lessons[3].id}/").status_code, 403)

    def test_protected_stream_with_range(self):
        up = next(l for l in self.lessons if l.video_file)
        sub = Subscription.objects.filter(teacher=self.course.instructor, status="active").first()
        st = self.login(sub.student.username)
        j = st.get(f"/api/v1/courses/{self.course.slug}/lessons/{up.id}/").data
        self.assertEqual(j["video_provider"], "upload")
        self.assertNotIn("private_media", str(j))         # مفيش مسار حقيقي للملف
        self.assertIn(sub.student.full_name, j["watermark"])
        path = re.sub(r"^https?://[^/]+", "", j["stream_url"])
        r = APIClient().get(path, HTTP_RANGE="bytes=0-99")  # الرابط الموقّع لوحده كفاية (عشان <video>)
        self.assertEqual(r.status_code, 206)
        self.assertEqual(len(b"".join(r.streaming_content)), 100)
        self.assertTrue(r["Content-Range"].startswith("bytes 0-99/"))
        self.assertEqual(APIClient().get(path.replace(path.split("/")[-2], "tampered:x"), {"k": "v"}).status_code, 404)
        with override_settings(VIDEO_LINK_TTL_MINUTES=-1):
            self.assertEqual(APIClient().get(path).status_code, 410)
        # الملف مش متاح من /media/
        self.assertEqual(APIClient().get(f"/media/{up.video_file.name}").status_code, 404)

    def test_progress_notes_and_certificate(self):
        st_user = self.outsider()
        Enrollment.objects.create(student=st_user, course=self.course, source="purchase")
        st = self.login(st_user.username)
        les = self.lessons[2]
        n = st.post(f"/api/v1/courses/{self.course.slug}/lessons/{les.id}/notes/", {"position_seconds": 42, "text": "القانون مهم"}, format="json")
        self.assertEqual(n.status_code, 201)
        self.assertEqual(st.get(f"/api/v1/courses/{self.course.slug}/lessons/{les.id}/notes/").data[0]["position_seconds"], 42)
        for l in self.lessons:
            r = st.post(f"/api/v1/courses/{self.course.slug}/lessons/{l.id}/progress/", {"completed": True, "position_seconds": 10}, format="json")
            self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["progress_percent"], 100)
        cert = Certificate.objects.get(student=st_user, course=self.course)
        self.assertEqual(st.get("/api/v1/my/certificates/").data["results"][0]["code"], cert.code)
        page = APIClient().get(f"/certificates/{cert.code}/")
        self.assertContains(page, st_user.full_name)
        self.assertContains(page, "noindex")


class InstructorTests(Base):
    def test_teacher_builds_course(self):
        t = self.login(self.course.instructor.username)
        outline = t.get(f"/api/v1/instructor/courses/{self.course.id}/outline/").data
        sec = outline[0]["id"]
        r = t.post("/api/v1/instructor/lessons/", {"section": sec, "title": "درس يوتيوب", "type": "video",
                                                   "video_url": "https://youtu.be/WUvTyaaNkzM?si=x", "access": "free"}, format="json")
        self.assertEqual((r.status_code, r.data["video_provider"], r.data["video_id"]), (201, "youtube", "WUvTyaaNkzM"))
        self.assertIn("youtube-nocookie.com/embed/WUvTyaaNkzM", r.data["embed_url"])
        up = t.post("/api/v1/instructor/lessons/", {"section": sec, "title": "فيديو مرفوع", "type": "video",
                                                    "video_file": SimpleUploadedFile("lesson.mp4", SAMPLE.read_bytes(), "video/mp4")}, format="multipart")
        self.assertEqual((up.status_code, up.data["has_video_file"], up.data["video_provider"]), (201, True, "upload"))
        self.assertNotIn("video_file", up.data)  # مسار الملف ما بيرجعش
        bad = t.post("/api/v1/instructor/lessons/", {"section": sec, "title": "x", "type": "video",
                                                     "video_file": SimpleUploadedFile("a.exe", b"MZ")}, format="multipart")
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(t.post("/api/v1/instructor/lessons/", {"section": sec, "title": "x", "type": "video"}, format="json").status_code, 400)
        # التحويل من فيديو مرفوع لرابط يمسح الملف
        lid = up.data["id"]
        f = Lesson.objects.get(pk=lid).video_file
        self.assertTrue(f.storage.exists(f.name))
        t.patch(f"/api/v1/instructor/lessons/{lid}/", {"video_url": "https://vimeo.com/76979871"}, format="json")
        self.assertFalse(f.storage.exists(f.name))
        # ترتيب + نقل درس لوحدة تانية
        ids = [l["id"] for l in outline[0]["lessons"]]
        r = t.post(f"/api/v1/instructor/courses/{self.course.id}/reorder/", {"lessons": {str(outline[1]["id"]): ids[::-1]}}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Lesson.objects.get(pk=ids[-1]).section_id, outline[1]["id"])
        self.assertEqual(Lesson.objects.get(pk=ids[-1]).order, 1)

    def test_admin_controls_free_lessons(self):
        t = self.login(self.course.instructor.username)
        a = self.login("admin")
        ids = [self.lessons[4].id, self.lessons[5].id]
        with override_settings(TEACHER_CAN_SET_FREE_LESSONS=False):
            self.assertEqual(t.post(f"/api/v1/instructor/courses/{self.course.id}/lessons-access/", {"lesson_ids": ids, "access": "free"}, format="json").status_code, 403)
            self.assertEqual(t.patch(f"/api/v1/instructor/lessons/{ids[0]}/", {"access": "free"}, format="json").status_code, 400)
            r = a.post(f"/api/v1/instructor/courses/{self.course.id}/lessons-access/", {"lesson_ids": ids, "access": "free"}, format="json")
            self.assertEqual(r.data, {"updated": 2})
        self.assertEqual(set(Lesson.objects.filter(pk__in=ids).values_list("access", flat=True)), {"free"})

    def test_other_teacher_cannot_touch_course(self):
        other = User.objects.filter(role="teacher").exclude(pk=self.course.instructor_id).exclude(username__startswith="pending").first()
        t = self.login(other.username)
        self.assertEqual(t.get(f"/api/v1/instructor/courses/{self.course.id}/").status_code, 404)
        sec = self.course.sections.first().id
        self.assertEqual(t.post("/api/v1/instructor/lessons/", {"section": sec, "title": "x", "type": "text"}, format="json").status_code, 403)

    def test_public_course_page_preview_schema(self):
        r = APIClient().get(self.course.get_absolute_url())
        self.assertContains(r, '"@type": "VideoObject"')
        self.assertContains(r, "معاينة مجانية")


class LiveRoomTests(Base):
    def _session(self):
        s = Session.objects.filter(status__in=["scheduled", "live"], scheduled_at__lte=timezone.now() + dt.timedelta(minutes=5),
                                   scheduled_at__gte=timezone.now() - dt.timedelta(minutes=50)).first()
        self.assertIsNotNone(s)
        return s

    def test_room_flow_with_feedback(self):
        s = self._session()
        st, t = self.login(s.student.username), self.login(s.teacher.username)
        d = st.get(f"/api/v1/sessions/{s.id}/").data
        for k in ("join_opens_at", "server_time", "previous_homework", "feedback"):
            self.assertIn(k, d)
        j = t.post(f"/api/v1/sessions/{s.id}/join/").data
        self.assertTrue(j["is_moderator"])
        self.assertIn("external_api_url", j)
        self.assertEqual(st.post(f"/api/v1/sessions/{s.id}/feedback/", {"rating": 5}, format="json").data["error"]["code"], "invalid_status")
        self.assertFalse(st.post(f"/api/v1/sessions/{s.id}/join/").data["is_moderator"])
        t.post(f"/api/v1/sessions/{s.id}/end/")
        self.assertEqual(t.post(f"/api/v1/sessions/{s.id}/feedback/", {"rating": 5}, format="json").status_code, 403)
        r = st.post(f"/api/v1/sessions/{s.id}/feedback/", {"rating": 2, "issues": ["audio", "connection"], "comment": "الصوت كان بيقطع"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        # تقييم ضعيف بيوصل للإدارة
        from apps.notifications.models import Notification
        self.assertTrue(Notification.objects.filter(type="session_low_rating").exists())
        self.assertEqual(self.login("admin").get(f"/api/v1/sessions/{s.id}/").data["feedback"]["rating"], 2)

    def test_jaas_token(self):
        import tempfile
        import jwt
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as f:
            f.write(pem)
        s = self._session()
        with override_settings(JITSI_JAAS_APP_ID="vpaas-magic-cookie-test", JITSI_JAAS_KID="vpaas-magic-cookie-test/abc", JITSI_JAAS_PRIVATE_KEY_FILE=f.name):
            j = self.login(s.teacher.username).post(f"/api/v1/sessions/{s.id}/join/").data
        self.assertEqual((j["provider"], j["domain"]), ("jaas", "8x8.vc"))
        self.assertTrue(j["room"].startswith("vpaas-magic-cookie-test/"))
        claims = jwt.decode(j["jwt"], key.public_key(), algorithms=["RS256"], audience="jitsi")
        self.assertEqual(claims["context"]["user"]["moderator"], "true")
        self.assertEqual(jwt.get_unverified_header(j["jwt"])["kid"], "vpaas-magic-cookie-test/abc")
