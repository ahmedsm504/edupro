"""
تكامل Jitsi (3 أوضاع، بالترتيب):
1) 8x8 JaaS: JITSI_JAAS_APP_ID + JITSI_JAAS_KID + JITSI_JAAS_PRIVATE_KEY_FILE → دومين 8x8.vc وتوكن RS256.
2) سيرفر Jitsi خاص بـ JWT: JITSI_APP_ID + JITSI_APP_SECRET (HS256).
3) من غير أي حاجة: meet.jit.si العام (للتجربة بس).
- لو JITSI_APP_ID و JITSI_APP_SECRET متظبطين (سيرفر Jitsi خاص بـ JWT) بنولّد توكن لكل مستخدم:
  المدرس moderator والطالب لا، والتوكن صالح للغرفة دي بس ولمدة الحصة.
- مهم: meet.jit.si العام بيقفل الاجتماعات المدمجة بعد 5 دقائق — لازم سيرفر خاص أو 8x8 JaaS في الإنتاج.
"""
import time

import jwt
from django.conf import settings


def _jaas_enabled():
    return bool(settings.JITSI_JAAS_APP_ID and settings.JITSI_JAAS_KID
                and (settings.JITSI_JAAS_PRIVATE_KEY or settings.JITSI_JAAS_PRIVATE_KEY_FILE))


def _jaas_key():
    if settings.JITSI_JAAS_PRIVATE_KEY:  # نص المفتاح نفسه في متغير (Railway) — \n بتتحول لسطور
        raw = settings.JITSI_JAAS_PRIVATE_KEY.strip().strip('"').strip("'")
        return raw.replace("\\n", "\n").replace("\r", "").encode()
    with open(settings.JITSI_JAAS_PRIVATE_KEY_FILE, "rb") as f:
        return f.read()


def jaas_status():
    """off | ok | bad_key — من غير ما نكشف أي حاجة من المفتاح."""
    if not _jaas_enabled():
        return "off"
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        load_pem_private_key(_jaas_key(), password=None)
        return "ok"
    except Exception:
        return "bad_key"


def _jaas_token(session, user, is_moderator):
    now = int(time.time())
    key = _jaas_key()
    claims = {
        "aud": "jitsi", "iss": "chat", "sub": settings.JITSI_JAAS_APP_ID, "room": "*",
        "nbf": now - 60, "exp": max(int(session.ends_at.timestamp()) + 30 * 60, now + 15 * 60),
        "context": {
            "user": {"id": str(user.id), "name": user.full_name, "avatar": user.avatar.url if user.avatar else "",
                     "email": user.email or "", "moderator": "true" if is_moderator else "false"},
            "features": {"livestreaming": "false", "recording": "true" if is_moderator else "false",
                         "transcription": "false", "outbound-call": "false"},
        },
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": settings.JITSI_JAAS_KID})


def build_join_payload(session, user, is_moderator: bool):
    domain = settings.JITSI_DOMAIN
    room = session.room_name
    token = None
    provider = "jitsi_public"
    if _jaas_enabled():
        domain, provider = "8x8.vc", "jaas"
        room = f"{settings.JITSI_JAAS_APP_ID}/{session.room_name}"
        token = _jaas_token(session, user, is_moderator)
    elif settings.JITSI_APP_ID and settings.JITSI_APP_SECRET:
        provider = "jitsi_jwt"
        now = int(time.time())
        exp = int(session.ends_at.timestamp()) + 30 * 60
        claims = {
            "aud": "jitsi",
            "iss": settings.JITSI_APP_ID,
            "sub": domain,
            "room": room,
            "nbf": now - 60,
            "exp": max(exp, now + 15 * 60),
            "moderator": is_moderator,
            "context": {
                "user": {
                    "id": str(user.id),
                    "name": user.full_name,
                    "avatar": user.avatar.url if user.avatar else "",
                    "email": user.email or "",
                    "moderator": "true" if is_moderator else "false",
                },
                "features": {"recording": "true" if is_moderator else "false"},
            },
        }
        token = jwt.encode(claims, settings.JITSI_APP_SECRET, algorithm="HS256")

    url = f"https://{domain}/{room}"
    if token:
        url += f"?jwt={token}"
    return {
        "provider": provider,   # jaas | jitsi_jwt | jitsi_public (التجربة: الغرفة المدمجة بتقفل بعد 5 دقايق)
        "external_api_url": f"https://{domain}/" + (f"{settings.JITSI_JAAS_APP_ID}/" if provider == "jaas" else "") + "external_api.js",
        "domain": domain,
        "server_url": f"https://{domain}",
        "room": room,
        "jwt": token,
        "url": url,
        "is_moderator": is_moderator,
        "display_name": user.full_name,
        "avatar": user.avatar.url if user.avatar else None,
        "subject": session.title or str(session.subject),
        # إعدادات مقترحة للـ SDK (jitsi_meet_flutter_sdk → configOverrides / featureFlags)
        "config_overrides": {
            "prejoinPageEnabled": False,
            "startWithAudioMuted": False,
            "startWithVideoMuted": False,
            "disableInviteFunctions": True,
            "defaultLanguage": "ar",
            "disableDeepLinking": True,
            "enableWelcomePage": False,
            "hideConferenceSubject": False,
            "toolbarButtons": ["microphone", "camera", "desktop", "chat", "raisehand", "tileview", "whiteboard",
                               "fullscreen", "settings", "hangup"] + (["mute-everyone", "security"] if is_moderator else []),
            "subject": session.title or str(session.subject),
        },
        "feature_flags": {
            "invite.enabled": False,
            "add-people.enabled": False,
            "meeting-password.enabled": False,
            "live-streaming.enabled": False,
            "recording.enabled": is_moderator,
            "chat.enabled": True,
            "welcomepage.enabled": False,
        },
        "ends_at": session.ends_at.isoformat(),
    }
