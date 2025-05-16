from __future__ import annotations

import types

from ..serialize import decode_body, decode_header_value


def process_urllib(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    request = frame.f_locals["req"]
    full_url = request.full_url
    method = request.get_method()
    method_and_full_url = f"{method} {full_url}"
    if event == "call":
        request_headers = {
            key: decode_header_value(value) for key, value in request.header_items()
        }

        return {
            "body": decode_body(request.data, request_headers),
            "headers": request_headers,
            "method": method,
            "method_and_full_url": method_and_full_url,
            "url": full_url,
        }

    elif event == "return":  # pragma: no branch
        if arg is None:
            # Probably an exception
            headers = None
            status_code = None
        else:
            response = frame.f_locals["r"]
            headers = dict(response.headers)
            status_code = response.status

        return {
            "body": None,
            "headers": headers,
            "method": method,
            "method_and_full_url": method_and_full_url,
            "status_code": status_code,
            "url": full_url,
        }

    elif event == "unwind":  # pragma: no cover
        return {
            "body": None,
            "headers": None,
            "method": method,
            "method_and_full_url": method_and_full_url,
            "status_code": None,
            "url": full_url,
        }


urllib = {
    "co_names": ("do_open",),
    "path_fragment": "urllib/request",
    "call_type": "outbound_http_request",
    "return_type": "outbound_http_response",
    "subtype": "urllib",
    "process": process_urllib,
}
