"""
صفحات الموقع العامة (Server-side rendered) — كلها مبنية للسيو:
canonical، Open Graph، JSON-LD (Organization/WebSite+SearchAction، Breadcrumb، Person، Course، BlogPosting، FAQPage، QAPage)،
noindex للصفحات الرقيقة (أسئلة من غير إجابة، وسوم فيها مقال واحد، نتايج البحث)، روابط داخلية كتير، و sitemap.
التطبيق نفسه (الطالب/المدرس/الإدارة) على /app/ ومبني على الـ API.
"""
import json
import time
from functools import wraps

from django.conf import settings
from django.contrib.syndication.views import Feed
from django.core.paginator import Paginator
from django.db.models import Count, F, Q
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.feedgenerator import Rss201rev2Feed
from django.views.decorators.cache import cache_page

from apps.accounts.models import TeacherProfile
from apps.catalog.models import Subject
from apps.core.richtext import excerpt, plain_text, text_to_html, with_toc
from apps.courses.models import Course
from apps.qa.models import Answer, Question
from apps.tutoring.models import Package, Review

from .models import FAQ, Article, BlogCategory, Page, Tag, Testimonial


def public_cache(seconds):
    """كاش للصفحات العامة في الإنتاج بس — في التطوير عشان تشوف تعديلاتك فوراً."""
    def deco(fn):
        cached = cache_page(seconds)(fn)

        @wraps(fn)
        def wrapper(request, *a, **kw):
            return (fn if settings.DEBUG else cached)(request, *a, **kw)
        return wrapper
    return deco


def ld(*objs):
    """JSON-LD آمن جوه <script>."""
    return [json.dumps(o, ensure_ascii=False).replace("</", "<\\/") for o in objs if o]


def abs_url(path):
    return settings.SITE_URL + path


def breadcrumb(*items):
    """items: (name, path or None)"""
    return {"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "name": n, **({"item": abs_url(p)} if p else {})} for i, (n, p) in enumerate(items)]}


def faq_schema(pairs):
    pairs = [(q, a) for q, a in pairs if q and a]
    if not pairs:
        return None
    return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
        {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]}


def page(qs, request, per=12):
    return Paginator(qs, per).get_page(request.GET.get("page"))


def approved_teachers():
    return TeacherProfile.objects.filter(approval_status="approved", user__is_active=True).select_related("user").prefetch_related("subjects")


def published_articles():
    return (Article.objects.filter(status="published", published_at__lte=timezone.now())
            .select_related("category", "subject", "author", "author__teacher_profile").prefetch_related("tags"))


def public_questions():
    return Question.objects.filter(moderation="approved").select_related("author", "subject", "author__teacher_profile")


# ============================================================ Home
@public_cache(120)
def home(request):
    faqs = list(FAQ.objects.filter(is_active=True)[:8])
    stats = {
        "teachers": TeacherProfile.objects.filter(approval_status="approved").count(),
        "subjects": Subject.objects.filter(is_active=True).count(),
        "answers": Answer.objects.filter(moderation="approved").count(),
        "courses": Course.objects.filter(status="published").count(),
    }
    ctx = {
        "subjects": Subject.objects.filter(is_active=True).annotate(
            tc=Count("teachers", filter=Q(teachers__approval_status="approved"), distinct=True)).order_by("-is_featured", "order")[:12],
        "teachers": approved_teachers().order_by("-is_featured", "-rating_avg")[:6],
        "courses": Course.objects.filter(status="published").select_related("instructor", "subject").order_by("-is_featured", "-students_count")[:3],
        "packages": Package.objects.filter(is_active=True, subject__isnull=True)[:3],
        "faqs": faqs,
        "testimonials": Testimonial.objects.filter(is_active=True)[:3],
        "articles": published_articles()[:3],
        "questions": public_questions().filter(answers_count__gt=0).order_by("-last_activity_at")[:5],
        "stats": stats,
        "crumbs": [("الرئيسية", "/"), ("المواد", None)],
        "schemas": ld(faq_schema([(f.question, f.answer) for f in faqs])),
    }
    return render(request, "seo/home.html", ctx)


# ============================================================ Subjects
@public_cache(300)
def subjects(request):
    qs = Subject.objects.filter(is_active=True).annotate(
        tc=Count("teachers", filter=Q(teachers__approval_status="approved"), distinct=True),
        qc=Count("questions", filter=Q(questions__moderation="approved"), distinct=True))
    return render(request, "seo/subjects.html", {"subjects": qs,
                                                 "schemas": ld(breadcrumb(("الرئيسية", "/"), ("المواد", None)))})


@public_cache(120)
def subject_detail(request, slug):
    subject = get_object_or_404(Subject, slug=slug, is_active=True)
    teachers = approved_teachers().filter(subjects=subject).order_by("-is_featured", "-rating_avg")[:9]
    faqs = [
        (f"إزاي أحجز مدرس {subject.name} أونلاين؟", f"اختار مدرس {subject.name} من القائمة، اطلب حصة تجريبية مجانية، وبعدها اشترك في الباقة اللي تناسبك."),
        (f"الحصة التجريبية في {subject.name} بفلوس؟", "لأ، أول حصة تجريبية في كل مادة مجانية عشان تتعرف على المدرس."),
        ("الحصص بتكون إزاي؟", "حصص لايف فردية بالصوت والصورة من الموبايل أو الكمبيوتر، والمدرس بيكتب تقرير بعد كل حصة."),
    ]
    ctx = {
        "subject": subject, "teachers": teachers,
        "courses": Course.objects.filter(subject=subject, status="published").select_related("instructor")[:6],
        "packages": Package.objects.filter(Q(subject=subject) | Q(subject__isnull=True), is_active=True),
        "questions": public_questions().filter(subject=subject, answers_count__gt=0).order_by("-score", "-last_activity_at")[:6],
        "articles": published_articles().filter(subject=subject)[:3],
        "faqs": faqs,
        "crumbs": [("الرئيسية", "/"), ("المواد", "/subjects/"), (subject.name, None)],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), ("المواد", "/subjects/"), (subject.name, None)), faq_schema(faqs)),
    }
    return render(request, "seo/subject_detail.html", ctx)


# ============================================================ Teachers
@public_cache(120)
def teachers(request):
    qs = approved_teachers()
    subject = Subject.objects.filter(slug=request.GET.get("subject")).first()
    if subject:
        qs = qs.filter(subjects=subject)
    term = request.GET.get("q", "").strip()
    if term:
        qs = qs.filter(Q(user__full_name__icontains=term) | Q(headline__icontains=term) | Q(subjects__name__icontains=term))
    gender = request.GET.get("gender")
    if gender in ("male", "female"):
        qs = qs.filter(user__gender=gender)
    sort = request.GET.get("sort", "")
    qs = qs.order_by({"exp": "-experience_years", "price": "hourly_rate"}.get(sort, "-rating_avg"), "-is_featured")
    pg = page(qs.distinct(), request, 12)
    noindex = bool(gender or sort or term or request.GET.get("page"))
    return render(request, "seo/teachers.html", {
        "page": pg, "subjects": Subject.objects.filter(is_active=True), "current_subject": subject, "noindex": noindex, "term": term,
        "crumbs": [("الرئيسية", "/"), ("المدرسين", "/teachers/" if subject else None),
                                 *([(subject.name, None)] if subject else [])],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), ("المدرسين", "/teachers/" if subject else None),
                                 *([(subject.name, None)] if subject else [])))})


@public_cache(120)
def teacher_detail(request, slug):
    t = get_object_or_404(approved_teachers(), slug=slug)
    reviews = Review.objects.filter(teacher=t.user, is_visible=True).select_related("student")[:8]
    answers = (Answer.objects.filter(author=t.user, moderation="approved", question__moderation="approved")
               .select_related("question", "question__subject").order_by("-score")[:6])
    articles = published_articles().filter(author=t.user)[:4]
    person = {
        "@context": "https://schema.org", "@type": "Person", "name": t.user.full_name, "jobTitle": t.headline or "مدرس",
        "description": t.bio[:300], "url": abs_url(t.get_absolute_url()), "knowsAbout": [s.name for s in t.subjects.all()],
        "worksFor": {"@type": "EducationalOrganization", "name": settings.SITE_NAME, "url": settings.SITE_URL},
    }
    if t.user.avatar:
        person["image"] = request.build_absolute_uri(t.user.avatar.url)
    if t.rating_count:
        person["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": float(t.rating_avg), "reviewCount": t.rating_count,
                                     "bestRating": 5, "worstRating": 1}
    first = t.subjects.first()
    return render(request, "seo/teacher_detail.html", {
        "t": t, "reviews": reviews, "answers": answers, "articles": articles,
        "answers_total": Answer.objects.filter(author=t.user, moderation="approved").count(),
        "courses": Course.objects.filter(instructor=t.user, status="published"),
        "crumbs": [("الرئيسية", "/"), ("المدرسين", "/teachers/"),
                                 *([(first.name, f"/teachers/?subject={first.slug}")] if first else []), (t.user.full_name, None)],
        "schemas": ld({**person, "@type": "Person"},
                      breadcrumb(("الرئيسية", "/"), ("المدرسين", "/teachers/"),
                                 *([(first.name, f"/teachers/?subject={first.slug}")] if first else []), (t.user.full_name, None)))})


# ============================================================ Courses
@public_cache(300)
def courses(request):
    qs = Course.objects.filter(status="published").select_related("instructor", "subject").order_by("-is_featured", "-students_count")
    subject = Subject.objects.filter(slug=request.GET.get("subject")).first()
    if subject:
        qs = qs.filter(subject=subject)
    if request.GET.get("free"):
        qs = qs.filter(price=0)
    return render(request, "seo/courses.html", {"page": page(qs, request, 12), "subjects": Subject.objects.filter(is_active=True, courses__status="published").distinct(),
                                                "current_subject": subject, "noindex": bool(request.GET.get("free") or request.GET.get("page")),
                                                "crumbs": [("الرئيسية", "/"), ("الكورسات", None)],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), ("الكورسات", None)))})


def _iso_duration(sec):
    sec = int(sec or 0)
    return f"PT{sec // 3600}H{(sec % 3600) // 60}M{sec % 60}S" if sec >= 3600 else f"PT{sec // 60}M{sec % 60}S"


@public_cache(300)
def course_detail(request, slug):
    c = get_object_or_404(Course.objects.select_related("instructor", "subject", "instructor__teacher_profile"), slug=slug, status="published")
    sections = list(c.sections.prefetch_related("lessons"))
    lessons = [l for s in sections for l in s.lessons.all()]
    total = sum(l.duration_seconds for l in lessons)
    # أول درس مجاني على يوتيوب/فيميو بيتعرض كمعاينة في الصفحة العامة (وبيطلع في جوجل كـ VideoObject)
    preview = next((l for l in lessons if l.access == "free" and l.embed_url), None)
    schema = {
        "@context": "https://schema.org", "@type": "Course", "name": c.title, "description": c.short_description or excerpt(c.description, 300),
        "inLanguage": "ar", "url": abs_url(c.get_absolute_url()),
        "provider": {"@type": "Organization", "name": settings.SITE_NAME, "sameAs": settings.SITE_URL},
        "offers": {"@type": "Offer", "price": str(c.price), "priceCurrency": c.currency, "category": "Paid" if c.price else "Free",
                   "availability": "https://schema.org/InStock"},
        "hasCourseInstance": {"@type": "CourseInstance", "courseMode": "online", "courseWorkload": f"PT{max(1, total // 3600)}H",
                              "instructor": {"@type": "Person", "name": c.instructor.full_name}},
        "numberOfLessons": len(lessons),
    }
    if c.what_you_learn:
        schema["teaches"] = c.what_you_learn
    if c.thumbnail:
        schema["image"] = abs_url(c.thumbnail.url)
    if c.rating_count:
        schema["aggregateRating"] = {"@type": "AggregateRating", "ratingValue": float(c.rating_avg), "ratingCount": c.rating_count}
    extra = []
    if preview:
        extra.append({"@context": "https://schema.org", "@type": "VideoObject", "name": f"{preview.title} — {c.title}",
                      "description": excerpt(preview.content or c.short_description or c.description, 200) or preview.title,
                      "thumbnailUrl": [preview.thumbnail or (abs_url(c.thumbnail.url) if c.thumbnail else abs_url("/static/img/logo.svg"))],
                      "uploadDate": (preview.created_at or c.created_at).isoformat(), "embedUrl": preview.embed_url.split("?")[0],
                      **({"duration": _iso_duration(preview.duration_seconds)} if preview.duration_seconds else {})})
    crumbs = [("الرئيسية", "/"), ("الكورسات", "/courses/"), (c.subject.name, f"/courses/?subject={c.subject.slug}"), (c.title, None)]
    return render(request, "seo/course_detail.html", {
        "c": c, "sections": sections, "total_minutes": total // 60, "lessons_count": len(lessons), "preview": preview,
        "free_count": sum(1 for l in lessons if l.access != "paid"),
        "reviews": c.reviews.filter(is_visible=True).select_related("student")[:6], "crumbs": crumbs,
        "schemas": ld(schema, breadcrumb(*crumbs), *extra)})


def certificate(request, code):
    """صفحة التحقق من شهادة الإتمام — قابلة للطباعة. noindex لأن فيها اسم الطالب."""
    from apps.courses.models import Certificate
    cert = get_object_or_404(Certificate.objects.select_related("course"), code=code.upper())
    return render(request, "seo/certificate.html", {"cert": cert, "noindex": True,
                                                    "crumbs": [("الرئيسية", "/"), ("التحقق من شهادة", None)]})


# ============================================================ Blog
def _blog_sidebar():
    return {
        "categories": BlogCategory.objects.annotate(n=Count("articles", filter=Q(articles__status="published"))).filter(n__gt=0),
        "popular": published_articles().order_by("-views_count")[:5],
        "tags": Tag.objects.annotate(n=Count("articles", filter=Q(articles__status="published"))).filter(n__gt=0).order_by("-n")[:16],
    }


@public_cache(120)
def blog(request):
    qs = published_articles()
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(body__icontains=q))
    featured = None if (q or request.GET.get("page")) else qs.filter(is_featured=True).first()
    if featured:
        qs = qs.exclude(pk=featured.pk)
    blog_schema = {"@context": "https://schema.org", "@type": "Blog", "name": f"مدونة {settings.SITE_NAME}", "url": abs_url("/blog/"), "inLanguage": "ar"}
    return render(request, "seo/blog.html", {"page": page(qs, request, 9), "featured": featured, "q": q, "noindex": bool(q),
                                             "title": "المدونة التعليمية", **_blog_sidebar(),
                                             "crumbs": [("الرئيسية", "/"), ("المدونة", None)],
        "schemas": ld(blog_schema, breadcrumb(("الرئيسية", "/"), ("المدونة", None)))})


@public_cache(120)
def blog_category(request, slug):
    cat = get_object_or_404(BlogCategory, slug=slug)
    return render(request, "seo/blog.html", {"page": page(published_articles().filter(category=cat), request, 9), "category": cat,
                                             "title": cat.name, **_blog_sidebar(),
                                             "crumbs": [("الرئيسية", "/"), ("المدونة", "/blog/"), (cat.name, None)],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), ("المدونة", "/blog/"), (cat.name, None)))})


@public_cache(120)
def blog_tag(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    qs = published_articles().filter(tags=tag)
    return render(request, "seo/blog.html", {"page": page(qs, request, 9), "tag": tag, "title": f"#{tag.name}", **_blog_sidebar(),
                                             "noindex": qs.count() < 3,  # صفحات الوسوم الرقيقة متتأرشفش
                                             "crumbs": [("الرئيسية", "/"), ("المدونة", "/blog/"), (f"#{tag.name}", None)],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), ("المدونة", "/blog/"), (f"#{tag.name}", None)))})


def article_detail(request, slug):
    a = get_object_or_404(published_articles(), slug=slug)
    Article.objects.filter(pk=a.pk).update(views_count=F("views_count") + 1)
    from .blog_api import related_articles
    body, toc = with_toc(a.body)
    author = a.author
    tp = getattr(author, "teacher_profile", None) if author else None
    url = abs_url(a.get_absolute_url())
    posting = {
        "@context": "https://schema.org", "@type": "BlogPosting", "headline": a.title[:110], "description": a.meta_description or a.excerpt,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url}, "url": url, "inLanguage": "ar",
        "datePublished": a.published_at.isoformat() if a.published_at else None, "dateModified": a.updated_at.isoformat(),
        "wordCount": a.word_count, "timeRequired": f"PT{a.reading_minutes}M",
        "keywords": ", ".join([t.name for t in a.tags.all()] + ([a.focus_keyword] if a.focus_keyword else [])),
        "articleSection": a.category.name if a.category else None,
        "author": {"@type": "Person", "name": author.full_name if author else settings.SITE_NAME,
                   **({"url": abs_url(tp.get_absolute_url()), "jobTitle": tp.headline} if tp and tp.is_approved else {})},
        "publisher": {"@type": "EducationalOrganization", "name": settings.SITE_NAME, "url": settings.SITE_URL},
    }
    if a.cover:
        posting["image"] = request.build_absolute_uri(a.cover.url)
    crumbs = [("الرئيسية", "/"), ("المدونة", "/blog/")]
    if a.category:
        crumbs.append((a.category.name, a.category.get_absolute_url()))
    crumbs.append((a.title, None))
    teachers = approved_teachers().filter(subjects=a.subject).order_by("-rating_avg")[:3] if a.subject else []
    return render(request, "seo/article.html", {
        "a": a, "body": body, "toc": toc, "related": related_articles(a), "author_profile": tp if tp and tp.is_approved else None,
        "teachers": teachers, "questions": public_questions().filter(subject=a.subject, answers_count__gt=0)[:4] if a.subject else [],
        "crumbs": [*crumbs],
        "schemas": ld(posting, breadcrumb(*crumbs), faq_schema([(x.get("q"), x.get("a")) for x in (a.faq or [])]))})


class BlogFeed(Feed):
    feed_type = Rss201rev2Feed
    title = f"{settings.SITE_NAME} — المدونة"
    link = "/blog/"
    description = "مقالات ونصايح المذاكرة من مدرسين المنصة"

    def items(self):
        return published_articles()[:30]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.excerpt

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        return item.author.full_name if item.author else settings.SITE_NAME


# ============================================================ Q&A
@public_cache(60)
def questions(request, subject_slug=None):
    qs = public_questions()
    subject = get_object_or_404(Subject, slug=subject_slug, is_active=True) if subject_slug else None
    if subject:
        qs = qs.filter(subject=subject)
    tab = request.GET.get("tab", "")
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(Q(title__icontains=search) | Q(body__icontains=search))
    if tab == "unanswered":
        qs = qs.filter(answers_count=0)
    elif tab == "popular":
        qs = qs.order_by("-score", "-answers_count", "-views_count")
    else:
        qs = qs.order_by("-last_activity_at")
    approved = Question.objects.filter(moderation="approved")
    crumbs = [("الرئيسية", "/"), ("الأسئلة والأجوبة", "/questions/" if subject else None)] + ([(subject.name, None)] if subject else [])
    return render(request, "seo/questions.html", {
        "page": page(qs, request, 15), "subject": subject, "tab": tab, "q": search,
        "subjects": Subject.objects.filter(is_active=True).annotate(n=Count("questions", filter=Q(questions__moderation="approved"))).order_by("-n"),
        "stats": {"questions": approved.count(), "answered": approved.filter(answers_count__gt=0).count(),
                  "answers": Answer.objects.filter(moderation="approved").count()},
        "top_teachers": approved_teachers().annotate(n=Count("user__answers", filter=Q(user__answers__moderation="approved"))).filter(n__gt=0).order_by("-n")[:5],
        "noindex": bool(tab or search or request.GET.get("page")),
        "crumbs": [*crumbs],
        "schemas": ld(breadcrumb(*crumbs))})


def question_detail(request, slug):
    q = get_object_or_404(public_questions(), slug=slug)
    Question.objects.filter(pk=q.pk).update(views_count=F("views_count") + 1)
    answers = sorted(q.answers.filter(moderation="approved").select_related("author", "author__teacher_profile"),
                     key=lambda a: (a.id != q.accepted_answer_id, -a.score, a.created_at))
    url = abs_url(q.get_absolute_url())

    def ans_ld(a):
        return {"@type": "Answer", "text": plain_text(text_to_html(a.body))[:2000], "dateCreated": a.created_at.isoformat(),
                "upvoteCount": max(a.score, 0), "url": f"{url}#answer-{a.id}",
                "author": {"@type": "Person", "name": a.author.full_name,
                           **({"url": abs_url(a.author.teacher_profile.get_absolute_url())}
                              if getattr(a.author, "teacher_profile", None) and a.author.teacher_profile.is_approved else {})}}
    main = {"@type": "Question", "name": q.title, "text": plain_text(q.body) or q.title, "answerCount": len(answers),
            "upvoteCount": max(q.score, 0), "dateCreated": q.created_at.isoformat(),
            "author": {"@type": "Person", "name": q.author.full_name}}
    accepted = next((a for a in answers if a.id == q.accepted_answer_id), None)
    if accepted:
        main["acceptedAnswer"] = ans_ld(accepted)
    others = [ans_ld(a) for a in answers if a is not accepted]
    if others:
        main["suggestedAnswer"] = others
    related = public_questions().filter(subject=q.subject, answers_count__gt=0).exclude(pk=q.pk).order_by("-score")[:6]
    return render(request, "seo/question_detail.html", {
        "q": q, "body_html": text_to_html(q.body), "answers": [(a, text_to_html(a.body)) for a in answers],
        "related": related, "noindex": not q.is_indexable,
        "teachers": approved_teachers().filter(subjects=q.subject).order_by("-rating_avg")[:3],
        "crumbs": [("الرئيسية", "/"), ("الأسئلة والأجوبة", "/questions/"),
                                 (q.subject.name, f"/questions/subject/{q.subject.slug}/"), (q.title, None)],
        "schemas": ld({"@context": "https://schema.org", "@type": "QAPage", "mainEntity": main} if answers else None,
                      breadcrumb(("الرئيسية", "/"), ("الأسئلة والأجوبة", "/questions/"),
                                 (q.subject.name, f"/questions/subject/{q.subject.slug}/"), (q.title, None)))})


# ============================================================ Search + misc
def search(request):
    term = request.GET.get("q", "").strip()
    res = {}
    if len(term) >= 2:
        res = {
            "teachers": approved_teachers().filter(Q(user__full_name__icontains=term) | Q(headline__icontains=term) | Q(subjects__name__icontains=term)).distinct()[:6],
            "subjects": Subject.objects.filter(is_active=True).filter(Q(name__icontains=term) | Q(name_en__icontains=term))[:6],
            "courses": Course.objects.filter(status="published").filter(Q(title__icontains=term) | Q(short_description__icontains=term)).select_related("instructor", "subject")[:6],
            "questions": public_questions().filter(Q(title__icontains=term) | Q(body__icontains=term))[:8],
            "articles": published_articles().filter(Q(title__icontains=term) | Q(excerpt__icontains=term))[:6],
        }
    return render(request, "seo/search.html", {"term": term, "res": res, "total": sum(len(v) for v in res.values()), "noindex": True})


def page_detail(request, slug):
    p = get_object_or_404(Page, slug=slug, is_published=True)
    return render(request, "seo/page.html", {"p": p, "crumbs": [("الرئيسية", "/"), (p.title, None)],
        "schemas": ld(breadcrumb(("الرئيسية", "/"), (p.title, None)))})


def app_shell(request):
    """تطبيق الويب (صفحة الدخول + لوحة كل دور). نفس الصفحة لـ /login/ و /app/ والتنقل جواها بالـ hash."""
    resp = render(request, "app/index.html", {"ASSET_V": int(time.time()) if settings.DEBUG else "3"})
    resp["Cache-Control"] = "no-store"
    return resp


def robots_txt(request):
    lines = ["User-agent: *", "Disallow: /admin/", "Disallow: /api/", "Disallow: /app/", "Disallow: /login/",
             "Disallow: /search/", "Disallow: /payments/", "Allow: /api/docs/", "", f"Sitemap: {settings.SITE_URL}/sitemap.xml"]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def assetlinks(request):
    """Android App Links — عشان روابط الموقع تفتح التطبيق مباشرة."""
    return JsonResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": settings.ANDROID_PACKAGE,
                   "sha256_cert_fingerprints": settings.ANDROID_SHA256_FINGERPRINTS},
    }], safe=False)


def apple_app_site_association(request):
    """iOS Universal Links."""
    return JsonResponse({"applinks": {"apps": [], "details": [{
        "appIDs": [settings.IOS_APP_ID] if settings.IOS_APP_ID else [],
        "components": [{"/": "/teachers/*"}, {"/": "/courses/*"}, {"/": "/subjects/*"}, {"/": "/blog/*"}, {"/": "/questions/*"}],
    }]}})


def not_found(request, exception=None):
    return render(request, "seo/404.html", {"noindex": True,
                                            "subjects": Subject.objects.filter(is_active=True, is_featured=True)[:8]}, status=404)


def favicon(request):
    from django.shortcuts import redirect
    from django.templatetags.static import static
    return redirect(static("img/logo.svg"), permanent=True)


def stale_service_worker(request):
    """
    المتصفح بيطلب /firebase-messaging-sw.js لو كان فيه service worker قديم متسجل على نفس العنوان
    (مثلاً من مشروع تاني كان شغال على localhost:8000). بنرجّع worker بيلغي نفسه عشان الطلبات دي تقف.
    """
    from django.http import HttpResponse
    js = "self.addEventListener('install',()=>self.skipWaiting());" \
         "self.addEventListener('activate',e=>e.waitUntil(self.registration.unregister()));"
    r = HttpResponse(js, content_type="application/javascript")
    r["Cache-Control"] = "no-store"
    return r
