from __future__ import annotations

import types
from typing import TYPE_CHECKING

from ..serialize import decode_body


def process_requests(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    request = frame.f_locals["request"]
    method_and_url = f"{request.method} {request.url}"

    if event == "call":
        return {
            "body": decode_body(request.body, request.headers),
            "headers": dict(request.headers),
            "method": request.method,
            "method_and_full_url": method_and_url,
            "url": request.url,
        }

    assert event == "return"

    response = arg
    if TYPE_CHECKING:
        from requests.models import Response

        assert isinstance(response, Response)

    if response is None:
        body = None
        headers = None
        status_code = None
    else:
        body = response.text
        headers = dict(response.headers)
        status_code = response.status_code

    return {
        "body": body,
        "headers": headers,
        "method": request.method,
        "method_and_full_url": method_and_url,
        "status_code": status_code,
        "url": request.url,
    }


requests_plugin = {
    "co_names": ("send",),
    "path_fragment": "requests/sessions",
    "call_type": "outbound_http_request",
    "return_type": "outbound_http_response",
    "subtype": "requests",
    "process": process_requests,
}
