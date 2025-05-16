import json
from datetime import datetime

from more_itertools import locate, peekable


def _format_header(header: str) -> str:
    header = header.upper().replace("-", "_")
    if header in ("CONTENT_LENGTH", "CONTENT_TYPE"):
        return header
    return f"HTTP_{header}"


def get_request_headers(request):
    request_headers = {
        _format_header(header): value for header, value in request["headers"].items()
    }
    if "HTTP_COOKIE" in request_headers and request_headers["HTTP_COOKIE"] == "":
        del request_headers["HTTP_COOKIE"]

    request_headers_to_delete = [
        "CONTENT_LENGTH",
        "HTTP_HOST",
        "HTTP_X_FORWARDED_FOR",
        "HTTP_X_FORWARDED_PROTO",
        "HTTP_CONNECTION",
        "HTTP_CACHE_CONTROL",
        "HTTP_DNT",
        "HTTP_SEC_CH_UA",
        "HTTP_USER_AGENT",
        "HTTP_ACCEPT",
        "HTTP_SEC_FETCH_DEST",
        "HTTP_SEC_CH_UA_MOBILE",
        "HTTP_REFERER",
        "HTTP_ACCEPT_ENCODING",
        "HTTP_ACCEPT_LANGUAGE",
        "HTTP_SEC_FETCH_SITE",
        "HTTP_SEC_FETCH_MODE",
        "HTTP_SEC_FETCH_USER",
        "HTTP_SEC_FETCH_DEST",
        "HTTP_SEC_CH_UA_PLATFORM",
        "HTTP_ORIGIN",
        "HTTP_UPGRADE_INSECURE_REQUESTS",
    ]

    for request_header in request_headers_to_delete:
        if request_header in request_headers:
            del request_headers[request_header]

    if "CONTENT_TYPE" in request_headers:
        # This is a special header, which ends up influencing
        # how the django test client formats different parts of the
        # request. It's provided to the test client as a lowercased
        # argument
        content_type = request_headers["CONTENT_TYPE"]
        del request_headers["CONTENT_TYPE"]
        if "multipart/form-data" not in content_type:
            request_headers["content_type"] = content_type
    return request_headers


def group_frames(frames):
    request_indices = peekable(locate(frames, lambda f: f["type"] == "django_request"))
    response_indices = locate(frames, lambda f: f["type"] == "django_response")
    while True:
        try:
            request_index = next(request_indices)
            response_index = next(response_indices)
            while request_indices.peek(len(frames)) < response_index:
                request_index = next(request_indices)
            while response_index < request_index:
                response_index = next(response_indices)
        except StopIteration:
            break

        yield (
            frames[request_index],
            frames[request_index + 1 : response_index],
            frames[response_index],
        )


def parse_request_frames(frames):
    served_request_frames = []
    for request, inner_frames, response in group_frames(frames):
        served_request_frames.append(
            {
                "request": request,
                "response": response,
                "templates": [
                    frame["template"]
                    for frame in inner_frames
                    if frame["type"] == "django_template_start"
                ],
                "frames": inner_frames,
            }
        )
    return served_request_frames


def get_response_json(response):
    content_type = response.get("headers", {}).get("Content-Type", "")
    if "application/json" in content_type:
        return json.loads(response["content"])
    return None


def drop_django_templates(template_names):
    return [
        name
        for name in template_names
        if name is not None  # Templates generated from a string might not have a name
        and not name.startswith("django/")
    ]


def format_timestamp(timestamp):
    return datetime.utcfromtimestamp(timestamp).isoformat(timespec="seconds")
