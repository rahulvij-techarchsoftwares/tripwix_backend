from __future__ import annotations

import ulid


def call_unittest(frame, event, arg, context):
    return (  # pragma: no cover
        event == "call" and frame.f_code.co_name == "startTest"
    ) or (event == "return" and frame.f_code.co_name == "stopTest")


def process_unittest(frame, event, arg, context):  # pragma: no cover
    frame_ids = context["frame_ids"]
    testcase = frame.f_locals["test"]
    co_name = frame.f_code.co_name
    if co_name == "startTest":
        frame_id = f"frm_{ulid.new()}"
        frame_ids[id(testcase)] = frame_id
    else:
        frame_id = frame_ids[id(testcase)]
    return {
        "frame_id": frame_id,
        "test_name": testcase._testMethodName,
        "test_class": testcase.__class__.__qualname__,
    }


def build_context(config):
    return {"frame_ids": {}}


unittest = {
    "co_names": ("startTest", "stopTest"),
    "path_fragment": "unittest/result.py",
    "call": call_unittest,
    "call_type": "start_test",
    "return_type": "end_test",
    "process": process_unittest,
    "build_context": build_context,
}
