from __future__ import annotations

import traceback
import types
from itertools import starmap
from typing import Dict, TypedDict

try:
    from django.db.models import Model as DjangoModel
except ImportError:  # pragma: no cover

    class DjangoModel:  # type: ignore
        """Stub type so isinstance returns False"""


from ..serialize import frame_path
from .core import get_ignore_frames, get_include_frames, library_filter


class ExceptionFrameInfo(TypedDict):
    path: str
    co_name: str
    locals: Dict[str, object]
    expanded_locals: Dict[str, Dict[str, object]]


def serialize_exception_frame(frame, expanded_locals) -> "ExceptionFrameInfo":
    return {
        "path": frame_path(frame),
        "co_name": frame.f_code.co_name,
        "locals": frame.f_locals,
        "expanded_locals": expanded_locals,
    }


def include_match(frame: types.FrameType, context) -> bool:
    for include_filter in context["include_frames"]:
        if include_filter(frame, event="return", arg=None):
            return True
    return False


def ignore_match(frame: types.FrameType, context) -> bool:
    for ignore_filter in context["ignore_frames"]:
        if ignore_filter(frame, event="return", arg=None):
            return True
    return False


def process_exception(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    frame_locals = frame.f_locals
    exc_type, exc_value, exc_traceback = frame_locals["exc_info"]

    recorded_exception_frames = []
    expanded_locals_for_frames = []
    frames = (frame[0] for frame in traceback.walk_tb(exc_traceback))
    for frame in frames:
        _include_match = include_match(frame, context)
        if not _include_match and ignore_match(frame, context):
            continue

        if _include_match or not library_filter(frame):
            frame_locals = frame.f_locals

            expanded_locals = {}
            for key, value in frame_locals.items():
                if hasattr(value, "__dict__") and isinstance(value, DjangoModel):
                    expanded_locals[key] = vars(value)

            recorded_exception_frames.append(frame)
            expanded_locals_for_frames.append(expanded_locals)

    exception_with_traceback = traceback.format_exception(
        exc_type, exc_value, exc_traceback
    )

    zipped_frames = zip(recorded_exception_frames, expanded_locals_for_frames)
    exception_frames = list(starmap(serialize_exception_frame, zipped_frames))
    bottom_exception_frame = exception_frames[-1] if exception_frames else None

    return {
        "exception_summary": traceback.format_exception_only(exc_type, exc_value),
        "exception_with_traceback": exception_with_traceback,
        "exception_frames": exception_frames,
        "bottom_exception_frame": bottom_exception_frame,
    }


def build_context(config):
    return {
        "include_frames": get_include_frames(config),
        "ignore_frames": get_ignore_frames(config),
    }


exception = {
    "co_names": ("handle_uncaught_exception",),
    "path_fragment": "django",
    "events": ["call"],
    "call_type": "exception",
    "return_type": "exception",
    "process": process_exception,
    "build_context": build_context,
}
