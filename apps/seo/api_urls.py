from rest_framework.routers import DefaultRouter

from .blog_api import (ArticleViewSet, CategoryViewSet, FAQViewSet, ManageArticleViewSet, ManageCategoryViewSet,
                       TagViewSet)

router = DefaultRouter()
router.register("articles", ArticleViewSet, basename="articles")
router.register("blog/categories", CategoryViewSet, basename="blog-categories")
router.register("blog/tags", TagViewSet, basename="blog-tags")
router.register("blog/manage/articles", ManageArticleViewSet, basename="blog-manage-articles")
router.register("blog/manage/categories", ManageCategoryViewSet, basename="blog-manage-categories")
router.register("faqs", FAQViewSet, basename="faqs")
urlpatterns = router.urls
