from asgiref.sync import sync_to_async
from channels.testing import WebsocketCommunicator
from django.core.management import call_command
from django.test import TransactionTestCase
from rest_framework_simplejwt.tokens import RefreshToken

from config.asgi import application


class WebSocketTests(TransactionTestCase):
    def setUp(self):
        call_command("seed_demo", verbosity=0)

    async def test_ws_chat_roundtrip(self):
        from apps.accounts.models import User
        from apps.chat.services import get_or_create_direct
        student = await sync_to_async(User.objects.get)(username="student1")
        teacher = await sync_to_async(User.objects.get)(username="teacher1")
        conv, _ = await sync_to_async(get_or_create_direct)(student, teacher)
        tok_s = str((await sync_to_async(RefreshToken.for_user)(student)).access_token)
        tok_t = str((await sync_to_async(RefreshToken.for_user)(teacher)).access_token)

        bad = WebsocketCommunicator(application, "/ws/?token=bad", headers=[(b"origin", b"http://localhost")])
        ok, _ = await bad.connect()
        self.assertFalse(ok)

        ws_s = WebsocketCommunicator(application, f"/ws/?token={tok_s}", headers=[(b"origin", b"http://localhost")])
        ws_t = WebsocketCommunicator(application, f"/ws/?token={tok_t}")  # موبايل: من غير Origin
        self.assertTrue((await ws_s.connect())[0])
        self.assertTrue((await ws_t.connect())[0])
        self.assertEqual((await ws_s.receive_json_from())["event"], "connected")
        self.assertEqual((await ws_t.receive_json_from())["event"], "connected")

        await ws_s.send_json_to({"action": "typing", "conversation_id": conv.id})
        self.assertEqual((await ws_t.receive_json_from(timeout=3))["event"], "typing")

        await ws_s.send_json_to({"action": "send_message", "conversation_id": conv.id, "text": "السلام عليكم", "client_id": "c1"})
        msg = None
        for _ in range(5):
            e = await ws_t.receive_json_from(timeout=3)
            if e["event"] == "message.new":
                msg = e
                break
        self.assertIsNotNone(msg)
        self.assertEqual(msg["data"]["message"]["text"], "السلام عليكم")
        await ws_s.disconnect()
        await ws_t.disconnect()
