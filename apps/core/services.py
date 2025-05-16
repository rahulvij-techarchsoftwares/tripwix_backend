"""
Services utils.
"""

from types import TracebackType
from typing import Optional, Type

from django.conf import settings
from redis import ConnectionPool, Redis


class RedisContextManager:
    """
    Context manager for Redis connections.
    """

    def __init__(self):
        pool = ConnectionPool(
            host=settings.REDIS_HOSTNAME,
            port=settings.REDIS_PORT,
            db=settings.REDIS_CACHE_DB,
            decode_responses=True,
        )
        self.r = Redis(connection_pool=pool)

    def __enter__(self) -> Redis:
        return self.r

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        self.r.close()
