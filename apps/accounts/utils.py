import logging
import re

from django.conf import settings

logger = logging.getLogger(__name__)
_AR = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_phone(phone: str) -> str:
    """يوحّد صيغة الرقم: يشيل المسافات، يحول الأرقام العربية، ويحوّل 01xxxxxxxxx لـ +201xxxxxxxxx."""
    p = re.sub(r"[^\d+]", "", (phone or "").translate(_AR))
    if p.startswith("00"):
        p = "+" + p[2:]
    if re.fullmatch(r"01\d{9}", p):
        p = "+2" + p
    if not p.startswith("+") and len(p) > 10:
        p = "+" + p
    return p


def send_sms(phone: str, message: str):
    """اربط هنا مزوّد الـ SMS بتاعك (Victory Link, Twilio, ...). الافتراضي بيطبع في اللوج."""
    if settings.SMS_BACKEND == "console":
        logger.warning("SMS to %s: %s", phone, message)
        return True
    raise NotImplementedError("Configure SMS provider in apps/accounts/utils.py")
