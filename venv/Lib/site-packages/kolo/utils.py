import subprocess
import sys
from tempfile import NamedTemporaryFile

import msgpack


def pretty_byte_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes:5d} B"

    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    bit_length = size_bytes.bit_length() - 1
    index = bit_length // 10
    denominator = 1 << (10 * index)
    ratio = size_bytes / denominator
    return f"{ratio:5.1f} {size_name[index]}"


def maybe_format(rendered):
    rendered = maybe_isort(rendered)

    try:
        import ruff
    except ImportError:
        if len(rendered) <= 1_000_000:
            rendered = maybe_black(rendered)
        return rendered

    with NamedTemporaryFile("w+", delete=False) as f:
        f.write(rendered)
        name = f.name

    subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "format",
            name,
            "--config",
            "format.skip-magic-trailing-comma=true",
        ],
        check=True,
    )
    with open(name) as f:
        rendered = f.read()

    return rendered


def maybe_black(rendered):
    try:
        from black import format_file_contents
        from black.mode import Mode
        from black.parsing import InvalidInput
        from black.report import NothingChanged
    except ImportError:
        return rendered

    try:
        return format_file_contents(
            rendered, fast=True, mode=Mode(magic_trailing_comma=False)
        )
    except (InvalidInput, NothingChanged):
        return rendered


def maybe_isort(rendered):
    try:
        from isort.api import sort_code_string
    except ImportError:
        return rendered
    return sort_code_string(rendered)


def get_terminal_formatter(mode):
    if mode == "off":
        return None

    import os

    from pygments.formatters import (
        Terminal256Formatter,
        TerminalFormatter,
        TerminalTrueColorFormatter,
    )

    style = "monokai" if mode == "dark" else "default"

    # Derived from https://github.com/pygments/pygments/blob/e49aef678a5ce40b6ed7b38cd71dddafc12f979c/pygments/cmdline.py#L448-L453
    if os.environ.get("COLORTERM", "") in ("truecolor", "24bit"):
        return TerminalTrueColorFormatter(style=style)
    if "256" in os.environ.get("TERM", ""):
        return Terminal256Formatter(style=style)
    return TerminalFormatter(bg=mode)


def get_sql_lexer(dialect):
    from pygments.lexers import MySqlLexer, PostgresLexer, SqlLexer

    if dialect == "postgres":
        return PostgresLexer()
    if dialect == "mysql":
        return MySqlLexer()
    return SqlLexer()


def highlight_sql(query, dialect, formatter):
    if formatter is None:
        # pygments adds an extra newline while highlighting.
        # Since this looks better, we also add one ourselves here.
        return query + "\n"

    from pygments import highlight

    return highlight(query, get_sql_lexer(dialect), formatter)


def highlight_python(code, formatter):
    from pygments import highlight
    from pygments.lexers import PythonLexer

    return highlight(code, PythonLexer(), formatter)


def extract_main_frames_from_data(data):
    if "config" not in data["meta"]:
        # config is not present in old traces
        return data["frames_of_interest"]

    if data.get("threads"):
        current_thread_id = data["current_thread_id"]
        if current_thread_id in data["threads"]:
            return data["threads"][current_thread_id]["frames"]
        else:
            return []
    else:
        return data["frames_of_interest"]


def extract_http_trace_name(frames_by_thread, current_thread_id):
    """
    Extract HTTP request/response information from frames to set a trace name.
    Looks for django_request and django_response frame types from the Django filter.

    Returns:
        A formatted trace name string or None if no HTTP information found
    """
    request_frame = None
    response_frame = None

    frames_from_current_thread = frames_by_thread.get(current_thread_id, [])
    first_three = frames_from_current_thread[:3]
    last_three = frames_from_current_thread[-3:]

    relevant_frames = first_three + last_three

    unpacked_frames = [
        msgpack.unpackb(f, strict_map_key=False) for f in relevant_frames
    ]

    for frame in unpacked_frames:
        if frame.get("type") == "django_request":
            print("extracting http trace name - django request")
            if request_frame is None:
                # first frame wins
                request_frame = frame
        elif frame.get("type") == "django_response":
            # last frame wins
            response_frame = frame

    if request_frame and response_frame:
        method = request_frame.get("method")
        path = request_frame.get("path_info")
        status_code = response_frame.get("status_code")

        if method and path and status_code:
            return f"{status_code} {method} {path}"

    return None


def extract_test_trace_name(frames_by_thread, current_thread_id):
    """
    Extract test name information from frames to set a trace name.
    Looks for start_test frame type from the pytest filter.

    Returns:
        A formatted trace name string or None if no test information found
    """
    frames_from_current_thread = frames_by_thread.get(current_thread_id, [])
    if not frames_from_current_thread:
        return None

    # Look at first and last few frames to be safe
    first_three = frames_from_current_thread[:3]
    last_three = frames_from_current_thread[-3:]

    relevant_frames = first_three + last_three

    unpacked_frames = [
        msgpack.unpackb(f, strict_map_key=False) for f in relevant_frames
    ]

    start_frame = None
    end_frame = None

    for frame in unpacked_frames:
        if frame.get("type") == "start_test":
            if start_frame is None:
                # first frame wins
                start_frame = frame
        elif frame.get("type") == "end_test":
            # last frame wins
            end_frame = frame

    # We want both start and end frames to be present to ensure we have a complete test
    if start_frame and end_frame:
        test_name = start_frame.get("test_name")
        test_class = start_frame.get("test_class")

        if test_name:
            if test_class:
                return f"{test_class}.{test_name}"
            return test_name

    return None
