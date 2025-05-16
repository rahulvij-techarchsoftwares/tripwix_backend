from __future__ import annotations


def process_huey(frame, event, arg, context):
    frame_locals = frame.f_locals
    task_object = frame_locals["self"]
    task_args, task_kwargs = task_object.data

    return {
        "name": f"{task_object.__module__}.{task_object.name}",
        "args": task_args,
        "kwargs": task_kwargs,
    }


def call_huey(frame, event, arg, context):
    # Doing the import once and binding is substantially faster than going
    # through the import system every time.
    # See:
    # https://github.com/django/asgiref/issues/269
    # https://github.com/django/asgiref/pull/288
    # A more battle-tested (slightly slower/more complex) alternative would be:
    # https://github.com/django/django/pull/14850
    # https://github.com/django/django/pull/14858
    # https://github.com/django/django/pull/14931
    if "class" not in context:
        from huey.api import Task

        context["class"] = Task
    return isinstance(frame.f_locals["self"], context["class"])


huey = {
    "co_names": ("execute",),
    "path_fragment": "/huey/api.py",
    "call": call_huey,
    "call_type": "background_job",
    "return_type": "background_job_end",
    "subtype": "huey",
    "process": process_huey,
}
