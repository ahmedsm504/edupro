"""
اتصال WebSocket واحد لكل مستخدم:  wss://domain/ws/?token=<JWT access>

السيرفر بيبعت أحداث بالشكل ده:
  {"event": "message.new", "data": {...}}
  events: message.new | message.read | message.deleted | typing | notification.new | session.updated | pong

العميل يقدر يبعت:
  {"action": "ping"}
  {"action": "typing", "conversation_id": 5, "is_typing": true}
  {"action": "read", "conversation_id": 5}
  {"action": "send_message", "conversation_id": 5, "text": "...", "client_id": "uuid-اختياري"}
"""
import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.notifications.services import user_group


class UserSocketConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        self.user = user
        self.group = user_group(user.id)
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
        await self.send_json({"event": "connected", "data": {"user_id": user.id}})

    async def disconnect(self, code):
        if hasattr(self, "group"):
            await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive_json(self, content, **kwargs):
        action = content.get("action")
        try:
            if action == "ping":
                await self.send_json({"event": "pong", "data": {}})
            elif action == "typing":
                await self._typing(content.get("conversation_id"), bool(content.get("is_typing", True)))
            elif action == "read":
                await self._read(content.get("conversation_id"))
            elif action == "send_message":
                msg_id = await self._send(content.get("conversation_id"), content.get("text", ""))
                await self.send_json({"event": "message.ack", "data": {"client_id": content.get("client_id"), "message_id": msg_id}})
            else:
                await self.send_json({"event": "error", "data": {"code": "unknown_action", "message": "action غير معروف"}})
        except Exception as e:  # noqa
            code = getattr(e, "error_code", "error")
            await self.send_json({"event": "error", "data": {"code": code, "message": str(getattr(e, "detail", e)),
                                                             "client_id": content.get("client_id")}})

    async def push_event(self, event):
        await self.send_json({"event": event["event"], "data": event["data"]})

    # ---- db helpers
    @database_sync_to_async
    def _conv(self, cid):
        from apps.core.exceptions import BusinessError
        from .models import Conversation
        from .services import is_member
        conv = Conversation.objects.filter(pk=cid).first()
        if not conv or not is_member(self.user, conv):
            raise BusinessError("محادثة غير موجودة.", code="not_found")
        return conv

    async def _typing(self, cid, is_typing):
        from .services import typing
        conv = await self._conv(cid)
        await database_sync_to_async(typing)(self.user, conv, is_typing)

    async def _read(self, cid):
        from .services import mark_read
        conv = await self._conv(cid)
        await database_sync_to_async(mark_read)(self.user, conv)

    async def _send(self, cid, text):
        from .services import send_message
        conv = await self._conv(cid)
        msg = await database_sync_to_async(send_message)(self.user, conv, text=text)
        return msg.id
