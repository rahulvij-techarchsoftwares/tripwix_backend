import dis
import functools
import logging
import operator
import os
import platform
import sys
import threading
import time
from collections import defaultdict
from typing import Optional

import httpx
import msgpack
import ulid

from .config import CONFIG_KEYS_TO_OMIT_FROM_SAVED_TRACE
from .db import save_trace_in_sqlite
from .filters.core import LibraryPathFilter
from .filters.kolo import kolo_filter_filename
from .git import COMMIT_SHA
from .plugins import PluginProcessor, load_plugin_data
from .serialize import dump_msgpack, dump_msgpack_lightweight_repr, user_code_call_site
from .threads import get_thread_id
from .upload import upload_to_dashboard
from .utils import extract_http_trace_name, extract_test_trace_name
from .version import __version__

logger = logging.getLogger("kolo")


def frozen_filter(filename):
    return "<frozen " in filename


def pypy_filter(filename):
    return "<builtin>/" in filename


def exec_filter(filename):
    return filename == "<string>"


def attrs_filter(filename):
    if filename:
        return filename.startswith("<attrs generated")
    else:  # pragma: no cover
        # Index of the frame in the Python stack:
        # 0: This function
        # 1: KoloMonitor.ignore method
        # 2: KoloMonitor.monitor_ method
        # 3: Attrs code with empty filename
        # 4: Attrs code that may match attr/_make.py
        # 5: Attrs code that may match attr/_make.py
        frame = sys._getframe(4)
        if frame is not None and frame.f_code.co_filename == "":
            frame = sys._getframe(5)
        return frame is not None and frame.f_code.co_filename.endswith(
            os.path.normpath("attr/_make.py")
        )


def pytest_filter(filename):
    return filename == "<pytest match expression>"


def build_frame_data(
    event, name, filename, frame, frame_id, call_site, omit_return_locals=False
):
    if omit_return_locals:
        frame_locals = None
    else:
        frame_locals = {k: v for k, v in frame.f_locals.items() if k != "__builtins__"}
    return {
        "path": frame_path(filename, frame.f_lineno),
        "co_name": name,
        "qualname": get_qualname(frame),
        "event": event,
        "frame_id": frame_id,
        "locals": frame_locals,
        "timestamp": time.time(),
        "type": "frame",
        "user_code_call_site": call_site,
    }


def frame_path(path, lineno):
    try:
        relative_path = os.path.relpath(path)
    except ValueError:
        relative_path = path
    return f"{relative_path}:{lineno}"


def get_qualname(frame):
    qualname = frame.f_code.co_qualname
    module = frame.f_globals.get("__name__", "<unknown>")
    return f"{module}.{qualname}"


class KoloLocals(threading.local):
    def __init__(self):
        self.call_frames = []
        self._frame_ids = {}
        self.line_frame = None
        self.line_frame_data = None
        self.variable = None
        self.opname = None


def get_instruction(code, offset):  # pragma: no cover
    for instruction in dis.get_instructions(code):
        if instruction.offset == offset:
            return instruction
    return None


if sys.version_info >= (3, 12):
    PY_START = sys.monitoring.events.PY_START
    PY_RETURN = sys.monitoring.events.PY_RETURN
    PY_UNWIND = sys.monitoring.events.PY_UNWIND
    PY_RESUME = sys.monitoring.events.PY_RESUME
    PY_YIELD = sys.monitoring.events.PY_YIELD
    PY_THROW = sys.monitoring.events.PY_THROW
    INSTRUCTION = sys.monitoring.events.INSTRUCTION
    NO_EVENTS = sys.monitoring.events.NO_EVENTS

    class KoloMonitor:
        def __init__(
            self,
            db_path,
            *,
            config=None,
            one_trace_per_test=False,
            source,
            name: Optional[str] = None,
        ):
            self.tool_id = sys.monitoring.PROFILER_ID
            self.active = False
            self.timestamp = None
            self.db_path = db_path
            self.config = config if config is not None else {}
            self.source = source
            self.one_trace_per_test = one_trace_per_test
            self.omit_return_locals = self.config.get("omit_return_locals", False)
            self.trace_id = f"trc_{ulid.new()}"
            self.trace_name = name

            filters = self.config.get("filters", {})
            self.include_frames = [
                os.path.normpath(f) for f in filters.get("include_frames", [])
            ]
            self.ignore_frames = [
                os.path.normpath(f) for f in filters.get("ignore_frames", [])
            ]

            self.default_include_frames = {}
            for plugin_data in load_plugin_data(self.config):
                processor = PluginProcessor(plugin_data, self.config)
                for co_name in plugin_data["co_names"]:
                    self.default_include_frames.setdefault(co_name, []).append(
                        processor
                    )

            self.default_ignore_frames = [
                LibraryPathFilter().filter,
                frozen_filter,
                pypy_filter,
                kolo_filter_filename,
                exec_filter,
                attrs_filter,
                pytest_filter,
            ]
            self.thread_locals = KoloLocals()
            self.line_events = self.config.get("line_events", False)

            # Key is the thread id, value is the native python thread object
            self.threads = {}

            # Key is the thread id, value is a list of frames for that thread
            self.frames_by_thread = defaultdict(list)

            self.current_thread_id = get_thread_id(threading.current_thread())
            if self.config.get("lightweight_repr", False):
                self.dump_msgpack = dump_msgpack_lightweight_repr
            else:
                self.dump_msgpack = dump_msgpack

        def ignore(self, filename):
            for ignore in self.default_ignore_frames:
                if ignore(filename):
                    return True
            return False

        def include(self, processor, event, filename, name, arg):
            try:
                if not processor.matches(filename, name):
                    return None

                # Index of the frame in the Python stack:
                # 0: This method
                # 1: KoloMonitor.monitor_ method
                # 2: The frame we want
                frame = sys._getframe(2)
                if processor.call_extra is not None and not processor.call_extra(
                    frame, event, arg, processor.context
                ):
                    return None

                return processor.process(
                    frame, event, arg, self.thread_locals.call_frames
                )
            except Exception as e:
                logger.warning(
                    "Unexpected exception in default_include_frames: %s",
                    processor,
                    exc_info=e,
                )
                return None

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

        def monitor_pystart(self, code, instruction_offset):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "call", filename, name, None
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frames.append(self.process_pystart(filename, name))
                        frame_types.append("frame")
                        return

                if self.ignore(filename):
                    if frames:
                        return  # Don't disable if a default processor matched
                    return sys.monitoring.DISABLE

                for path in self.ignore_frames:
                    if path in filename:
                        if frames:
                            return  # Don't disable if a default processor matched
                        return sys.monitoring.DISABLE

                frames.append(self.process_pystart(filename, name))
                frame_types.append("frame")
            finally:
                self.push_frames_call(frames, frame_types)

        def monitor_pyreturn(
            self, code, instruction_offset, retval
        ):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "return", filename, name, retval
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frames.append(self.process_pyreturn(filename, name, retval))
                        frame_types.append("frame")
                        return

                if self.ignore(filename):
                    if frames:
                        return  # Don't disable if a default processor matched
                    return sys.monitoring.DISABLE

                for path in self.ignore_frames:
                    if path in filename:
                        if frames:
                            return  # Don't disable if a default processor matched
                        return sys.monitoring.DISABLE

                frames.append(self.process_pyreturn(filename, name, retval))
                frame_types.append("frame")
            finally:
                self.push_frames_return(frames, frame_types)

        def monitor_pyunwind(
            self, code, instruction_offset, exception
        ):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "unwind", filename, name, exception
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frames.append(self.process_pyunwind(filename, name, exception))
                        frame_types.append("frame")
                        return

                if self.ignore(filename):
                    # We would like to return `sys.monitoring.DISABLE` here, but
                    # `PY_UNWIND` events cannot be disabled, so we do the next best
                    # thing and return asap.
                    return

                for path in self.ignore_frames:
                    if path in filename:
                        # We would like to return `sys.monitoring.DISABLE` here, but
                        # `PY_UNWIND` events cannot be disabled, so we do the next best
                        # thing and return asap.
                        return

                frames.append(self.process_pyunwind(filename, name, exception))
                frame_types.append("frame")
            finally:
                self.push_frames_return(frames, frame_types)

        def monitor_pyresume(self, code, instruction_offset):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "resume", filename, name, None
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frames.append(self.process_pyresume(filename, name))
                        frame_types.append("frame")
                        return

                if self.ignore(filename):
                    if frames:
                        return  # Don't disable if a default processor matched
                    return sys.monitoring.DISABLE

                for path in self.ignore_frames:
                    if path in filename:
                        if frames:
                            return  # Don't disable if a default processor matched
                        return sys.monitoring.DISABLE

                frames.append(self.process_pyresume(filename, name))
                frame_types.append("frame")
            finally:
                self.push_frames_call(frames, frame_types)

        def monitor_pyyield(self, code, instruction_offset, retval):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "yield", filename, name, retval
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frame_data = self.process_pyyield(filename, name, retval)
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append("frame")
                            return

                if self.ignore(filename):
                    if frames:
                        return  # Don't disable if a default processor matched
                    return sys.monitoring.DISABLE

                for path in self.ignore_frames:
                    if path in filename:
                        if frames:
                            return  # Don't disable if a default processor matched
                        return sys.monitoring.DISABLE

                frame_data = self.process_pyyield(filename, name, retval)
                if frame_data is not None:
                    frames.append(frame_data)
                    frame_types.append("frame")
            finally:
                self.push_frames_return(frames, frame_types)

        def monitor_pythrow(
            self, code, instruction_offset, exception
        ):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            filename = code.co_filename
            name = code.co_name

            frames = []
            frame_types = []

            try:
                if name in self.default_include_frames:
                    processors = self.default_include_frames[name]
                    for processor in processors:
                        frame_data = self.include(
                            processor, "throw", filename, name, exception
                        )
                        if frame_data is not None:
                            frames.append(frame_data)
                            frame_types.append(frame_data["type"])

                for path in self.include_frames:
                    if path in filename:
                        frames.append(self.process_pythrow(filename, name, exception))
                        frame_types.append("frame")
                        return

                if self.ignore(filename):
                    # We would like to return `sys.monitoring.DISABLE` here, but
                    # `PY_UNWIND` events cannot be disabled, so we do the next best
                    # thing and return asap.
                    return

                for path in self.ignore_frames:
                    if path in filename:
                        # We would like to return `sys.monitoring.DISABLE` here, but
                        # `PY_UNWIND` events cannot be disabled, so we do the next best
                        # thing and return asap.
                        return

                frames.append(self.process_pythrow(filename, name, exception))
                frame_types.append("frame")
            finally:
                self.push_frames_call(frames, frame_types)

        def monitor_instruction(self, code, instruction_offset):  # pragma: no cover
            if self.thread_locals.opname is not None:
                self.process_assignment()

            instruction = get_instruction(code, instruction_offset)

            if instruction is None or instruction.opname not in (
                "STORE_FAST",
                "STORE_GLOBAL",
                "STORE_DEREF",
            ):
                return sys.monitoring.DISABLE

            # pytest assert internals
            argval = instruction.argval
            if argval is not None and instruction.argval.startswith("@"):
                return sys.monitoring.DISABLE

            filename = code.co_filename
            name = code.co_name

            for path in self.include_frames:
                if path in filename:
                    self.process_instruction(filename, name, instruction)
                    return

            if self.ignore(filename):
                return sys.monitoring.DISABLE

            for path in self.ignore_frames:
                if path in filename:
                    return sys.monitoring.DISABLE

            self.process_instruction(filename, name, instruction)

        def process_pystart(self, filename, name):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pystart method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = f"frm_{ulid.new()}"
            self.thread_locals._frame_ids[id(frame)] = frame_id

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.append((frame, frame_id))

            data = build_frame_data(
                "call",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
            )
            data["arg"] = None
            return data

        def process_pyreturn(self, filename, name, retval):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pyreturn method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = self.thread_locals._frame_ids[id(frame)]

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.pop()

            data = build_frame_data(
                "return",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
                self.omit_return_locals,
            )
            data["arg"] = retval
            return data

        def process_pyunwind(self, filename, name, exception):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pyunwind method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = self.thread_locals._frame_ids[id(frame)]

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.pop()

            data = build_frame_data(
                "unwind",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
            )
            data["exception"] = exception
            return data

        def process_pyresume(self, filename, name):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pyresume method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = f"frm_{ulid.new()}"
            self.thread_locals._frame_ids[id(frame)] = frame_id

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.append((frame, frame_id))

            data = build_frame_data(
                "resume",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
            )
            data["arg"] = None
            return data

        def process_pyyield(self, filename, name, retval):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pyyield method
            # 2: The frame we want
            frame = sys._getframe(2)
            try:
                frame_id = self.thread_locals._frame_ids[id(frame)]
            except KeyError:
                # We enabled Kolo in a generator or async function, so missed the start/resume frame
                return

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.pop()

            data = build_frame_data(
                "yield",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
                self.omit_return_locals,
            )
            data["arg"] = retval
            return data

        def process_pythrow(self, filename, name, exception):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_pythrow method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = f"frm_{ulid.new()}"
            self.thread_locals._frame_ids[id(frame)] = frame_id

            user_code_call_site_ = user_code_call_site(
                self.thread_locals.call_frames, frame_id
            )

            self.thread_locals.call_frames.append((frame, frame_id))

            data = build_frame_data(
                "throw",
                name,
                filename,
                frame,
                frame_id,
                user_code_call_site_,
            )
            data["exception"] = exception
            return data

        def process_instruction(self, filename, name, instruction):  # pragma: no cover
            # Index of the frame in the Python stack:
            # 0: This function
            # 1: KoloMonitor.monitor_instruction method
            # 2: The frame we want
            frame = sys._getframe(2)
            frame_id = self.thread_locals._frame_ids.get(id(frame))

            self.thread_locals.variable = instruction.argval
            self.thread_locals.opname = instruction.opname
            self.thread_locals.line_frame = frame
            self.thread_locals.line_frame_data = {
                "path": frame_path(filename, frame.f_lineno),
                "co_name": name,
                "qualname": get_qualname(frame),
                "event": "line",
                "frame_id": frame_id,
                "timestamp": time.time(),
                "type": "frame",
            }

        def process_assignment(self):  # pragma: no cover
            frame = self.thread_locals.line_frame
            variable = self.thread_locals.variable
            opname = self.thread_locals.opname
            frame_data = self.thread_locals.line_frame_data

            if opname == "STORE_FAST":
                frame_data["assign"] = (variable, frame.f_locals[variable])
            elif opname == "STORE_GLOBAL":
                frame_data["assign"] = (variable, frame.f_globals[variable])
            elif opname == "STORE_DEREF":  # nonlocal
                frame_data["assign"] = (variable, frame.f_locals[variable])

            self.push_frame_data(frame_data)

            self.thread_locals.line_frame = None
            self.thread_locals.variable = None
            self.thread_locals.opname = None
            self.thread_locals.line_frame_data = None

        def push_frame_data(self, data):
            data = self.dump_msgpack(data)

            current_thread = threading.current_thread()
            thread_id = get_thread_id(current_thread)
            if thread_id not in self.threads:
                self.threads[thread_id] = current_thread

            self.frames_by_thread[thread_id].append(data)

        def push_frames_call(self, frames, frame_types):
            if not frames:
                pass
            elif frame_types == ["frame"]:
                self.push_frame_data(frames[0])
            else:
                if self.one_trace_per_test:
                    for index, frame_type in enumerate(frame_types):
                        if frame_type == "start_test":
                            before, frames = frames[:index], frames[index:]
                            for frame_data in before:
                                self.push_frame_data(frame_data)

                            self.start_test()

                for frame_data in frames:
                    self.push_frame_data(frame_data)

        def push_frames_return(self, frames, frame_types):
            if not frames:
                pass
            elif frame_types == ["frame"]:
                self.push_frame_data(frames[0])
            else:
                frames.reverse()
                frame_types.reverse()

                if self.one_trace_per_test:
                    for index, frame_type in enumerate(frame_types):
                        if frame_type == "end_test":
                            before, frames = frames[: index + 1], frames[index + 1 :]
                            for frame_data in before:
                                self.push_frame_data(frame_data)

                            self.end_test()

                for frame_data in frames:
                    self.push_frame_data(frame_data)

        def build_trace(self, frames_by_thread=None):
            # frames_by_thread is only passed when called by end_test.

            config = {
                k: v
                for k, v in self.config.items()
                if k not in CONFIG_KEYS_TO_OMIT_FROM_SAVED_TRACE
            }
            # Config to ALWAYS include, even if the user user didn't change the default
            config["use_monitoring"] = True
            config["use_rust"] = False

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
                "timestamp": self.timestamp,
                "trace_id": self.trace_id,
                "trace_name": self.trace_name,
            }

            if frames_by_thread is None:
                frames_by_thread = self.frames_by_thread

            # frames_of_interest and frames are always empty
            # for sys.monitoring traces now.
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

            # TODO: And then let's also capture threads with threading.enumerate()
            # just for some fun extra data...
            return self.dump_msgpack(data)

        def save(self, frames_by_thread=None):
            """
            frames_by_thread is only passed when called from end_test,
            because end_test cuts off some frames and saves directly.
            """

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

            trace_name = extract_test_trace_name(
                frames_by_thread, self.current_thread_id
            )
            if trace_name:
                self.trace_name = trace_name
                return

            trace_name = extract_http_trace_name(
                frames_by_thread, self.current_thread_id
            )
            if trace_name:
                self.trace_name = trace_name

    def activate_monitoring(monitor):
        monitor.active = True
        tool_id = monitor.tool_id
        sys.monitoring.use_tool_id(tool_id, "kolo")
        all_events = PY_START | PY_RETURN | PY_UNWIND | PY_RESUME | PY_YIELD | PY_THROW

        sys.monitoring.register_callback(tool_id, PY_START, monitor.monitor_pystart)
        sys.monitoring.register_callback(tool_id, PY_RETURN, monitor.monitor_pyreturn)
        sys.monitoring.register_callback(tool_id, PY_UNWIND, monitor.monitor_pyunwind)
        sys.monitoring.register_callback(tool_id, PY_RESUME, monitor.monitor_pyresume)
        sys.monitoring.register_callback(tool_id, PY_YIELD, monitor.monitor_pyyield)
        sys.monitoring.register_callback(tool_id, PY_THROW, monitor.monitor_pythrow)

        if monitor.line_events:
            all_events |= INSTRUCTION
            sys.monitoring.register_callback(
                tool_id, INSTRUCTION, monitor.monitor_instruction
            )

        sys.monitoring.set_events(tool_id, all_events)

        monitor.timestamp = time.time()

    def disable_monitoring(monitor):
        if monitor.active:
            monitor.active = False
            sys.monitoring.set_events(monitor.tool_id, NO_EVENTS)
            sys.monitoring.register_callback(monitor.tool_id, PY_START, None)
            sys.monitoring.register_callback(monitor.tool_id, PY_RETURN, None)
            sys.monitoring.register_callback(monitor.tool_id, PY_UNWIND, None)
            sys.monitoring.register_callback(monitor.tool_id, PY_RESUME, None)
            sys.monitoring.register_callback(monitor.tool_id, PY_YIELD, None)
            sys.monitoring.register_callback(monitor.tool_id, PY_THROW, None)
            if monitor.line_events:
                sys.monitoring.register_callback(monitor.tool_id, INSTRUCTION, None)
            sys.monitoring.free_tool_id(monitor.tool_id)
            sys.monitoring.restart_events()
