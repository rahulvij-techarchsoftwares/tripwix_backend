from __future__ import annotations

import types


def call_celery(frame, event, arg, context):
    return "sentry_sdk" not in frame.f_code.co_filename


def process_celery(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    frame_locals = frame.f_locals
    task_name = frame_locals["self"].name
    task_args = frame_locals["args"]
    task_kwargs = frame_locals["kwargs"]
    return {
        "name": task_name,
        "args": task_args,
        "kwargs": task_kwargs,
    }


celery = {
    "co_names": ("apply_async",),
    "path_fragment": "celery/app/task.py",
    "call": call_celery,
    "call_type": "background_job",
    "return_type": "background_job_end",
    "subtype": "celery",
    "process": process_celery,
}
