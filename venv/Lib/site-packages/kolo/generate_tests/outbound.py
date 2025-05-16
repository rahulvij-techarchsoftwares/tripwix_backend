import json
from typing import Dict, List, Optional, TypedDict, cast

from more_itertools import pairwise

from kolo.types import JSON


class OutboundRequest(TypedDict):
    body: str
    headers: Dict[str, str]
    method: str
    method_and_full_url: str
    url: str


class OutboundResponse(TypedDict):
    body: Optional[str]
    headers: Optional[Dict[str, str]]
    method: str
    method_and_full_url: str
    status_code: Optional[int]
    url: str


class OutboundJSONResponse(OutboundResponse, total=False):
    content_type: Optional[str]
    json_body: JSON


class OutboundFrame(TypedDict):
    request: OutboundRequest
    response: OutboundJSONResponse


def update_response_json_body(response: OutboundJSONResponse) -> OutboundJSONResponse:
    if response["headers"] is None:
        return response

    content_type = (
        response["headers"].get("Content-Type")
        or response["headers"].get("content-type")
        or response["headers"].get("CONTENT-TYPE")
    )
    response["content_type"] = content_type
    content_type_is_json = content_type and "application/json" in content_type
    body = response.get("body", None)
    if content_type_is_json and isinstance(body, str):
        response["json_body"] = json.loads(body)
    return response


def parse_outbound_frames(frames) -> List[OutboundFrame]:
    frames = (
        frame
        for frame in frames
        if frame["type"] in ("outbound_http_request", "outbound_http_response")
    )

    without_urllib3 = (frame for frame in frames if frame["subtype"] != "urllib3")

    outbound_frames = []
    for request, response in pairwise(without_urllib3):
        if (
            request["type"] != "outbound_http_request"
            or response["type"] != "outbound_http_response"
        ):
            # We don't have a (request, response) pair, so move ahead.
            # Usually this is (response, request), but could also be
            # (request, request) or (response, response) if the trace
            # failed to record as expected.
            continue  # pragma: no cover

        response = update_response_json_body(response)
        outbound_frame: OutboundFrame = {"request": request, "response": response}
        outbound_frames.append(outbound_frame)

    return outbound_frames
