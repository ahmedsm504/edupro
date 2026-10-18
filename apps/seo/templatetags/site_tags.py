import re

from django import template
from django.utils.http import urlencode

register = template.Library()


@register.filter
def initial(name):
    """أول حرف من الاسم بعد شيل الألقاب (أ. د. م. الشيخ)."""
    n = re.sub(r"^(أ\.|د\.|م\.|الشيخ)\s*", "", str(name or "")).strip()
    return n[:1] or "؟"


@register.simple_tag(takes_context=True)
def qs(context, **kwargs):
    """يبني query string محافظ على الباقي: {% qs page=2 %}"""
    params = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            params.pop(k, None)
        else:
            params[k] = v
    if "page" not in kwargs:
        params.pop("page", None)
    s = urlencode(sorted((k, v) for k, v in params.items()))
    return f"?{s}" if s else "?"


@register.filter
def minutes(seconds):
    return round((seconds or 0) / 60)


@register.filter
def stars(value):
    v = round(float(value or 0))
    return "★" * v + "☆" * (5 - v)


@register.filter
def read_time(n):
    """وقت القراءة بالعربي الصح: دقيقة / دقيقتين / 3 دقايق / 11 دقيقة."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n <= 1:
        return "دقيقة قراءة"
    if n == 2:
        return "دقيقتين قراءة"
    return f"{n} {'دقايق' if n <= 10 else 'دقيقة'} قراءة"
