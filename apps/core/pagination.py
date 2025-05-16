from collections import OrderedDict

from rest_framework.pagination import LimitOffsetPagination as BaseLimitOffsetPagination
from rest_framework.response import Response


class LimitOffsetPagination(BaseLimitOffsetPagination):
    def get_paginated_response(self, data, extra_context=()):
        return Response(
            OrderedDict(
                [
                    ("total", self.count),
                    ("count", self.get_count(data)),
                    ("next", self.get_next_link()),
                    ("previous", self.get_previous_link()),
                    ("results", data),
                    *extra_context,
                ]
            )
        )
