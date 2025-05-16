from __future__ import annotations

import types

import ulid


def pytest_generated_filter(frame: types.FrameType, event: str, arg: object) -> bool:
    """
    Ignore pytest generated code

    When using the `-k` or `-m` command line argument, pytest compiles
    code with a custom filename:

        <pytest match expression>

    https://github.com/pytest-dev/pytest/blob/9454fc38d3636b79ee657d6cacf7477eb8acee52/src/_pytest/mark/expression.py#L208

    Since this is library code, we want to filter it out.
    """
    return frame.f_code.co_filename == "<pytest match expression>"


def build_context(config):
    return {"frame_ids": {}}


def process_pytest(frame, event, arg, context):  # pragma: no cover
    frame_ids = context["frame_ids"]
    co_name = frame.f_code.co_name
    # location is a (filename, lineno, testname) tuple
    # https://docs.pytest.org/en/7.1.x/reference/reference.html#pytest.hookspec.pytest_runtest_logstart
    location = frame.f_locals["location"]
    if co_name == "pytest_runtest_logstart":
        frame_id = f"frm_{ulid.new()}"
        frame_ids[id(location)] = frame_id
    else:
        frame_id = frame_ids[id(location)]

    _filename, _lineno, test = location
    test_class, _sep, test_name = test.rpartition(".")
    return {
        "frame_id": frame_id,
        "test_name": test_name,
        "test_class": test_class if test_class else None,
    }


def call_pytest(frame, event, arg, context):
    return (  # pragma: no cover
        event == "call" and frame.f_code.co_name == "pytest_runtest_logstart"
    ) or (event == "return" and frame.f_code.co_name == "pytest_runtest_logfinish")


pytest = {
    "co_names": ("pytest_runtest_logstart", "pytest_runtest_logfinish"),
    "path_fragment": "kolo/pytest_plugin.py",
    "call": call_pytest,
    "call_type": "start_test",
    "return_type": "end_test",
    "process": process_pytest,
    "build_context": build_context,
}
