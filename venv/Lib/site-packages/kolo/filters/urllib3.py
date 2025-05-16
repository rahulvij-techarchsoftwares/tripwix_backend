from __future__ import annotations

import types

from ..serialize import decode_body, decode_header_value


def get_full_url(frame_locals) -> str:
    scheme = frame_locals["self"].scheme
    host = frame_locals["self"].host
    port = frame_locals["self"].port
    if (
        port is None
        or (scheme == "https" and port == 443)
        or (scheme == "http" and port == 80)
    ):
        port = ""
    else:
        port = f":{port}"
    url = frame_locals["url"]
    return f"{scheme}://{host}{port}{url}"


def process_urllib3(
    frame: types.FrameType,
    event: str,
    arg: object,
    context,
):
    frame_locals = frame.f_locals
    full_url = get_full_url(frame_locals)
    method = frame_locals["method"].upper()
    method_and_full_url = f"{method} {full_url}"

    if event == "call":
        request_headers = {
            key: decode_header_value(value)
            for key, value in frame_locals["headers"].items()
        }

        return {
            "body": decode_body(frame_locals["body"], request_headers),
            "headers": request_headers,
            "method": method,
            "method_and_full_url": method_and_full_url,
            "url": full_url,
        }

    assert event == "return"

    try:
        response = frame_locals["response"]
    except KeyError:
        headers = None
        status = None
    else:
        headers = dict(response.headers)
        status = response.status

    return {
        "body": None,
        "headers": headers,
        "method": method,
        "method_and_full_url": method_and_full_url,
        "status_code": status,
        "url": full_url,
    }


urllib3 = {
    "co_names": ("urlopen",),
    "path_fragment": "urllib3/connectionpool",
    "call_type": "outbound_http_request",
    "return_type": "outbound_http_response",
    "subtype": "urllib3",
    "process": process_urllib3,
}
