"""
فلتر منع التواصل خارج المنصة (Anti-poaching).
بيكتشف أرقام الموبايل (حتى لو مكتوبة بأرقام عربية أو بمسافات أو بالحروف)، الإيميلات، اللينكات،
وكلمات زي واتساب/تليجرام، وبيخفيها ويرجع إن الرسالة مشبوهة.
"""
import re

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

WORD_DIGITS = {
    "صفر": "0", "زيرو": "0", "واحد": "1", "اتنين": "2", "اثنين": "2", "تلاتة": "3", "ثلاثة": "3",
    "اربعة": "4", "أربعة": "4", "خمسة": "5", "ستة": "6", "سبعة": "7", "تمانية": "8", "ثمانية": "8", "تسعة": "9",
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
    "seven": "7", "eight": "8", "nine": "9",
}

KEYWORDS = [
    "واتس", "واتساب", "وتساب", "واتساپ", "whatsapp", "whats app", "wa.me", "تليجرام", "تلجرام", "تيليجرام",
    "telegram", "t.me", "فيسبوك", "فيس بوك", "facebook", "انستا", "instagram", "ماسنجر", "messenger",
    "رقمي", "رقم تليفوني", "رقم موبايلي", "رقمك", "ابعتلي رقم", "كلمني برا", "برا المنصة", "خارج المنصة",
    "زوم خاص", "zoom", "skype", "سكايب", "imo", "ايمو", "viber", "فايبر", "signal", "gmail", "hotmail",
]

EMAIL_RE = re.compile(r"[\w.+-]+\s*(@|\(at\)|\[at\]|at)\s*[\w-]+\s*(\.|dot)\s*[a-z]{2,}", re.I)
URL_RE = re.compile(r"(https?://|www\.)\S+|\b[\w-]+\.(com|net|org|me|io|link|ly|eg)\b\S*", re.I)
# 7+ أرقام مع السماح بمسافات/شرط/نقط بينهم
PHONE_RE = re.compile(r"(?:\+?\d[\s\-._/]*){7,}")


def _normalize(text: str) -> str:
    t = text.translate(ARABIC_DIGITS)
    low = t.lower()
    for w, d in WORD_DIGITS.items():
        low = re.sub(rf"\b{re.escape(w)}\b", d, low)
    return low


def scan(text: str):
    """يرجع (clean_text, reasons[]). reasons فاضية = الرسالة سليمة."""
    if not text:
        return text, []
    reasons = []
    cleaned = text.translate(ARABIC_DIGITS)

    if EMAIL_RE.search(cleaned):
        reasons.append("email")
        cleaned = EMAIL_RE.sub("***", cleaned)
    if URL_RE.search(cleaned):
        reasons.append("link")
        cleaned = URL_RE.sub("***", cleaned)
    if PHONE_RE.search(cleaned):
        reasons.append("phone")
        cleaned = PHONE_RE.sub("*** ", cleaned)

    normalized = _normalize(text)
    digits_only = re.sub(r"\D", "", normalized)
    if "phone" not in reasons and len(digits_only) >= 9 and PHONE_RE.search(normalized):
        reasons.append("phone_obfuscated")
        cleaned = "*** (تم إخفاء محتوى مخالف)"

    for kw in KEYWORDS:
        if kw in normalized:
            reasons.append(f"keyword:{kw}")
            cleaned = re.sub(re.escape(kw), "***", cleaned, flags=re.I)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned, sorted(set(reasons))
