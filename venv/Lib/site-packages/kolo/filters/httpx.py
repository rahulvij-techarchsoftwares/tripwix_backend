import types

import ulid


def build_context(config):
    return {
        "frame_ids": {},
        "request_ids": set(),
    }


def process_httpx(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    request_ids = context["request_ids"]
    frame_ids = context["frame_ids"]

    frame_locals = frame.f_locals
    # Track `request_id` to strip out unwanted resume frames in the async case.
    # Unfortunately `request_id` isn't guaranteed to be unique if the user chooses
    # to re-use a `request` instance, but I haven't thought of a way to do better.
    # We can't use `self` (`Client` or `AsyncClient` because that's even more likely
    # to be re-used.
    request_id = id(frame_locals["request"])
    request = frame_locals["request"]
    method = request.method
    url = str(request.url)

    if event in ("call", "resume"):
        if request_id in request_ids:
            frame_id = frame_ids[id(frame)]
        else:
            request_ids.add(request_id)
            frame_id = f"frm_{ulid.new()}"
            frame_ids[id(frame)] = frame_id
        return {
            "body": None,
            "frame_id": frame_id,
            "headers": dict(request.headers),
            "method": method,
            "method_and_full_url": f"{method} {url}",
            "url": url,
        }

    from httpx._models import Response

    if isinstance(arg, Response):
        request_ids.discard(request_id)

        from httpx._exceptions import ResponseNotRead

        try:
            body = arg.text
        except ResponseNotRead:  # pragma: no cover
            body = None
        headers = dict(arg.headers)
        status_code = arg.status_code
    else:
        # If we don't have a `Response`, we're suspending the coroutine
        # or there was an exception

        body = None
        headers = None
        status_code = None

    return {
        "body": body,
        "frame_id": frame_ids[id(frame)],
        "headers": headers,
        "method": method,
        "method_and_full_url": f"{method} {url}",
        "status_code": status_code,
        "url": url,
    }


httpx = {
    "co_names": ("send",),
    "path_fragment": "httpx/_client.py",
    "call_type": "outbound_http_request",
    "return_type": "outbound_http_response",
    "subtype": "httpx",
    "process": process_httpx,
    "build_context": build_context,
}
