"""API المدونة: قراءة عامة + إدارة المقالات (المدرس يكتب ويبعت للمراجعة، الإدارة تنشر)."""
from django.db.models import Count, F, Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, parsers, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from apps.catalog.serializers import SubjectMiniSerializer
from apps.core.exceptions import BusinessError
from apps.core.models import schema_safe
from apps.core.permissions import IsStaffRole, IsTeacherOrStaff, Roles
from apps.core.richtext import with_toc
from apps.notifications.services import notify, notify_staff

from .models import FAQ, Article, BlogCategory, Tag


class CategorySerializer(serializers.ModelSerializer):
    articles_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = BlogCategory
        fields = ["id", "name", "slug", "description", "subject", "order", "articles_count"]
        read_only_fields = ["slug"]


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ["id", "name", "slug"]


class AuthorSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    full_name = serializers.CharField()
    avatar = serializers.ImageField()
    headline = serializers.SerializerMethodField()
    teacher_slug = serializers.SerializerMethodField()

    def get_headline(self, u) -> str:
        tp = getattr(u, "teacher_profile", None)
        return tp.headline if tp else "فريق التحرير"

    def get_teacher_slug(self, u) -> str | None:
        tp = getattr(u, "teacher_profile", None)
        return tp.slug if tp and tp.is_approved else None


class ArticleListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    subject = SubjectMiniSerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Article
        fields = ["id", "title", "slug", "excerpt", "cover", "cover_alt", "category", "subject", "tags", "author",
                  "reading_minutes", "views_count", "is_featured", "published_at", "updated_at"]


class ArticleDetailSerializer(ArticleListSerializer):
    body = serializers.SerializerMethodField()
    toc = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()

    class Meta(ArticleListSerializer.Meta):
        fields = ArticleListSerializer.Meta.fields + ["body", "toc", "faq", "word_count", "meta_title", "meta_description", "related"]

    def get_body(self, a) -> str:
        return with_toc(a.body)[0]

    def get_toc(self, a) -> list:
        return with_toc(a.body)[1]

    def get_related(self, a) -> list:
        return ArticleListSerializer(related_articles(a), many=True, context=self.context).data


def related_articles(a, n=3):
    base = Article.objects.filter(status="published").exclude(pk=a.pk).select_related("category", "subject", "author")
    tag_ids = list(a.tags.values_list("id", flat=True))
    rel = (base.filter(Q(tags__in=tag_ids) | Q(category=a.category_id) | Q(subject=a.subject_id))
           .annotate(common=Count("tags", filter=Q(tags__in=tag_ids))).order_by("-common", "-published_at").distinct())
    out = list(rel[:n])
    if len(out) < n:
        out += list(base.exclude(pk__in=[x.pk for x in out])[: n - len(out)])
    return out


@extend_schema_view(
    list=extend_schema(summary="المقالات المنشورة",
                       parameters=[OpenApiParameter("category__slug", str), OpenApiParameter("tags__slug", str),
                                   OpenApiParameter("subject", int), OpenApiParameter("is_featured", bool), OpenApiParameter("search", str)]),
    retrieve=extend_schema(summary="مقال كامل: body فيه ids للعناوين + toc (فهرس) + faq + related"),
)
@extend_schema(tags=["Blog"])
class ArticleViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    filterset_fields = ["subject", "category", "category__slug", "tags__slug", "is_featured"]
    search_fields = ["title", "excerpt", "body"]
    ordering_fields = ["published_at", "views_count"]

    def get_queryset(self):
        return (Article.objects.filter(status="published", published_at__lte=timezone.now())
                .select_related("category", "subject", "author", "author__teacher_profile").prefetch_related("tags").distinct())

    def get_serializer_class(self):
        return ArticleDetailSerializer if self.action == "retrieve" else ArticleListSerializer

    def retrieve(self, request, *a, **kw):
        art = self.get_object()
        Article.objects.filter(pk=art.pk).update(views_count=F("views_count") + 1)
        return Response(ArticleDetailSerializer(art, context={"request": request}).data)


@extend_schema(tags=["Blog"])
class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = CategorySerializer
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"

    def get_queryset(self):
        return BlogCategory.objects.annotate(articles_count=Count("articles", filter=Q(articles__status="published")))


@extend_schema(tags=["Blog"])
class TagViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = TagSerializer
    lookup_field = "slug"
    lookup_value_regex = "[^/]+"
    search_fields = ["name"]
    queryset = Tag.objects.all()


# ---------------- إدارة المقالات ----------------
class ManageArticleSerializer(serializers.ModelSerializer):
    tag_names = serializers.ListField(child=serializers.CharField(max_length=60), write_only=True, required=False)
    tags = TagSerializer(many=True, read_only=True)
    author = AuthorSerializer(read_only=True)

    class Meta:
        model = Article
        fields = ["id", "title", "slug", "category", "subject", "tags", "tag_names", "author", "excerpt", "body", "cover",
                  "cover_alt", "faq", "meta_title", "meta_description", "focus_keyword", "status", "rejection_reason",
                  "is_featured", "noindex", "reading_minutes", "word_count", "views_count", "published_at", "updated_at"]
        read_only_fields = ["slug", "status", "rejection_reason", "reading_minutes", "word_count", "views_count", "published_at"]

    def validate_faq(self, v):
        if not isinstance(v, list) or any(not isinstance(x, dict) or not x.get("q") or not x.get("a") for x in v):
            raise serializers.ValidationError('لازم تكون [{"q": "...", "a": "..."}]')
        return v

    def _tags(self, inst, names):
        if names is not None:
            inst.tags.set([Tag.objects.get_or_create(name=n.strip())[0] for n in names if n.strip()])

    def create(self, data):
        names = data.pop("tag_names", None)
        inst = super().create(data)
        self._tags(inst, names)
        return inst

    def update(self, inst, data):
        names = data.pop("tag_names", None)
        inst = super().update(inst, data)
        self._tags(inst, names)
        return inst


@extend_schema(tags=["Blog - Manage"])
@schema_safe(Article)
class ManageArticleViewSet(viewsets.ModelViewSet):
    """المدرس: مقالاته بس (مسودة ← مراجعة). الإدارة: كل المقالات + نشر/رفض/تمييز."""
    permission_classes = [IsTeacherOrStaff]
    serializer_class = ManageArticleSerializer
    parser_classes = [parsers.JSONParser, parsers.MultiPartParser, parsers.FormParser]
    filterset_fields = ["status", "category", "subject"]
    search_fields = ["title"]

    def _staff(self):
        return self.request.user.role in Roles.STAFF or self.request.user.is_superuser

    def get_queryset(self):
        qs = Article.objects.select_related("category", "subject", "author").prefetch_related("tags").order_by("-updated_at")
        return qs if self._staff() else qs.filter(author=self.request.user)

    def perform_create(self, ser):
        ser.save(author=self.request.user, status="published" if self._staff() and self.request.data.get("publish") in (True, "true", "1") else "draft")

    def perform_update(self, ser):
        art = ser.save()
        if not self._staff() and art.status == "published":
            art.status = "pending_review"  # تعديل المدرس على مقال منشور بيرجع للمراجعة
            art.save(update_fields=["status"])

    @extend_schema(summary="إرسال المقال للمراجعة", request=None, responses=ManageArticleSerializer)
    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        art = self.get_object()
        if art.word_count < 150:
            raise BusinessError("المقال قصير — لازم 150 كلمة على الأقل عشان يتنشر.", code="article_too_short")
        art.status = "pending_review"
        art.save(update_fields=["status"])
        notify_staff("article_review", "مقال محتاج مراجعة", art.title, {"screen": "blog_manage", "id": art.id})
        return Response(ManageArticleSerializer(art, context={"request": request}).data)

    @extend_schema(summary="(إدارة) نشر/رفض/إلغاء نشر",
                   request=serializers.Serializer, responses=ManageArticleSerializer)
    @action(detail=True, methods=["post"], permission_classes=[IsStaffRole])
    def moderate(self, request, pk=None):
        art = self.get_object()
        act = request.data.get("action")
        if act == "publish":
            art.status, art.rejection_reason = "published", ""
        elif act == "reject":
            art.status, art.rejection_reason = "rejected", request.data.get("reason", "")
        elif act == "unpublish":
            art.status = "draft"
        else:
            raise BusinessError("action لازم publish أو reject أو unpublish", code="validation_error")
        art.save()
        if art.author_id and art.author_id != request.user.id:
            notify(art.author, "article_status", "تم نشر مقالك 🎉" if act == "publish" else "مقالك محتاج تعديل",
                   art.title if act == "publish" else art.rejection_reason, {"screen": "blog_manage", "id": art.id})
        return Response(ManageArticleSerializer(art, context={"request": request}).data)


@extend_schema(tags=["Blog - Manage"])
class ManageCategoryViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRole]
    serializer_class = CategorySerializer
    pagination_class = None
    queryset = BlogCategory.objects.all()


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ["id", "question", "answer"]


@extend_schema(tags=["Content"])
class FAQViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = FAQSerializer
    queryset = FAQ.objects.filter(is_active=True)
