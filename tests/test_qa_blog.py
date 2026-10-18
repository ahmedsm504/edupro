"""بنك الأسئلة والمدونة:  python manage.py test tests.test_qa_blog"""
import json
import re

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.qa.models import Answer, Question
from apps.seo.models import Article

PWD = "admin12345"


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_demo", verbosity=0)

    def setUp(self):
        cache.clear()

    def login(self, username):
        c = APIClient()
        r = c.post("/api/v1/auth/login/", {"identifier": username, "password": PWD}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.data['access']}")
        return c


class QATests(Base):
    def test_full_question_flow(self):
        st, t = self.login("student20"), self.login("teacher1")
        r = st.post("/api/v1/qa/questions/", {"title": "إزاي أحل متباينة من الدرجة التانية؟", "body": "جربت أحلها زي المعادلة", "subject": 1,
                                              "tags": ["جبر", "ثانوية عامة"]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        slug = r.data["slug"]
        self.assertEqual(r.data["moderation"], "approved")
        self.assertEqual(len(r.data["tags"]), 2)
        # المدرس بيشوفه في "أسئلة في موادي"
        self.assertIn(slug, [x["slug"] for x in t.get("/api/v1/qa/questions/?tab=for_me").data["results"]])
        a = t.post(f"/api/v1/qa/questions/{slug}/answers/", {"body": "حوّلها لمعادلة الأول وحدد الجذور، وبعدين اختبر الفترات بين الجذور."}, format="json")
        self.assertEqual(a.status_code, 201, a.content)
        # تصويت + منع التصويت للنفس
        self.assertEqual(st.post(f"/api/v1/qa/answers/{a.data['id']}/vote/", {"value": 1}, format="json").data["score"], 1)
        self.assertEqual(t.post(f"/api/v1/qa/answers/{a.data['id']}/vote/", {"value": 1}, format="json").data["error"]["code"], "self_vote")
        # اختيار أفضل إجابة: صاحب السؤال بس
        self.assertEqual(t.post(f"/api/v1/qa/answers/{a.data['id']}/accept/").status_code, 403)
        self.assertEqual(st.post(f"/api/v1/qa/answers/{a.data['id']}/accept/").status_code, 200)
        d = APIClient().get(f"/api/v1/qa/questions/{slug}/").data
        self.assertTrue(d["answers"][0]["is_accepted"])
        self.assertTrue(d["answers"][0]["author"]["is_verified_teacher"])
        # الإشعار وصل للطالب
        self.assertTrue(st.get("/api/v1/notifications/?type=qa_new_answer").data["count"] >= 1)
        # الصفحة العامة فيها QAPage schema وبقت indexable
        html = self.client.get(f"/questions/{slug}/").content.decode()
        self.assertIn('"@type": "QAPage"', html)
        self.assertIn('"acceptedAnswer"', html)
        self.assertNotIn("noindex", html)

    def test_contact_info_is_held_for_moderation(self):
        st = self.login("student21")
        r = st.post("/api/v1/qa/questions/", {"title": "محتاج مدرس كيمياء ضروري جداً", "body": "كلمني على 01011122233", "subject": 3}, format="json")
        self.assertEqual(r.data["moderation"], "pending")
        slug = r.data["slug"]
        self.assertEqual(APIClient().get(f"/api/v1/qa/questions/{slug}/").status_code, 404)  # مش ظاهر للناس
        self.assertEqual(self.client.get(f"/questions/{slug}/").status_code, 404)
        adm = self.login("admin")
        q = adm.get("/api/v1/qa/moderation/").data["questions"]
        self.assertIn(slug, [x["slug"] for x in q])
        self.assertEqual(adm.post("/api/v1/qa/moderation/", {"kind": "question", "id": r.data["id"], "action": "reject"}, format="json").status_code, 200)
        self.assertEqual(Question.objects.get(slug=slug).moderation, "rejected")

    def test_unanswered_question_is_noindex(self):
        q = Question.objects.filter(moderation="approved", answers_count=0).first()
        self.assertIn("noindex", self.client.get(q.get_absolute_url()).content.decode())

    def test_validation(self):
        r = self.login("student1").post("/api/v1/qa/questions/", {"title": "قصير", "subject": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("title", r.data["error"]["details"])


class BlogTests(Base):
    def test_public_api_and_page(self):
        lst = APIClient().get("/api/v1/articles/").data
        self.assertGreaterEqual(lst["count"], 8)
        slug = lst["results"][0]["slug"]
        d = APIClient().get(f"/api/v1/articles/{slug}/").data
        self.assertTrue(d["toc"])
        self.assertIn('id="', d["body"])
        html = self.client.get(f"/blog/{slug}/").content.decode()
        self.assertIn('"@type": "BlogPosting"', html)
        self.assertIn('"@type": "BreadcrumbList"', html)
        self.assertEqual(len(APIClient().get("/api/v1/blog/categories/").data), 5)

    def test_teacher_writes_staff_publishes(self):
        t, adm = self.login("teacher2"), self.login("admin")
        body = "<h2>المقدمة</h2>" + "<p>" + "كلمة مفيدة " * 120 + "</p><script>alert(1)</script><p onclick='x()'>نص</p>"
        r = t.post("/api/v1/blog/manage/articles/", {"title": "مقال تجربة عن الإنجليزي", "body": body, "tag_names": ["إنجليزي"],
                                                     "faq": [{"q": "سؤال؟", "a": "إجابة"}]}, format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.data["status"], "draft")
        self.assertNotIn("<script", r.data["body"])
        self.assertNotIn("onclick", r.data["body"])
        aid = r.data["id"]
        self.assertEqual(APIClient().get(f"/api/v1/articles/{r.data['slug']}/").status_code, 404)  # المسودة مش منشورة
        self.assertEqual(t.post(f"/api/v1/blog/manage/articles/{aid}/submit/").data["status"], "pending_review")
        self.assertEqual(t.post(f"/api/v1/blog/manage/articles/{aid}/moderate/", {"action": "publish"}, format="json").status_code, 403)
        self.assertEqual(adm.post(f"/api/v1/blog/manage/articles/{aid}/moderate/", {"action": "publish"}, format="json").data["status"], "published")
        html = self.client.get(f"/blog/{r.data['slug']}/").content.decode()
        self.assertIn('"@type": "FAQPage"', html)
        # المدرس يشوف مقالاته بس
        self.assertTrue(all(a["author"]["id"] == t.get("/api/v1/me/").data["id"] for a in t.get("/api/v1/blog/manage/articles/").data["results"]))

    def test_short_article_cannot_be_submitted(self):
        t = self.login("teacher3")
        r = t.post("/api/v1/blog/manage/articles/", {"title": "قصير", "body": "<p>كلام قليل</p>"}, format="json")
        self.assertEqual(t.post(f"/api/v1/blog/manage/articles/{r.data['id']}/submit/").data["error"]["code"], "article_too_short")


class SEOTests(Base):
    def test_pages_and_schema(self):
        checks = {"/": ["EducationalOrganization", "SearchAction", "FAQPage"], "/subjects/math/": ["FAQPage", "BreadcrumbList"],
                  "/questions/": ["BreadcrumbList"], "/blog/": ['"Blog"']}
        for url, needles in checks.items():
            html = self.client.get(url).content.decode()
            for n in needles:
                self.assertIn(n, html, f"{url} missing {n}")
            for blob in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
                json.loads(blob)  # كل الـ JSON-LD صالح
        self.assertIn("sitemap-questions.xml", self.client.get("/sitemap.xml").content.decode())
        self.assertIn("Disallow: /app/", self.client.get("/robots.txt").content.decode())
        self.assertEqual(self.client.get("/blog/feed/").status_code, 200)
        self.assertIn("noindex", self.client.get("/search/?q=تكامل").content.decode())
