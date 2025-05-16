from __future__ import annotations

import logging
import types

formatter = logging.Formatter()


def process_logging(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    frame_locals = frame.f_locals
    logger_name = frame_locals["self"].name
    exc_info = frame_locals["exc_info"]
    traceback = None if exc_info is None else formatter.formatException(exc_info)
    extra = frame_locals["extra"]
    return {
        "args": frame_locals["args"],
        "extra": extra,
        "level": logging.getLevelName(frame_locals["level"]),
        "msg": frame_locals["msg"],
        "stack": formatter.formatStack(frame_locals["sinfo"]),
        "traceback": traceback,
        "name": logger_name,
    }


logging_plugin = {
    "co_names": ("_log",),
    "path_fragment": "/logging/",
    "events": ["return"],
    "call_type": "log_message",
    "return_type": "log_message",
    "process": process_logging,
}
