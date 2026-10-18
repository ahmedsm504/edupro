from django.contrib.sitemaps.views import index as sitemap_index
from django.contrib.sitemaps.views import sitemap
from django.urls import path

from apps.payments.views import dev_checkout, payment_result

from . import views as v
from .sitemaps import sitemaps

urlpatterns = [
    path("", v.home, name="home"),
    path("login/", v.app_shell, name="login"),
    path("signup/", v.app_shell, name="signup"),
    path("app/", v.app_shell, name="app"),
    path("subjects/", v.subjects, name="subjects"),
    path("subjects/<str:slug>/", v.subject_detail, name="subject"),
    path("teachers/", v.teachers, name="teachers"),
    path("teachers/<str:slug>/", v.teacher_detail, name="teacher"),
    path("courses/", v.courses, name="courses"),
    path("courses/<str:slug>/", v.course_detail, name="course"),
    path("certificates/<str:code>/", v.certificate, name="certificate"),
    path("blog/", v.blog, name="blog"),
    path("blog/feed/", v.BlogFeed(), name="blog-feed"),
    path("blog/category/<str:slug>/", v.blog_category, name="blog-category"),
    path("blog/tag/<str:slug>/", v.blog_tag, name="blog-tag"),
    path("blog/<str:slug>/", v.article_detail, name="article"),
    path("questions/", v.questions, name="questions"),
    path("questions/subject/<str:subject_slug>/", v.questions, name="questions-subject"),
    path("questions/<str:slug>/", v.question_detail, name="question"),
    path("search/", v.search, name="search"),
    path("p/<str:slug>/", v.page_detail, name="page"),
    path("payments/result/", payment_result, name="payment-result"),
    path("payments/dev-checkout/<uuid:reference>/", dev_checkout, name="dev-checkout"),
    path("robots.txt", v.robots_txt),
    path("favicon.ico", v.favicon),
    path("firebase-messaging-sw.js", v.stale_service_worker),
    path("sitemap.xml", sitemap_index, {"sitemaps": sitemaps, "sitemap_url_name": "sitemap-section"}, name="sitemap"),
    path("sitemap-<section>.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap-section"),
    path(".well-known/assetlinks.json", v.assetlinks),
    path(".well-known/apple-app-site-association", v.apple_app_site_association),
]
