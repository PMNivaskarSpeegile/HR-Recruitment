"""Project-wide list pagination.

WHY: list endpoints must never return an unbounded result set (a table with
10,000 candidates would crash the browser and hammer the DB). Every list view
inherits this default: 20 per page, client can request up to 100.
"""
from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
