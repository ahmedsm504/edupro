"""
روابط الفيديو: بنفهم رابط يوتيوب/فيميو/Bunny اللي المدرس بيلزقه بأي شكل، ونطلع منه embed نضيف.
والفيديو المرفوع مباشرة بيتحفظ في مكان خاص (private_media) ومحدش يوصله غير برابط موقّع مؤقت.
"""
import re
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.core import signing
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

VIDEO_EXTS = (".mp4", ".webm", ".mov", ".m4v")
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


@deconstructible
class PrivateStorage(FileSystemStorage):
    """تخزين برا MEDIA_ROOT ومن غير base_url — الملفات دي مش بتتعرض للعامة أبداً."""

    def __init__(self, **kw):
        super().__init__(base_url=None, **kw)

    # بنقرا المكان من الإعدادات كل مرة (عشان override_settings في الاختبارات يشتغل)
    @property
    def base_location(self):
        return str(settings.PRIVATE_MEDIA_ROOT)

    @property
    def location(self):
        import os
        return os.path.abspath(self.base_location)


private_storage = PrivateStorage()


def parse_video_url(url: str):
    """يرجّع (provider, video_id). provider: youtube | vimeo | bunny | direct | other."""
    url = (url or "").strip()
    if not url:
        return "", ""
    u = urlparse(url if "://" in url else "https://" + url)
    host = (u.hostname or "").lower().removeprefix("www.").removeprefix("m.")
    parts = [p for p in u.path.split("/") if p]
    if host in ("youtube.com", "youtube-nocookie.com", "music.youtube.com"):
        vid = parse_qs(u.query).get("v", [""])[0]
        if not vid and len(parts) >= 2 and parts[0] in ("embed", "shorts", "live", "v"):
            vid = parts[1]
        return ("youtube", vid) if _YT_ID.match(vid or "") else ("other", "")
    if host == "youtu.be" and parts and _YT_ID.match(parts[0]):
        return "youtube", parts[0]
    if host in ("vimeo.com", "player.vimeo.com"):
        nums = [p for p in parts if p.isdigit()]
        return ("vimeo", nums[0]) if nums else ("other", "")
    if host in ("iframe.mediadelivery.net", "video.bunnycdn.com") and len(parts) >= 3:
        return "bunny", f"{parts[-2]}/{parts[-1]}"
    if u.path.lower().endswith(VIDEO_EXTS + (".m3u8",)):
        return "direct", ""
    return "other", ""


def embed_url(provider, video_id, url=""):
    if provider == "youtube" and video_id:
        # nocookie + من غير فيديوهات مقترحة من قنوات تانية
        return f"https://www.youtube-nocookie.com/embed/{video_id}?rel=0&modestbranding=1&playsinline=1&enablejsapi=1"
    if provider == "vimeo" and video_id:
        return f"https://player.vimeo.com/video/{video_id}?dnt=1&title=0&byline=0&portrait=0"
    if provider == "bunny" and video_id:
        return f"https://iframe.mediadelivery.net/embed/{video_id}?autoplay=false&preload=true"
    return ""


def thumbnail_url(provider, video_id):
    if provider == "youtube" and video_id:
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
    return ""


# ---------- روابط موقعة للفيديو المرفوع ----------
_SALT = "lesson-video"


def make_stream_token(lesson_id: int, user_id) -> str:
    return signing.TimestampSigner(salt=_SALT).sign_object({"l": lesson_id, "u": user_id or 0})


def read_stream_token(token: str):
    """يرجّع dict فيه l و u، أو يرمي signing.BadSignature / SignatureExpired."""
    return signing.TimestampSigner(salt=_SALT).unsign_object(token, max_age=settings.VIDEO_LINK_TTL_MINUTES * 60)
