import importlib
import os
import sys
import time
from typing import Optional

import ulid

from .serialize import user_code_call_site

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points


def load(processor):
    mod, sep, name = processor.partition(":")
    processor = importlib.import_module(mod)
    if sep:  # pragma: no branch
        for attr in name.split("."):
            processor = getattr(processor, attr)

    return processor


def load_plugin_data(config):
    kolo_plugins = entry_points(group="kolo.processors")
    processors = [plugin.load() for plugin in kolo_plugins]
    local_procesors = config.get("processors", [])
    processors.extend([load(processor) for processor in local_procesors])
    return processors


class PluginProcessor:
    def __init__(self, plugin_data, config):
        self.plugin_data = plugin_data
        self.config = config

        self.co_names = plugin_data["co_names"]
        self.filename = os.path.normpath(plugin_data["path_fragment"])
        self.call_type = plugin_data["call_type"]
        self.return_type = plugin_data["return_type"]
        self.unwind_type = plugin_data.get("unwind_type", self.return_type)
        self.resume_type = plugin_data.get("resume_type", self.call_type)
        self.yield_type = plugin_data.get("yield_type", self.return_type)
        self.throw_type = plugin_data.get("throw_type", self.unwind_type)
        self.subtype = plugin_data.get("subtype")
        self.call_extra = plugin_data.get("call")
        self.process_extra = plugin_data.get("process")
        self.events = plugin_data.get("events")
        build_context = plugin_data.get("build_context")
        if build_context is None:
            self.context = {}
        else:
            self.context = build_context(config)

        self.frame_ids = {}

    def __call__(self, frame, event, arg):
        filename = frame.f_code.co_filename
        co_name = frame.f_code.co_name

        if self.call_extra is None:
            return co_name in self.co_names and self.filename in filename
        return (
            co_name in self.co_names
            and self.filename in filename
            and self.call_extra(frame, event, arg, self.context)
        )

    def matches(self, filename, name):
        return name in self.co_names and self.filename in filename

    def frame_id(self, frame, event):
        frame_id: Optional[str]
        if event == "call":
            frame_id = f"frm_{ulid.new()}"
            self.frame_ids[id(frame)] = frame_id
        elif event == "return":
            frame_id = self.frame_ids.get(id(frame))
            if frame_id is None:
                frame_id = f"frm_{ulid.new()}"
        else:
            frame_id = None  # pragma: no cover
        return frame_id

    def process(self, frame, event, arg, call_frames):
        if self.events is not None and event not in self.events:
            return None

        timestamp = time.time()
        frame_id = self.frame_id(frame, event)
        data = {
            "frame_id": frame_id,
            "timestamp": timestamp,
            "user_code_call_site": user_code_call_site(call_frames, frame_id),
        }

        if event == "call":
            data["type"] = self.call_type
        elif event == "return":
            data["type"] = self.return_type
        elif event == "unwind":
            data["type"] = self.unwind_type
        elif event == "resume":
            data["type"] = self.resume_type
        elif event == "yield":
            data["type"] = self.yield_type
        elif event == "throw":  # pragma: no branch
            data["type"] = self.throw_type

        if self.subtype is not None:
            data["subtype"] = self.subtype

        if self.process_extra is not None:
            data.update(self.process_extra(frame, event, arg, self.context))
        return data

    def __repr__(self):
        return f"PluginProcessor({self.plugin_data})"
