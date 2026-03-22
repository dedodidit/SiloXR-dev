# backend/apps/api/pagination.py

from rest_framework.pagination import CursorPagination, PageNumberPagination


class EventCursorPagination(CursorPagination):
    """
    Cursor pagination for event history.
    Cursor pagination is required for time-series data — offset pagination
    produces inconsistent results when new events are inserted between pages.
    """
    page_size          = 50
    ordering           = "-occurred_at"
    cursor_query_param = "cursor"


class StandardPagePagination(PageNumberPagination):
    page_size             = 25
    page_size_query_param = "page_size"
    max_page_size         = 100