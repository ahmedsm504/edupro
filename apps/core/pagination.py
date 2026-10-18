from rest_framework.pagination import PageNumberPagination, CursorPagination


class StandardPagination(PageNumberPagination):
    """?page=1&page_size=20  →  {count, next, previous, results}"""
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class MessageCursorPagination(CursorPagination):
    """للشات: ?cursor=...  الأحدث أولاً (مناسب للـ infinite scroll لفوق)."""
    page_size = 30
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-created_at"
