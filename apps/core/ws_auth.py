"""مصادقة WebSocket بالـ JWT:  ws://host/ws/?token=<access>"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


@database_sync_to_async
def _get_user(token):
    from rest_framework_simplejwt.authentication import JWTAuthentication
    try:
        auth = JWTAuthentication()
        validated = auth.get_validated_token(token)
        return auth.get_user(validated)
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        qs = parse_qs(scope.get("query_string", b"").decode())
        token = (qs.get("token") or [None])[0]
        if not token:
            for name, value in scope.get("headers", []):
                if name == b"authorization":
                    token = value.decode().split(" ", 1)[-1]
        scope["user"] = await _get_user(token) if token else AnonymousUser()
        return await super().__call__(scope, receive, send)
