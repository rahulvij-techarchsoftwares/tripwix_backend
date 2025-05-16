from __future__ import annotations

import gzip
import json
import logging
import os
import types
from datetime import date, datetime, time
from decimal import Decimal
from email.message import Message
from email.utils import collapse_rfc2231_value
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, TypedDict, TypeVar

try:
    from django.db.models import QuerySet
except ImportError:
    QuerySet = None  # type: ignore

import msgpack

logger = logging.getLogger("kolo")


if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse, StreamingHttpResponse


class UserCodeCallSite(TypedDict):
    line_number: int
    call_frame_id: str


def user_code_call_site(
    call_frames: List[Tuple[types.FrameType, str]],
    frame_id: str,
) -> UserCodeCallSite | None:
    count = len(call_frames)
    if count == 0:
        return None

    call_frame, call_frame_id = call_frames[-1]

    # If `frame_id` is set in a `return` frame, we want to skip it
    if call_frame_id == frame_id:
        if count == 1:
            return None
        call_frame, call_frame_id = call_frames[-2]

    return {
        "call_frame_id": call_frame_id,
        "line_number": call_frame.f_lineno,
    }


Local = TypeVar("Local")


SERIALIZE_PATH = os.path.normpath("kolo/serialize.py")


# TODO: Make these threadlocals when we support multithreading
QUERYSET_PATCHED = False
IN_KOLO_PROFILER = False


def monkeypatch_queryset_repr():
    global QUERYSET_PATCHED
    if QUERYSET_PATCHED:
        return

    try:
        from django.db.models import QuerySet
    except ImportError:  # pragma: no cover
        QUERYSET_PATCHED = True
        return

    old_repr = QuerySet.__repr__

    def new_repr(queryset):
        if getattr(queryset, "_result_cache", None) is None and IN_KOLO_PROFILER:
            return f"Unevaluated queryset for: {queryset.model}"
        return old_repr(queryset)

    QuerySet.__repr__ = new_repr  # type: ignore
    QUERYSET_PATCHED = True


def msgpack_encode_hook(obj):
    try:
        if isinstance(obj, tuple):
            return msgpack.ExtType(6, _dump_msgpack(list(obj)))

        if isinstance(obj, set):
            return msgpack.ExtType(7, _dump_msgpack(list(obj)))

        if isinstance(obj, frozenset):
            return msgpack.ExtType(8, _dump_msgpack(list(obj)))

        if isinstance(obj, dict):
            return dict(obj)

        if isinstance(obj, datetime):
            return msgpack.ExtType(1, obj.isoformat().encode("utf-8"))

        if isinstance(obj, date):
            return msgpack.ExtType(2, obj.isoformat().encode("utf-8"))

        if isinstance(obj, time):
            return msgpack.ExtType(3, obj.isoformat().encode("utf-8"))

        if isinstance(obj, int):
            num_bytes = (obj.bit_length() + 7) // 8 + 1
            return msgpack.ExtType(4, obj.to_bytes(num_bytes, "big", signed=True))

        if isinstance(obj, Decimal):
            return msgpack.ExtType(5, str(obj).encode("utf-8"))

        if (
            QuerySet is not None
            and isinstance(obj, QuerySet)
            and obj._result_cache is None
        ):
            data = f"Unevaluated queryset for: {obj.model}".encode("utf-8")
            return msgpack.ExtType(0, data)

        return msgpack.ExtType(0, repr(obj).encode("utf-8"))
    except Exception:
        path = f"{obj.__module__}.{type(obj).__qualname__}"
        return msgpack.ExtType(127, path.encode("utf-8"))


def msgpack_decode_hook(code, data):
    if code == 0:
        return data.decode("utf-8")
    if code == 1:
        return datetime.fromisoformat(data.decode("utf-8"))
    if code == 2:
        return date.fromisoformat(data.decode("utf-8"))
    if code == 3:
        return time.fromisoformat(data.decode("utf-8"))
    if code == 4:
        return int.from_bytes(data, "big", signed=True)
    if code == 5:
        return Decimal(data.decode("utf-8"))
    if code == 6:
        return tuple(load_msgpack(data))
    if code == 7:
        return set(load_msgpack(data))
    if code == 8:
        return frozenset(load_msgpack(data))
    if code == 127:
        data = data.decode("utf-8")
        return f"KoloSerializationError: {data}"
    raise ValueError(f"Unknown msgpack extension. Code: {code}")


def _dump_msgpack(data):
    return msgpack.packb(data, default=msgpack_encode_hook, strict_types=True)


def dump_msgpack(data):
    global IN_KOLO_PROFILER
    IN_KOLO_PROFILER = True
    try:
        return _dump_msgpack(data)
    finally:
        IN_KOLO_PROFILER = False


def msgpack_encode_hook_lightweight_repr(obj):
    if isinstance(obj, tuple):
        return msgpack.ExtType(6, dump_msgpack_lightweight_repr(list(obj)))

    if isinstance(obj, set):
        return msgpack.ExtType(7, dump_msgpack_lightweight_repr(list(obj)))

    if isinstance(obj, frozenset):
        return msgpack.ExtType(8, dump_msgpack_lightweight_repr(list(obj)))

    if isinstance(obj, dict):
        return dict(obj)

    if isinstance(obj, datetime):
        return msgpack.ExtType(1, obj.isoformat().encode("utf-8"))

    if isinstance(obj, date):
        return msgpack.ExtType(2, obj.isoformat().encode("utf-8"))

    if isinstance(obj, time):
        return msgpack.ExtType(3, obj.isoformat().encode("utf-8"))

    if isinstance(obj, int):
        num_bytes = (obj.bit_length() + 7) // 8 + 1
        return msgpack.ExtType(4, obj.to_bytes(num_bytes, "big", signed=True))

    if isinstance(obj, Decimal):
        return msgpack.ExtType(5, str(obj).encode("utf-8"))

    return msgpack.ExtType(
        0, f"<{obj.__class__.__qualname__} object {id(obj)}>".encode("utf-8")
    )


def dump_msgpack_lightweight_repr(data):
    return msgpack.packb(
        data, default=msgpack_encode_hook_lightweight_repr, strict_types=True
    )


def load_msgpack(data):
    return msgpack.unpackb(data, strict_map_key=False, ext_hook=msgpack_decode_hook)


def decode_header_value(bytes_or_str: bytes | str) -> str:
    """
    Convert a bytes header value to text.

    Valid header values are expected to be ascii in modern times, but
    ISO-8859-1 (latin1) has historically been allowed.

    https://datatracker.ietf.org/doc/html/rfc7230#section-3.2.4
    """
    if isinstance(bytes_or_str, bytes):
        return bytes_or_str.decode("latin1")
    return bytes_or_str


def frame_path(frame: types.FrameType) -> str:
    path = frame.f_code.co_filename
    try:
        relative_path = os.path.relpath(path)
    except ValueError:
        relative_path = path
    return f"{relative_path}:{frame.f_lineno}"


def decode_body(body: Any, request_headers: Dict[str, str]) -> Any:
    """Convert a request body into a json-serializable form."""
    if isinstance(body, bytes):
        content_type = request_headers.get("Content-Type", "")
        m = Message()
        m["content-type"] = content_type
        charset = collapse_rfc2231_value(m.get_param("charset", "utf-8"))
        try:
            return body.decode(charset)
        except UnicodeDecodeError:
            return "<Binary request body>"
    return body


def get_content(response: HttpResponse | StreamingHttpResponse) -> str:
    if response.streaming:
        return "<Streaming Response>"

    if TYPE_CHECKING:
        assert isinstance(response, HttpResponse)
    content_encoding = response.get("Content-Encoding")
    if content_encoding == "gzip":
        content = gzip.decompress(response.content)
    else:
        content = response.content
    try:
        return content.decode(response.charset)
    except UnicodeDecodeError:
        return f"<Response with invalid charset ({response.charset})>"


def get_request_body(request: "HttpRequest") -> str:
    from django.http.request import RawPostDataException

    try:
        return request.body.decode("utf-8")
    except UnicodeDecodeError:  # pragma: no cover
        return "<Binary request body>"
    except RawPostDataException:
        return "<Request data already read>"
