from rest_framework.routers import DefaultRouter

from . import views as v

router = DefaultRouter()
router.register("chat/conversations", v.ConversationViewSet, basename="conversations")
router.register("chat/messages", v.MessageViewSet, basename="messages")
router.register("admin/violations", v.ViolationViewSet, basename="violations")
urlpatterns = router.urls
