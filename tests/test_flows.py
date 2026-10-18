"""اختبارات السيناريوهات الأساسية:  python manage.py test tests"""
import datetime as dt
import hashlib
import hmac
from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.tutoring.models import Session, Subscription

PWD = "admin12345"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self._tokens = {}

    def client_for(self, phone):
        c = APIClient()
        if phone in self._tokens:
            c.credentials(HTTP_AUTHORIZATION=f"Bearer {self._tokens[phone]}")
            return c
        r = c.post("/api/v1/auth/login/", {"identifier": phone, "password": PWD}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self._tokens[phone] = r.data["access"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c

    @property
    def admin(self):
        return self.client_for("admin")

    @property
    def student(self):
        return self.client_for("student1")

    @property
    def teacher(self):
        return self.client_for("teacher1")


class AuthTests(Base):
    def test_register_login_me_refresh_logout(self):
        c = APIClient()
        r = c.post("/api/v1/auth/register/", {"full_name": "طالب جديد", "phone": "01155555555", "password": "Strong#Pass9",
                                              "role": "student"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["user"]["phone"], "+201155555555")
        self.assertIn("grade", r.data["user"]["profile"])
        r = c.post("/api/v1/auth/login/", {"identifier": "01155555555", "password": "Strong#Pass9"}, format="json")
        self.assertEqual(r.status_code, 200)
        refresh = r.data["refresh"]
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(c.get("/api/v1/me/").data["role"], "student")
        r2 = c.post("/api/v1/auth/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(c.post("/api/v1/auth/logout/", {"refresh": r2.data["refresh"]}, format="json").status_code, 204)

    def test_error_format(self):
        r = APIClient().post("/api/v1/auth/login/", {"identifier": "x", "password": "bad"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.data["success"])
        self.assertEqual(r.data["error"]["code"], "validation_error")
        r = APIClient().get("/api/v1/me/")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.data["error"]["code"], "not_authenticated")

    def test_teacher_registration_requires_approval(self):
        c = APIClient()
        r = c.post("/api/v1/auth/register/", {"full_name": "مدرس", "phone": "01166666666", "password": "Strong#Pass9",
                                              "role": "teacher", "subject_ids": [1]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["user"]["profile"]["approval_status"], "pending")
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        self.assertEqual(c.get("/api/v1/teacher/students/").status_code, 403)
        uid = r.data["user"]["id"]
        r = self.admin.post(f"/api/v1/admin/users/{uid}/teacher-review/", {"action": "approve"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(c.get("/api/v1/teacher/students/").status_code, 200)

    def test_parent_role_removed(self):
        r = APIClient().post("/api/v1/auth/register/", {"full_name": "ولي", "phone": "01188888888", "password": "Strong#Pass9",
                                                        "role": "parent"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(User.objects.filter(role="parent").exists())
        self.assertEqual(self.admin.get("/api/v1/parent/children/").status_code, 404)


class TutoringFlowTests(Base):
    def test_full_subscription_and_session_lifecycle(self):
        st = self.client_for("student26")  # عمر
        r = st.post("/api/v1/subscriptions/", {"package": 2, "subject": 2}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        sub_id = r.data["id"]
        self.assertEqual(r.data["status"], "pending_payment")

        # admin marks paid (cash) → pending_assignment
        r = self.admin.post(f"/api/v1/subscriptions/{sub_id}/mark-paid/")
        self.assertEqual(r.data["status"], "pending_assignment", r.content)

        teacher = User.objects.get(username="teacher1")
        wd = (timezone.localdate().weekday() + 1) % 7
        r = self.admin.post(f"/api/v1/subscriptions/{sub_id}/assign/",
                            {"teacher": teacher.id, "slots": [{"weekday": wd, "start_time": "20:00"}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["status"], "active")
        self.assertGreater(Session.objects.filter(subscription_id=sub_id).count(), 0)

        s = Session.objects.filter(subscription_id=sub_id).first()
        t = self.teacher
        r = t.post(f"/api/v1/sessions/{s.id}/join/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.data["error"]["code"], "session_not_started")

        s.scheduled_at = timezone.now() + dt.timedelta(minutes=2)
        s.save()
        r = t.post(f"/api/v1/sessions/{s.id}/join/")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["is_moderator"])
        self.assertEqual(r.data["room"], s.room_name)
        r = st.post(f"/api/v1/sessions/{s.id}/join/")
        self.assertFalse(r.data["is_moderator"])
        s.refresh_from_db()
        self.assertEqual(s.status, "live")

        # طالب تاني ميقدرش يدخل
        other = self.client_for("student2")
        self.assertEqual(other.post(f"/api/v1/sessions/{s.id}/join/").status_code, 404)

        r = t.post(f"/api/v1/sessions/{s.id}/end/")
        self.assertEqual(r.data["status"], "completed")
        self.assertEqual(Subscription.objects.get(pk=sub_id).sessions_used, 1)

        r = t.post(f"/api/v1/sessions/{s.id}/report/", {"topics": "قوانين نيوتن", "homework": "تمارين 1-5",
                                                       "performance": 4, "private_notes": "سري"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        r = st.get(f"/api/v1/sessions/{s.id}/")
        self.assertEqual(r.data["report"]["topics"], "قوانين نيوتن")
        self.assertNotIn("private_notes", r.data["report"])

        # review بعد حصة مكتملة
        r = st.post("/api/v1/reviews/", {"teacher": teacher.id, "rating": 5, "comment": "ممتاز"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)

    def test_late_cancel_by_student_is_counted(self):
        s = Session.objects.filter(student__username="student1", status="scheduled").first()
        s.scheduled_at = timezone.now() + dt.timedelta(minutes=30)
        s.save()
        r = self.student.post(f"/api/v1/sessions/{s.id}/cancel/", {"reason": "ظرف"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.data["counted"])

    def test_student_sees_only_own_sessions(self):
        r = self.student.get("/api/v1/sessions/?upcoming=true&page_size=100")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(r.data["count"], 0)
        me_id = self.student.get("/api/v1/me/").data["id"]
        self.assertTrue(all(x["student"]["id"] == me_id for x in r.data["results"]))

    def test_trial_request(self):
        st = self.client_for("student26")
        r = st.post("/api/v1/trials/", {"subject": 3, "preferred_times": "بعد العصر"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(st.post("/api/v1/trials/", {"subject": 3}, format="json").data["error"]["code"], "trial_exists")
        teacher = User.objects.get(username="teacher1")
        r = self.admin.post(f"/api/v1/trials/{r.data['id']}/schedule/",
                            {"teacher": teacher.id, "scheduled_at": (timezone.now() + dt.timedelta(days=1, hours=5)).isoformat()}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["status"], "scheduled")


class ChatTests(Base):
    def test_chat_rules_and_contact_filter(self):
        st = self.student
        own = User.objects.get(username="teacher1")
        stranger = User.objects.get(username="teacher3")
        r = st.post("/api/v1/chat/conversations/start/", {"user_id": stranger.id}, format="json")
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.data["error"]["code"], "chat_not_allowed")
        r = st.post("/api/v1/chat/conversations/start/", {"user_id": own.id}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        cid = r.data["id"]
        r = st.post(f"/api/v1/chat/conversations/{cid}/messages/", {"text": "كلمني واتس على ٠١٢ ٣٤٥ ٦٧٨ ٩٠"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertTrue(r.data["is_flagged"])
        self.assertNotIn("678", r.data["text"])
        r = self.admin.get("/api/v1/admin/violations/")
        self.assertGreaterEqual(r.data["count"], 2)  # واحدة من البيانات التجريبية + دي
        self.assertIn("٠١٢", r.data["results"][0]["original_text"])
        r = self.teacher.get(f"/api/v1/chat/conversations/{cid}/messages/")
        self.assertTrue(r.data["results"][0]["is_flagged"])
        self.assertEqual(self.teacher.get("/api/v1/chat/conversations/").data["results"][0]["unread_count"], 1)

    def test_clean_message_not_flagged(self):
        own = User.objects.get(username="teacher1")
        st = self.student
        cid = st.post("/api/v1/chat/conversations/start/", {"user_id": own.id}, format="json").data["id"]
        r = st.post(f"/api/v1/chat/conversations/{cid}/messages/", {"text": "حليت الواجب يا مستر، صفحة 45"}, format="json")
        self.assertFalse(r.data["is_flagged"])


class CourseAndQuizTests(Base):
    def test_courses(self):
        r = APIClient().get("/api/v1/courses/")
        self.assertGreaterEqual(r.data["count"], 2)
        paid = [c for c in r.data["results"] if c["price"] != "0.00"][0]
        free = [c for c in r.data["results"] if c["price"] == "0.00"][0]
        st = APIClient()
        reg = st.post("/api/v1/auth/register/", {"full_name": "طالب كورسات", "phone": "01177777777", "password": "Strong#Pass9",
                                                 "role": "student"}, format="json")
        st.credentials(HTTP_AUTHORIZATION=f"Bearer {reg.data['access']}")
        self.assertEqual(st.post(f"/api/v1/courses/{paid['slug']}/enroll/").status_code, 402)
        detail = st.get(f"/api/v1/courses/{paid['slug']}/").data
        locked = [l for s in detail["sections"] for l in s["lessons"] if l["locked"]][0]
        self.assertEqual(st.get(f"/api/v1/courses/{paid['slug']}/lessons/{locked['id']}/").status_code, 403)
        self.assertIn(st.post(f"/api/v1/courses/{free['slug']}/enroll/").status_code, (200,))
        d = st.get(f"/api/v1/courses/{free['slug']}/").data
        lesson = d["sections"][0]["lessons"][0]["id"]
        r = st.post(f"/api/v1/courses/{free['slug']}/lessons/{lesson}/progress/", {"completed": True, "position_seconds": 900}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertGreater(r.data["progress_percent"], 0)

    def test_quiz_flow(self):
        st = self.student
        quizzes = st.get("/api/v1/quizzes/").data["results"]
        q = [x for x in quizzes if x["title"] == "واجب الاشتقاق 1"][0]
        att = st.post(f"/api/v1/quizzes/{q['id']}/start/").data
        qs = {q["type"]: q for q in att["questions"]}
        self.assertNotIn("is_correct", qs["single"]["choices"][0])
        right = [c for c in qs["single"]["choices"] if c["text"] == "2x"][0]["id"]
        st.post(f"/api/v1/attempts/{att['id']}/answer/", {"question": qs["single"]["id"], "selected_choices": [right]}, format="json")
        st.post(f"/api/v1/attempts/{att['id']}/answer/", {"question": qs["short"]["id"], "text_answer": "cos x"}, format="json")
        st.post(f"/api/v1/attempts/{att['id']}/answer/", {"question": qs["essay"]["id"], "text_answer": "شرح"}, format="json")
        r = st.post(f"/api/v1/attempts/{att['id']}/submit/")
        self.assertEqual(r.data["status"], "submitted")
        self.assertEqual(Decimal(r.data["score"]), Decimal("3"))
        essay_ans = [a for a in r.data["answers"] if a["question"] == qs["essay"]["id"]][0]
        r = self.teacher.post(f"/api/v1/attempts/{att['id']}/grade/", {"answers": [{"answer_id": essay_ans["id"], "points_awarded": 2}]}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data["status"], "graded")
        self.assertEqual(Decimal(r.data["score"]), Decimal("5"))


@override_settings(PAYMOB_HMAC_SECRET="test-secret", PAYMOB_SECRET_KEY="", PAYMOB_PUBLIC_KEY="pk")
class PaymentTests(Base):
    def test_free_coupon_checkout_and_webhook(self):
        from apps.payments.models import Coupon, Order
        from apps.payments.paymob import HMAC_FIELDS, _fmt, _get
        Coupon.objects.update_or_create(code="FREE100", defaults={"percent_off": 100, "is_active": True, "max_uses": None})
        st = self.client_for("student26")
        sub = Subscription.objects.get(student__username="student26", status="pending_payment")
        r = st.post("/api/v1/payments/checkout/", {"kind": "subscription", "subscription_id": sub.id, "coupon": "free100"}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["order"]["status"], "paid")
        sub.refresh_from_db()
        self.assertEqual(sub.status, "pending_assignment")

        # webhook for a course order
        from apps.courses.models import Course
        course = Course.objects.filter(price__gt=0, status="published").exclude(enrollments__student=sub.student).first()
        order = Order.objects.create(user=sub.student, student=sub.student, kind="course", course=course,
                                     amount=course.price, total=course.price, paymob_order_id="999")
        obj = {"id": 123, "amount_cents": int(course.price * 100), "created_at": "2026-10-18T00:00:00", "currency": "EGP",
               "error_occured": False, "has_parent_transaction": False, "integration_id": 1, "is_3d_secure": True,
               "is_auth": False, "is_capture": False, "is_refunded": False, "is_standalone_payment": True, "is_voided": False,
               "order": {"id": 999}, "owner": 1, "pending": False,
               "source_data": {"pan": "2346", "sub_type": "MasterCard", "type": "card"}, "success": True}
        msg = "".join(_fmt(_get(obj, f)) for f in HMAC_FIELDS)
        sig = hmac.new(b"test-secret", msg.encode(), hashlib.sha512).hexdigest()
        c = APIClient()
        self.assertEqual(c.post("/api/v1/payments/paymob/webhook/?hmac=bad", {"type": "TRANSACTION", "obj": obj}, format="json").status_code, 400)
        r = c.post(f"/api/v1/payments/paymob/webhook/?hmac={sig}", {"type": "TRANSACTION", "obj": obj}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        order.refresh_from_db()
        self.assertEqual(order.status, "paid")
        self.assertTrue(course.enrollments.filter(student=sub.student).exists())


class PublicSiteTests(Base):
    def test_pages(self):
        from apps.accounts.models import TeacherProfile
        from apps.courses.models import Course
        t = TeacherProfile.objects.filter(approval_status="approved").first()
        c = Course.objects.first()
        for url in ["/", "/subjects/", "/subjects/math/", "/teachers/", t.get_absolute_url(), "/courses/",
                    c.get_absolute_url(), "/blog/", "/p/about/", "/robots.txt", "/sitemap.xml",
                    "/.well-known/assetlinks.json", "/api/v1/config/", "/api/v1/subjects/", "/api/v1/teachers/"]:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 200, f"{url}: {r.status_code}")

    def test_dashboards(self):
        for phone in ["admin", "supervisor", "teacher1", "student1"]:
            r = self.client_for(phone).get("/api/v1/dashboard/")
            self.assertEqual(r.status_code, 200, f"{phone}: {r.content[:300]}")
