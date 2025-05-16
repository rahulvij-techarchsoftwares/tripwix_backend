from __future__ import annotations

import time
import types
from contextlib import suppress

from ..serialize import get_content, get_request_body


def process_django(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    if event in ("call", "resume", "throw"):
        context["timestamp"] = time.time()
        request = frame.f_locals["request"]
        return {
            "body": get_request_body(request),
            "headers": dict(request.headers),
            "method": request.method,
            "path_info": request.path_info,
            # dict(request.POST) can give confusing results due to MultivalueDict
            "post_data": dict(request.POST),
            "query_params": dict(request.GET),
            "scheme": request.scheme,
            # Override the timestamp in PluginProcessor because consistency with
            # ms_duration is more important.
            "timestamp": context["timestamp"],
        }
    elif event in ("return", "yield", "unwind"):  # pragma: no branch
        timestamp = time.time()
        duration = timestamp - context["timestamp"]
        ms_duration = round(duration * 1000, 2)

        request = frame.f_locals["request"]
        match = request.resolver_match
        if match:  # match is None if this is a 404
            # TODO(later): We should record the urlconf used, if it's not ROOT_URLCONF
            # TODO(later): We should report on whether it was a `path` or `re_path` if we can;
            #  we might have to look in `tried` or go up a frame to find the pattern object?
            try:
                route_params = {
                    "captured": match.captured_kwargs,
                    "defaults": match.extra_kwargs,
                }
            except AttributeError:
                # Prior to Django 4.1, the match never holds a reference to the "default" arguments
                # etc; see the PR & corresponding ticket:
                # https://github.com/django/django/pull/15402
                # https://code.djangoproject.com/ticket/16406
                route_params = {
                    "captured": {},
                    "defaults": {},
                }
            url_pattern = {
                "namespace": match.namespace,
                "route": match.route,
                "route_params": route_params,
                "url_name": match.url_name,
                "view_qualname": match._func_path,
                "view_params": {"positional": match.args, "keyword": match.kwargs},
            }
        else:
            url_pattern = None

        if "response" not in frame.f_locals:
            return {
                "ms_duration": ms_duration,
                "status_code": None,
                "content": "",
                "headers": {},
                "url_pattern": url_pattern,
                # Override the timestamp in PluginProcessor because consistency with
                # ms_duration is more important.
                "timestamp": timestamp,
            }
        response = frame.f_locals["response"]
        return {
            "ms_duration": ms_duration,
            "status_code": response.status_code,
            "content": get_content(response),
            "headers": dict(response.items()),
            "url_pattern": url_pattern,
            # Override the timestamp in PluginProcessor because consistency with
            # ms_duration is more important.
            "timestamp": timestamp,
        }


def flatten(context):
    from django.template.context import BaseContext

    flat = {}
    for c in context.dicts:
        if isinstance(c, BaseContext):
            c = flatten(c)
        flat.update(c)
    return flat


def process_django_template(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    template_context = frame.f_locals["context"]
    with suppress(AttributeError):
        try:
            template_context = template_context.flatten()
        except ValueError:  # pragma: no cover
            # https://code.djangoproject.com/ticket/35417
            template_context = flatten(template_context)

    template_name = frame.f_locals["self"].name
    if isinstance(template_name, str):
        # `name` can be a Django `SafeString`. In this case, it would get
        # serialized as the `repr`, rather than the raw string we care about.
        # Appending "" converts back to a normal python `str`.
        template_name += ""

    return {
        "context": template_context,
        "template": template_name,
    }


django = {
    "co_names": ("get_response",),
    "path_fragment": "/kolo/middleware.py",
    "call_type": "django_request",
    "return_type": "django_response",
    "process": process_django,
}

django_async = {
    "co_names": ("aget_response",),
    "path_fragment": "/kolo/middleware.py",
    "call_type": "django_request",
    "return_type": "django_response",
    "process": process_django,
}

django_template = {
    "co_names": ("_render",),
    "path_fragment": "django/template/base.py",
    "call_type": "django_template_start",
    "return_type": "django_template_end",
    "process": process_django_template,
}

django_template_instrumented_test = {
    "co_names": ("instrumented_test_render",),
    "path_fragment": "django/test/utils.py",
    "call_type": "django_template_start",
    "return_type": "django_template_end",
    "process": process_django_template,
}

django_setup = {
    "co_names": ("setup",),
    "path_fragment": "django/__init__.py",
    "call_type": "django_setup_start",
    "return_type": "django_setup_end",
    "process": None,
}

django_checks = {
    "co_names": ("run_checks",),
    "path_fragment": "django/core/checks/registry.py",
    "call_type": "django_checks_start",
    "return_type": "django_checks_end",
    "process": None,
}

django_test_db = {
    "co_names": ("create_test_db",),
    "path_fragment": "django/db/backends/base/creation.py",
    "call_type": "django_create_test_db_start",
    "return_type": "django_create_test_db_end",
    "process": None,
}
