"""
أدوات المحتوى الغني (المقالات والأسئلة):
- sanitize_html: بيشيل أي HTML خطر (script, on*, javascript:) ويسيب التنسيق الآمن بس — من غير مكتبات خارجية.
- with_toc: بيدّي كل عنوان h2/h3 id ويرجّع فهرس المحتوى.
- reading_minutes / plain_text / excerpt.
"""
import html as _html
import math
import re
from html.parser import HTMLParser

from django.utils.text import slugify

ALLOWED_TAGS = {
    "p", "br", "hr", "h2", "h3", "h4", "strong", "b", "em", "i", "u", "s", "mark", "small", "sub", "sup",
    "ul", "ol", "li", "blockquote", "pre", "code", "a", "img", "figure", "figcaption",
    "table", "thead", "tbody", "tr", "th", "td", "span", "div",
}
VOID = {"br", "hr", "img"}
ALLOWED_ATTRS = {
    "a": {"href", "title", "rel", "target"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "th": {"colspan", "rowspan", "scope"}, "td": {"colspan", "rowspan"},
    "h2": {"id"}, "h3": {"id"}, "h4": {"id"},
    "code": {"class"}, "pre": {"class"}, "span": {"class"}, "div": {"class"},
}
SAFE_URL = re.compile(r"^(https?://|/|#|mailto:)", re.I)
DROP_CONTENT = {"script", "style", "iframe", "object", "embed", "form", "input", "button", "textarea", "select", "svg", "math"}


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack, self.skip = [], [], 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT:
            self.skip += 1
            return
        if self.skip or tag not in ALLOWED_TAGS:
            return
        allowed = ALLOWED_ATTRS.get(tag, set())
        parts = []
        for k, v in attrs:
            if k not in allowed or v is None:
                continue
            if k in ("href", "src") and not SAFE_URL.match(v.strip()):
                continue
            parts.append(f'{k}="{_html.escape(v, quote=True)}"')
        if tag == "a":
            href = dict(attrs).get("href", "") or ""
            if href.startswith("http"):  # روابط خارجية: nofollow عشان السيو
                parts = [p for p in parts if not p.startswith(("rel=", "target="))]
                parts += ['rel="nofollow noopener"', 'target="_blank"']
        if tag == "img" and not any(p.startswith("loading=") for p in parts):
            parts.append('loading="lazy"')
        self.out.append(f"<{tag}{' ' + ' '.join(parts) if parts else ''}>")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip or tag not in ALLOWED_TAGS or tag in VOID:
            return
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data):
        if not self.skip:
            self.out.append(_html.escape(data, quote=False))

    def result(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitize_html(value: str) -> str:
    c = _Cleaner()
    c.feed(value or "")
    c.close()
    return c.result()


_HEADING = re.compile(r"<(h[23])(\s[^>]*)?>(.*?)</\1>", re.S | re.I)


def with_toc(body: str):
    """يرجّع (html فيه ids للعناوين, [{"id","text","level"}])."""
    toc, used = [], set()

    def repl(m):
        tag, attrs, inner = m.group(1).lower(), m.group(2) or "", m.group(3)
        text = re.sub(r"<[^>]+>", "", inner).strip()
        existing = re.search(r'id="([^"]+)"', attrs)
        hid = existing.group(1) if existing else (slugify(text, allow_unicode=True)[:60] or f"s{len(toc) + 1}")
        base, i = hid, 2
        while hid in used:
            hid = f"{base}-{i}"
            i += 1
        used.add(hid)
        toc.append({"id": hid, "text": _html.unescape(text), "level": int(tag[1])})
        attrs = re.sub(r'\sid="[^"]*"', "", attrs)
        return f'<{tag}{attrs} id="{hid}">{inner}</{tag}>'

    return _HEADING.sub(repl, body or ""), toc


def plain_text(value: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", value or ""))).strip()


def word_count(value: str) -> int:
    return len(plain_text(value).split())


def reading_minutes(value: str) -> int:
    return max(1, math.ceil(word_count(value) / 200))  # ~200 كلمة/دقيقة للعربي


def excerpt(value: str, length=160) -> str:
    t = plain_text(value)
    return t if len(t) <= length else t[: length - 1].rsplit(" ", 1)[0] + "…"


_LTR_RUN = re.compile(r"(?<![\w&])([A-Za-z0-9(][A-Za-z0-9 =+\-*/×÷^().,'²³¹⁰⁴⁵⁶⁷⁸⁹⁻√∫πθ]*[A-Za-z0-9)²³¹⁰⁴⁵⁶⁷⁸⁹'])")


def _iso_ltr(escaped: str) -> str:
    """يعزل المعادلات والكلام الإنجليزي جوه النص العربي عشان ما تتقلبش (1/R = 1/R1 + ...)."""
    def repl(m):
        run = m.group(1)
        if len(run) < 3 or not re.search(r"[A-Za-z=+\-*/^²³]", run):
            return run
        return f'<bdi dir="ltr">{run}</bdi>'
    return _LTR_RUN.sub(repl, escaped)


def text_to_html(value: str) -> str:
    """نص عادي (سؤال/إجابة) → HTML آمن بفقرات، والـ ```كود``` يتحول لـ pre."""
    value = (value or "").strip()
    out = []
    for i, chunk in enumerate(re.split(r"```", value)):
        if i % 2:
            out.append(f"<pre><code>{_html.escape(chunk.strip())}</code></pre>")
            continue
        for para in re.split(r"\n\s*\n", chunk.strip()):
            if para.strip():
                lines = [_iso_ltr(_html.escape(line)) for line in para.strip().split("\n")]
                out.append('<p dir="auto">' + "<br>".join(lines) + "</p>")
    return "".join(out)
