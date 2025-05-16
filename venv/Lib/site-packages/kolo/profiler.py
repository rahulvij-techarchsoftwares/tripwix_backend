from __future__ import annotations

import inspect
import logging
import platform
import sys
import threading
import time
import types
from collections import defaultdict
from collections.abc import Mapping
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol, TypeVar, overload

import httpx
import msgpack
import ulid

from kolo.threads import get_thread_id

from .config import CONFIG_KEYS_TO_OMIT_FROM_SAVED_TRACE, load_config
from .db import save_trace_in_sqlite, setup_db
from .filters.attrs import attrs_filter
from .filters.core import (
    FrameFilter,
    FrameProcessor,
    exec_filter,
    frozen_filter,
    get_ignore_frames,
    get_include_frames,
    library_filter,
)
from .filters.kolo import kolo_filter
from .filters.pypy import pypy_filter
from .filters.pytest import pytest_generated_filter
from .git import COMMIT_SHA
from .plugins import PluginProcessor, load_plugin_data
from .serialize import (
    UserCodeCallSite,
    dump_msgpack,
    dump_msgpack_lightweight_repr,
    frame_path,
    monkeypatch_queryset_repr,
    user_code_call_site,
)
from .upload import upload_to_dashboard
from .utils import extract_http_trace_name, extract_test_trace_name
from .version import __version__

logger = logging.getLogger("kolo")


class KoloLocals(threading.local):
    def __init__(self):
        self.call_frames = []
        self._frame_ids = {}


INCLUDE_FRAMES_WARNING = """\
Unexpected exception in include_frames: %s
    co_filename: %s
    co_name: %s
    event: %s
    frame locals: %s
"""
IGNORE_FRAMES_WARNING = """\
Unexpected exception in ignore_frames: %s
    co_filename: %s
    co_name: %s
    event: %s
    frame locals: %s
"""
DEFAULT_INCLUDE_FRAMES_WARNING = """\
Unexpected exception in default_include_frames: %s
    co_filename: %s
    co_name: %s
    event: %s
    frame locals: %s
"""
DEFAULT_IGNORE_FRAMES_WARNING = """\
Unexpected exception in default_ignore_frames: %s
    co_filename: %s
    co_name: %s
    event: %s
    frame locals: %s
"""
PROCESS_FRAME_WARNING = """\
Unexpected exception in KoloProfiler.process_frame
    co_filename: %s
    co_name: %s
    event: %s
    frame locals: %s
"""


class KoloProfiler:
    """
    Collect runtime information about code to view in VSCode.

    include_frames can be passed to enable profiling of standard library
    or third party code.

    ignore_frames can also be passed to disable profiling of a user's
    own code.

    The list should contain fragments of the path to the relevant files.
    For example, to include profiling for the json module the include_frames
    could look like ["/json/"].

    The list may also contain frame filters. A frame filter is a function
    (or other callable) that takes the same arguments as the profilefunc
    passed to sys.setprofile and returns a boolean representing whether
    to allow or block the frame.

    include_frames takes precedence over ignore_frames. A frame that
    matches an entry in each list will be profiled.

    Rough order of operations in profiler (ideally kolo could natively make such a list!)
    1. __call__ is the sys registered profile callback which then calls calls push_frame_data
    2. push_frame_data adds to self.frames_by_thread
    3. save_trace_in_thread
    4. KoloProfiler.save
    5. build_trace
    """

    def __init__(
        self,
        db_path: Path,
        config=None,
        one_trace_per_test=False,
        *,
        source,
        name: Optional[str] = None,
    ) -> None:
        self.db_path = db_path
        self.source = source
        self.one_trace_per_test = one_trace_per_test
        trace_id = ulid.new()
        self.trace_id = f"trc_{trace_id}"
        self.trace_name = name
        self.start_test_indices: Dict[str, int] = {}
        self.config = config if config is not None else {}
        self.include_frames = get_include_frames(config)
        self.ignore_frames = get_ignore_frames(config)

        self.default_include_frames: Dict[str, List[FrameProcessor]] = {}
        for plugin_data in load_plugin_data(self.config):
            processor = PluginProcessor(plugin_data, self.config)
            for co_name in plugin_data["co_names"]:
                self.default_include_frames.setdefault(co_name, []).append(processor)

        self.default_ignore_frames: List[FrameFilter] = [
            library_filter,
            frozen_filter,
            pypy_filter,
            kolo_filter,
            exec_filter,
            attrs_filter,
            pytest_generated_filter,
        ]
        self.thread_locals = KoloLocals()
        self.timestamp = time.time()
        self.rust_profiler = None
        self.omit_return_locals = self.config.get("omit_return_locals", False)

        # Key is the thread id, value is the native python thread object
        self.threads: Dict[str, threading.Thread] = {}

        # Key is the thread id, value is a list of frames for that thread
        self.frames_by_thread: Dict[str, List[bytes]] = defaultdict(list)

        self.current_thread_id = get_thread_id(threading.current_thread())
        if self.config.get("lightweight_repr", False):
            self.dump_msgpack = dump_msgpack_lightweight_repr
        else:
            self.dump_msgpack = dump_msgpack

    def __call__(self, frame: types.FrameType, event: str, arg: object) -> None:
        if event in ["c_call", "c_return", "c_exception"]:
            return

        co_name = frame.f_code.co_name

        frames = []
        frame_types = []

        try:
            # Execute only the filters listening for this co_name
            for processor in self.default_include_frames.get(co_name, ()):
                try:
                    if processor(frame, event, arg):
                        frame_data = processor.process(
                            frame, event, arg, self.thread_locals.call_frames
                        )
                        if frame_data:  # pragma: no branch
                            data = self.dump_msgpack(frame_data)
                            frames.append(data)
                            frame_types.append(frame_data["type"])
                except Exception as e:
                    logger.warning(
                        DEFAULT_INCLUDE_FRAMES_WARNING,
                        processor,
                        frame.f_code.co_filename,
                        frame.f_code.co_name,
                        event,
                        frame.f_locals,
                        exc_info=e,
                    )
                    continue

            for frame_filter in self.include_frames:
                try:
                    if frame_filter(frame, event, arg):
                        frames.append(self.process_frame(frame, event, arg))
                        frame_types.append("frame")
                        return
                except Exception as e:
                    logger.warning(
                        INCLUDE_FRAMES_WARNING,
                        frame_filter,
                        frame.f_code.co_filename,
                        frame.f_code.co_name,
                        event,
                        frame.f_locals,
                        exc_info=e,
                    )
                    continue

            for frame_filter in self.default_ignore_frames:
                try:
                    if frame_filter(frame, event, arg):
                        return
                except Exception as e:
                    logger.warning(
                        DEFAULT_IGNORE_FRAMES_WARNING,
                        frame_filter,
                        frame.f_code.co_filename,
                        frame.f_code.co_name,
                        event,
                        frame.f_locals,
                        exc_info=e,
                    )
                    continue

            for frame_filter in self.ignore_frames:
                try:
                    if frame_filter(frame, event, arg):
                        return
                except Exception as e:
                    logger.warning(
                        IGNORE_FRAMES_WARNING,
                        frame_filter,
                        frame.f_code.co_filename,
                        frame.f_code.co_name,
                        event,
                        frame.f_locals,
                        exc_info=e,
                    )
                    continue

            try:
                frames.append(self.process_frame(frame, event, arg))
                frame_types.append("frame")
            except Exception as e:
                logger.warning(
                    PROCESS_FRAME_WARNING,
                    frame.f_code.co_filename,
                    frame.f_code.co_name,
                    event,
                    frame.f_locals,
                    exc_info=e,
                )

        finally:
            if not frames:
                return

            if event == "return":
                frames.reverse()
                frame_types.reverse()

            if self.one_trace_per_test:  # pragma: no branch
                for index, frame_type in enumerate(frame_types):  # pragma: no cover
                    if frame_type == "start_test":
                        before, frames = frames[:index], frames[index:]

                        self.push_frame_data(before)

                        self.start_test()

                    elif frame_type == "end_test":
                        before, frames = frames[: index + 1], frames[index + 1 :]

                        self.push_frame_data(before)

                        self.end_test()

            self.push_frame_data(frames)

    def push_frame_data(self, data):
        current_thread = threading.current_thread()

        thread_id = get_thread_id(current_thread)
        if thread_id not in self.threads:
            self.threads[thread_id] = current_thread

        if thread_id not in self.frames_by_thread:
            self.frames_by_thread[thread_id] = []

        self.frames_by_thread[thread_id].extend(data)

    def start_test(self):
        self.trace_id = f"trc_{ulid.new()}"
        self.start_test_indices = {
            thread_id: len(frames)
            for thread_id, frames in self.frames_by_thread.items()
        }

    def end_test(self):
        frames_by_thread = {
            thread_id: frames[self.start_test_indices.get(thread_id, 0) :]
            for thread_id, frames in self.frames_by_thread.items()
        }
        self.save(frames_by_thread=frames_by_thread)

    def __enter__(self) -> None:
        if self.config.get("use_rust", True):
            try:
                from ._kolo import register_profiler
            except ImportError:
                # Useful for PyPY, which doesn't do rust
                sys.setprofile(self)
                threading.setprofile(self)
            else:
                register_profiler(self)
        else:
            sys.setprofile(self)
            threading.setprofile(self)

    def __exit__(self, *exc) -> None:
        sys.setprofile(None)
        threading.setprofile(None)

    def build_trace(self, frames_by_thread=None):
        # frames_by_thread is only passed when called by end_test.

        if self.rust_profiler:
            return self.rust_profiler.build_trace()

        config = {
            k: v
            for k, v in self.config.items()
            if k not in CONFIG_KEYS_TO_OMIT_FROM_SAVED_TRACE
        }
        # Config to ALWAYS include, even if the user user didn't change the default
        config["use_monitoring"] = False
        config["use_rust"] = False

        timestamp = self.timestamp
        data = {
            "command_line_args": sys.argv,
            "current_commit_sha": COMMIT_SHA,
            "current_thread_id": self.current_thread_id,
            "meta": {
                "version": __version__,
                "source": self.source,
                "environment": {
                    "py_version": platform.python_version(),
                    "py_version_full": sys.version,
                    "platform": platform.platform(),
                    "system": platform.system(),
                    "machine": platform.machine(),
                    "processor": platform.processor(),
                },
                "config": config,
            },
            "timestamp": timestamp,
            "trace_id": self.trace_id,
            "trace_name": self.trace_name,
        }

        if frames_by_thread is None:
            frames_by_thread = self.frames_by_thread

        # From kolo v2.35.0 onwards, frames_of_interest and frames are always empty
        data["frames_of_interest"] = []
        data["frames"] = {}

        data["threads"] = {}
        for thread_id, thread in self.threads.items():
            data["threads"][thread_id] = {
                "name": thread.name,
                "ident": getattr(thread, "ident", None),
                "native_id": getattr(thread, "native_id", None),
                "daemon": thread.daemon,
                "is_alive": thread.is_alive(),
            }

            if thread_id in frames_by_thread:
                data["threads"][thread_id]["frames"] = [
                    msgpack.unpackb(f, strict_map_key=False)
                    for f in frames_by_thread[thread_id]
                ]

        return self.dump_msgpack(data)

    def save(self, frames_by_thread=None) -> None:
        """
        frames_by_thread is only passed when called from end_test,
        because end_test cuts off some frames and saves directly.
        """

        if self.rust_profiler:
            self.rust_profiler.save()
            return

        if self.trace_name is None:
            self._set_trace_name(frames_by_thread)

        serialized_data = self.build_trace(frames_by_thread=frames_by_thread)
        timeout = self.config.get("sqlite_busy_timeout", 60)
        save_trace_in_sqlite(
            self.db_path, self.trace_id, msgpack=serialized_data, timeout=timeout
        )

    def _set_trace_name(self, frames_by_thread=None):
        """
        Extract test name or HTTP request/response information from frames to set the trace name.
        """
        if frames_by_thread is None:
            frames_by_thread = self.frames_by_thread

        trace_name = extract_test_trace_name(frames_by_thread, self.current_thread_id)
        if trace_name:
            self.trace_name = trace_name
            return

        trace_name = extract_http_trace_name(frames_by_thread, self.current_thread_id)
        if trace_name:
            self.trace_name = trace_name

    def process_frame(self, frame: types.FrameType, event: str, arg: object) -> bytes:
        if event == "call":
            frame_id = f"frm_{ulid.new()}"
            self.thread_locals._frame_ids[id(frame)] = frame_id
        elif event == "return":  # pragma: no branch
            frame_id = self.thread_locals._frame_ids[id(frame)]

        user_code_call_site_ = user_code_call_site(
            self.thread_locals.call_frames, frame_id
        )

        if event == "call":
            self.thread_locals.call_frames.append((frame, frame_id))
        elif event == "return":  # pragma: no branch
            self.thread_locals.call_frames.pop()

        if self.omit_return_locals and event == "return":
            frame_locals = None
        else:
            frame_locals = {
                k: v for k, v in frame.f_locals.items() if k != "__builtins__"
            }

        frame_data = {
            "path": frame_path(frame),
            "co_name": frame.f_code.co_name,
            "qualname": get_qualname(frame),
            "event": event,
            "frame_id": frame_id,
            "arg": arg,
            "locals": frame_locals,
            "timestamp": time.time(),
            "type": "frame",
            "user_code_call_site": user_code_call_site_,
        }
        return self.dump_msgpack(frame_data)


def get_qualname(frame: types.FrameType) -> str | None:
    try:
        qualname = frame.f_code.co_qualname  # type: ignore[attr-defined]
    except AttributeError:
        pass
    else:
        module = frame.f_globals.get("__name__", "<unknown>")
        return f"{module}.{qualname}"

    co_name = frame.f_code.co_name
    if co_name == "<module>":  # pragma: no cover
        module = frame.f_globals.get("__name__", "<unknown>")
        return f"{module}.<module>"

    try:
        outer_frame = frame.f_back
        assert outer_frame
        try:
            function = outer_frame.f_locals[co_name]
        except KeyError:
            try:
                self = frame.f_locals["self"]
            except KeyError:
                cls = frame.f_locals.get("cls")
                if isinstance(cls, type):
                    function = inspect.getattr_static(cls, co_name)
                else:
                    try:
                        qualname = frame.f_locals["__qualname__"]
                    except KeyError:
                        function = frame.f_globals[co_name]
                    else:  # pragma: no cover
                        module = frame.f_globals.get("__name__", "<unknown>")
                        return f"{module}.{qualname}"
            else:
                function = inspect.getattr_static(self, co_name)
                if isinstance(function, property):
                    function = function.fget

        return f"{function.__module__}.{function.__qualname__}"
    except Exception:
        return None


def save_trace_in_thread(profiler):
    if platform.machine() == "wasm32":
        profiler.save()
    else:
        name = "kolo-save_request_in_db"
        threading.Thread(target=profiler.save, name=name).start()


def upload_trace_in_thread(profiler, upload_token):
    def upload():
        trace = profiler.build_trace()
        try:
            response = upload_to_dashboard(trace, upload_token)
            response.raise_for_status()
        except httpx.HTTPError:
            logger.exception("Failed to upload trace to Kolo dashboard.")

    if platform.machine() == "wasm32":
        upload()
    else:
        name = "kolo-upload_to_dashboard"
        threading.Thread(target=upload, name=name).start()


class Enabled:
    def __init__(
        self,
        config: Mapping[str, Any] | None,
        source: str,
        one_trace_per_test: bool,
        save_in_thread: bool,
        upload_token: Optional[str],
        db_path: Optional[Path] = None,
        name: Optional[str] = None,
    ):
        if config is None:
            config = {}
        self.config = load_config(config)
        self._profiler: KoloProfiler | None = None
        self._monitor = None
        self.source = source
        self.one_trace_per_test = one_trace_per_test
        self.save_in_thread = save_in_thread
        self.upload_token = upload_token
        self.db_path = db_path
        self.name = name

    def __call__(self, func):
        @wraps(func)
        def inner(*args, **kwargs):
            with self:
                return func(*args, **kwargs)

        return inner

    def __enter__(self) -> None:
        use_monitoring = self.config.get("use_monitoring", False)

        if use_monitoring and sys.version_info >= (3, 12):
            if sys.monitoring.get_tool(sys.monitoring.PROFILER_ID):  # type: ignore[attr-defined]
                return
        elif sys.getprofile():
            return

        if sys.version_info < (3, 12) or not use_monitoring:
            try:
                thread_profiler = threading.getprofile()  # type: ignore[attr-defined]
            except AttributeError:
                thread_profiler = threading._profile_hook
            if thread_profiler:
                return

        # self.db_path is typically not set,
        # but we make use of it in tests.
        if self.db_path is None:
            db_path = setup_db()
        else:
            db_path = self.db_path

        monkeypatch_queryset_repr()

        if sys.version_info >= (3, 12) and use_monitoring:
            from .monitoring import activate_monitoring

            monitor = self.register_monitor(db_path)
            activate_monitoring(monitor)
            self._monitor = monitor
        else:
            self._profiler = KoloProfiler(
                db_path,
                config=self.config,
                source=self.source,
                one_trace_per_test=self.one_trace_per_test,
                name=self.name,
            )
            self._profiler.__enter__()

    def register_monitor(self, db_path):
        use_rust = self.config.get("use_rust", True)
        if use_rust:
            from ._kolo import register_monitor

            return register_monitor(
                str(db_path),
                config=self.config,
                source=self.source,
                one_trace_per_test=self.one_trace_per_test,
                name=self.name,
            )

        from .monitoring import KoloMonitor  # type: ignore[attr-defined]

        return KoloMonitor(
            db_path,
            config=self.config,
            source=self.source,
            one_trace_per_test=self.one_trace_per_test,
            name=self.name,
        )

    def save_trace_profiler(self):
        assert self._profiler is not None

        if self.one_trace_per_test:
            return

        if not self.save_in_thread:
            self._profiler.save()
            return

        if self.upload_token:
            upload_trace_in_thread(self._profiler, self.upload_token)
        else:
            save_trace_in_thread(self._profiler)

    def save_trace_monitor(self):
        assert self._monitor is not None

        if self.one_trace_per_test:
            return

        if not self.save_in_thread:
            self._monitor.save()
            return

        if self.upload_token:
            upload_trace_in_thread(self._monitor, self.upload_token)
        else:
            save_trace_in_thread(self._monitor)

    def __exit__(self, *exc) -> None:
        if self._profiler is not None:
            self._profiler.__exit__(*exc)
            self.save_trace_profiler()
            self._profiler = None

        if self._monitor is not None:
            from .monitoring import disable_monitoring  # type: ignore[attr-defined]

            disable_monitoring(self._monitor)
            self.save_trace_monitor()
            self._monitor = None


F = TypeVar("F", bound=Callable[..., Any])


class CallableContextManager(Protocol):
    def __call__(self, func: F) -> F: ...  # pragma: no cover

    def __enter__(self) -> None: ...  # pragma: no cover

    def __exit__(self, *exc) -> None: ...  # pragma: no cover


@overload
def enable(_func: F) -> F:
    """Stub"""


@overload
def enable(
    config: Mapping[str, Any] | None = None,
    name: Optional[str] = None,
    source: str = "kolo.enable",
    _one_trace_per_test: bool = False,
    _save_in_thread: bool = False,
    _upload_token: Optional[str] = None,
    _db_path: Optional[Path] = None,
) -> CallableContextManager:
    """Stub"""


def enable(
    config=None,
    *,
    name=None,
    source="kolo.enable",
    _one_trace_per_test=False,
    _save_in_thread=False,
    _upload_token=None,
    _db_path=None,
):
    if config is None or isinstance(config, Mapping):
        function = None
    else:
        # Treat as a decorator called on a function
        function = config
        config = None

    enabled = Enabled(
        config=config,
        source=source,
        name=name,
        one_trace_per_test=_one_trace_per_test,
        save_in_thread=_save_in_thread,
        upload_token=_upload_token,
        db_path=_db_path,
    )

    if function is None:
        return enabled
    return enabled(function)


enabled = enable
