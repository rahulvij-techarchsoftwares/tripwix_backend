from hashlib import sha1

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.cache import patch_response_headers
from django.utils.dateparse import parse_datetime
from django.utils.http import http_date
from django.views.decorators.cache import cache_control
from django.views.decorators.http import condition, conditional_page

from ..db import get_db_last_modified
from .api import delete_trace, generate_test, get_trace, latest_traces, read_source_file
from .home import web_home_html


def kolo_web_home(request: HttpRequest) -> HttpResponse:
    return HttpResponse(web_home_html(running_in_user_django=True))


def get_last_modified(request):
    """
    Return the last modified time of the db.

    Cache the value on request to avoid duplicate work in
    kolo_web_api_latest_traces_etag and kolo_web_api_latest_traces_last_modified
    which can be called in either order based on the Django version.

    The order changed in Django 5.0:
    https://github.com/django/django/commit/d3d173425fc0a1107836da5b4567f1c88253191b
    """
    try:
        return request._db_last_modified
    except AttributeError:
        request._db_last_modified = get_db_last_modified()
    return request._db_last_modified


def kolo_web_api_latest_traces_etag(request, *a, **kwargs):
    last_modified = get_last_modified(request)
    if last_modified is not None:
        return sha1(last_modified.isoformat().encode("utf-8")).hexdigest()
    return None


def kolo_web_api_latest_traces_last_modified(request, *a, **kwargs):
    return get_last_modified(request)


@cache_control(max_age=1)
@condition(
    etag_func=kolo_web_api_latest_traces_etag,
    last_modified_func=kolo_web_api_latest_traces_last_modified,
)
def kolo_web_api_latest_traces(request: HttpRequest) -> HttpResponse:
    if "anchor" in request.GET and "showNext" in request.GET:
        anchor = request.GET["anchor"]
        show_next = int(request.GET["showNext"])
    else:
        anchor = None
        show_next = int(request.GET.get("showNext", 10))

    return JsonResponse(latest_traces(show_next, anchor))


@conditional_page
def kolo_web_api_get_trace(request: HttpRequest) -> HttpResponse:
    trace_id = request.path.replace("/_kolo/api/traces/", "").replace("/", "")
    msgpack_data, created_at = get_trace(trace_id)
    response = HttpResponse(msgpack_data, content_type="application/msgpack")
    # When Chrome (Blink) and Safari (WebKit) do a `fetch()` request, they include the `If-None-Match` and
    # `If-Modified-Since` headers which allow for `ETag` (or `Last-Modified`) matching and returning a
    # 304 (Not Modified) response. FireFox (Gecko) only does so if a {cache: "force-cache"} value is given as options.
    last_modified = parse_datetime(created_at)
    if last_modified is not None:
        response["Last-Modified"] = http_date(last_modified.timestamp())
    response["ETag"] = trace_id
    # Once we've seen the trace, don't even try asking for the URL again for a while (a month) - because the traces are
    # ostensibly immutable, we should only really expect to *need* to ask for them again upon cache eviction
    patch_response_headers(response, cache_timeout=86400 * 28)
    return response


def kolo_web_api_delete_trace(request: HttpRequest) -> HttpResponse:
    trace_id = request.path.replace("/_kolo/api/traces/", "").replace("/", "")
    return JsonResponse(delete_trace(trace_id))


def kolo_web_api_generate_test(request: HttpRequest) -> HttpResponse:
    trace_id = request.path.replace("/_kolo/api/generate-test/", "").replace("/", "")
    return JsonResponse(generate_test(trace_id))


def kolo_web_api_source_file(request: HttpRequest) -> HttpResponse:
    file_path = request.GET["path"]
    return JsonResponse(read_source_file(file_path))
