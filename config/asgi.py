import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402
from channels.security.websocket import AllowedHostsOriginValidator  # noqa: E402

from apps.core.ws_auth import JWTAuthMiddleware  # noqa: E402
from apps.chat.routing import websocket_urlpatterns  # noqa: E402

ws_app = JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
browser_ws_app = AllowedHostsOriginValidator(ws_app)


async def websocket_entry(scope, receive, send):
    """تطبيقات الموبايل مش بتبعت Origin → تعدّي (المصادقة بالتوكن). المتصفحات بيتراجع الـ Origin بتاعها."""
    has_origin = any(name == b"origin" for name, _ in scope.get("headers", []))
    app = browser_ws_app if has_origin else ws_app
    return await app(scope, receive, send)


application = ProtocolTypeRouter({"http": django_asgi_app, "websocket": websocket_entry})
