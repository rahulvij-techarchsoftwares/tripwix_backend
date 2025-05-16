from __future__ import annotations

import contextlib
import inspect
import io
import json
import logging
import os
import sys
from typing import Awaitable, Callable, List

from asgiref.sync import iscoroutinefunction, markcoroutinefunction, sync_to_async
from django.conf import settings
from django.core.servers.basehttp import ServerHandler
from django.http import (
    FileResponse,
    HttpRequest,
    HttpResponse,
    HttpResponseNotFound,
    JsonResponse,
)

from .checks import get_third_party_profiler
from .config import load_config
from .db import setup_db
from .open_in_pycharm import OpenInPyCharmError
from .profiler import enable
from .serialize import monkeypatch_queryset_repr
from .settings import get_webapp_settings
from .web.api import (
    check_vacuum_needed,
    get_latest_version_info,
    get_project_root,
    get_user_info,
    handle_open_editor,
    handle_static_file,
    handle_user_info_update,
    save_settings_data,
)
from .web.django import (
    kolo_web_api_delete_trace,
    kolo_web_api_generate_test,
    kolo_web_api_get_trace,
    kolo_web_api_latest_traces,
    kolo_web_api_source_file,
    kolo_web_home,
)

logger = logging.getLogger("kolo")

DjangoView = Callable[[HttpRequest], HttpResponse]
DjangoAsyncView = Callable[[HttpRequest], Awaitable[HttpResponse]]


def get_host(args):
    if len(args) < 2:
        return ""

    if args[1] != "runserver":
        return ""

    ipv6 = "-6" in args or "--ipv6" in args
    if ipv6:
        host = "[::1]"
    else:
        host = "127.0.0.1"

    args = [arg for arg in args[2:] if not arg.startswith("-")]

    if not args:
        port = 8000
    else:
        _host, sep, port = args[0].rpartition(":")
        if sep:
            host = _host

    return f"http://{host}:{port}"


class KoloMiddleware:
    sync_capable = True
    async_capable = True

    def __init__(self, get_response: DjangoView | DjangoAsyncView) -> None:
        self._is_coroutine = iscoroutinefunction(get_response)
        if self._is_coroutine:
            markcoroutinefunction(self)
        self._get_response = get_response
        self.config = load_config()
        if settings.DEBUG:
            self.upload_token = None
        else:
            self.upload_token = self.get_upload_token()
        self.enabled = self.should_enable()
        if self.enabled:
            self.db_path = setup_db()

            # TODO: Put the full URL here not just the /_kolo/ path
            if not self.config.get("hide_startup_message", False):
                host = get_host(sys.argv)
                print(f"\nView recent requests at {host}/_kolo/")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.path.startswith("/_kolo"):
            if self._is_coroutine:
                hide_from_daphne()
                return sync_to_async(kolo_web_router)(request)  # type: ignore[return-value]
            return kolo_web_router(request)

        if not self._is_coroutine:
            get_response = self.get_response
        else:
            get_response = self.aget_response  # type: ignore

        # WARNING: Because Django's runserver uses threading, we need
        # to be careful about thread safety here.
        if not self.enabled or self.check_for_third_party_profiler():
            return get_response(request)

        filter_config = self.config.get("filters", {})
        ignore_request_paths = filter_config.get("ignore_request_paths", [])
        for path in ignore_request_paths:
            if path in request.path:
                return get_response(request)

        monkeypatch_queryset_repr()
        if self._is_coroutine:
            return self.aprofile_response(request)
        else:
            return self.profile_response(request)

    def profile_response(self, request):
        with enable(
            self.config,
            source="kolo.middleware.KoloMiddleware",
            _save_in_thread=True,
            _upload_token=self.upload_token,
        ):
            response = self.get_response(request)
        return response

    async def aprofile_response(self, request):
        with enable(
            self.config,
            source="kolo.middleware.KoloMiddleware",
            _save_in_thread=True,
            _upload_token=self.upload_token,
        ):
            response = await self.aget_response(request)
        return response

    async def aget_response(self, request: HttpRequest) -> HttpResponse:
        response = await self._get_response(request)  # type: ignore
        return response

    def get_response(self, request: HttpRequest) -> HttpResponse:
        response = self._get_response(request)
        return response  # type: ignore

    def check_for_third_party_profiler(self) -> bool:
        profiler = get_third_party_profiler(self.config)
        if profiler:
            logger.warning("Profiler %s is active, disabling KoloMiddleware", profiler)
            return True
        return False

    def should_enable(self) -> bool:
        if settings.DEBUG is False and self.upload_token is None:
            logger.debug("DEBUG mode is off, disabling KoloMiddleware")
            return False

        if os.environ.get("KOLO_DISABLE", "false").lower() not in ["false", "0"]:
            logger.debug("KOLO_DISABLE is set, disabling KoloMiddleware")
            return False

        return not self.check_for_third_party_profiler()

    def get_upload_token(self):
        if not self.config.get("production_beta", False):
            return None

        upload_token = os.environ.get("KOLO_API_TOKEN", None)
        if upload_token is None:
            logging.warning(
                "Kolo production beta is enabled, but `KOLO_API_TOKEN` environment variable is not set."
            )
            return None

        if upload_token.startswith("kolo_prod_"):
            return upload_token

        logging.warning("`KOLO_API_TOKEN` is invalid.")
        return None


@contextlib.contextmanager
def hide_from_runserver(*args, **kwds):
    """
    Hides the requestline log messages from runserver's stdout.
    This works because Django's runserver is built on `wsgiref` which is ultimately built on `TCPServer` and the notion
    of a "server" creating a class "per request" which means we can rely on there being one `WSGIRequestHandler`
    for every incoming request, and we can modify that instance's methods to silence it.

    We don't want to restore the original method on exiting the context manager, because that would be "too soon" and
    the log message would ultimately still get spooled out at the WSGI server layer later (i.e. higher up the callstack)
    """

    def no_log(*a, **kw):
        return None

    for frame in inspect.stack():
        if "self" in frame.frame.f_locals:
            if isinstance(frame.frame.f_locals["self"], ServerHandler):
                server_handler = frame.frame.f_locals["self"]
                if hasattr(server_handler, "request_handler"):
                    server_handler.request_handler.log_message = no_log
    yield


DAPHNE_PATCHED = False


def hide_from_daphne(*args, **kwds):
    """
    Hides the requestline log messages from daphne runserver's stdout.
    """

    global DAPHNE_PATCHED

    if DAPHNE_PATCHED:
        return

    from daphne.server import Server

    for frame in inspect.stack():
        if "self" in frame.frame.f_locals:
            server = frame.frame.f_locals["self"]
            if isinstance(server, Server):
                old_log = server.action_logger

                def no_log(protocol, action, details):
                    if details["path"].startswith("/_kolo"):
                        return None
                    return old_log(protocol, action, details)

                server.action_logger = no_log
                DAPHNE_PATCHED = True
                break


@hide_from_runserver()
def kolo_web_router(request: HttpRequest) -> HttpResponse:
    request.get_host()  # Trigger any ALLOWED_HOSTS error
    path = request.path

    # Static paths
    if path.startswith("/_kolo/static/"):
        try:
            contents, mime_type = handle_static_file(path[len("/_kolo/static/") :])
            return FileResponse(
                io.BytesIO(contents),
                content_type=mime_type,
            )  # type: ignore # FileResponse inherits from StreamingHttpResponse but hard to fix the downstream errors when fixing that type
        except FileNotFoundError:
            return HttpResponseNotFound("File not found")

    # API paths
    elif path.startswith("/_kolo/api"):
        if path.startswith("/_kolo/api/generate-test/"):
            return kolo_web_api_generate_test(request)
        elif path.startswith("/_kolo/api/traces/"):
            if request.method == "GET":
                return kolo_web_api_get_trace(request)
            elif request.method == "DELETE":
                return kolo_web_api_delete_trace(request)
            else:
                return HttpResponseNotFound("Kolo Web: Not Found")
        elif path.startswith("/_kolo/api/latest-traces/"):
            return kolo_web_api_latest_traces(request)
        elif path.startswith("/_kolo/api/save-test/"):
            return kolo_web_api_save_test(request)
        elif path.startswith("/_kolo/api/config/"):
            return kolo_web_api_config(request)
        elif path.startswith("/_kolo/api/init/"):
            return kolo_web_api_init(request)
        elif path.startswith("/_kolo/api/settings/"):
            return kolo_web_api_settings(request)
        elif path.startswith("/_kolo/api/source-file/"):
            return kolo_web_api_source_file(request)
        elif path.startswith("/_kolo/api/open-editor/"):
            return kolo_web_api_open_editor(request)
        elif path.startswith("/_kolo/api/user-info/"):
            return kolo_web_api_user_info(request)
        elif path.startswith("/_kolo/api/latest-version/"):
            return kolo_web_api_latest_version(request)
        else:
            return HttpResponseNotFound("Kolo Web API: Not Found")

    # SPA path (let React render and handle the path)
    else:
        return kolo_web_home(request)


def kolo_web_api_save_test(request: HttpRequest) -> HttpResponse:
    project_folder = get_project_root()
    data = json.loads(request.body.decode("utf-8"))
    file_content: str = data["content"]
    relative_file_path: List[str] = data["path"]
    file_path = project_folder / os.path.join(*relative_file_path)

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as file:
        file.write(file_content)

    return JsonResponse({"file_path": f"{file_path}"})


def kolo_web_api_config(request: HttpRequest) -> HttpResponse:
    return JsonResponse(load_config())


def kolo_web_api_init(request: HttpRequest) -> HttpResponse:
    did_vacuum, last_vacuumed = check_vacuum_needed()
    return JsonResponse({"did_vacuum": did_vacuum, "last_vacuumed": last_vacuumed})


def kolo_web_api_settings(request: HttpRequest) -> HttpResponse:
    """
    Return the `webapp_settings` stored in the `kolo_kv` SQLite table.
    """
    if request.method == "GET":
        return JsonResponse(get_webapp_settings())
    elif request.method == "POST":
        settings = json.loads(request.body.decode("utf-8"))
        save_settings_data(settings)
        return JsonResponse({"ok": True})
    else:
        return JsonResponse({"ok": False}, status=404)


def kolo_web_api_open_editor(request: HttpRequest) -> HttpResponse:
    file_path = request.GET["path"]
    editor = request.GET["editor"]
    try:
        handle_open_editor(file_path, editor)
        return JsonResponse({"ok": True})
    except OpenInPyCharmError as e:
        return JsonResponse({"ok": False, "message": e.message}, status=500)


def kolo_web_api_user_info(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        return JsonResponse(get_user_info())
    elif request.method == "POST":
        data = json.loads(request.body.decode("utf-8"))
        email = data["email"]
        try:
            handle_user_info_update(email)
            return JsonResponse({"ok": True})
        except ValueError as e:
            return JsonResponse({"ok": False, "message": str(e)}, status=400)
        except IOError as e:
            logger.error("Could not save user details", e)
            return JsonResponse(
                {"ok": False, "message": "Could not save user details"}, status=500
            )
    else:
        return JsonResponse({"ok": False}, status=404)


def kolo_web_api_latest_version(request: HttpRequest) -> JsonResponse:
    try:
        version = get_latest_version_info()
        return JsonResponse({"latest_version": version})
    except ValueError as e:
        return JsonResponse({"ok": False, "message": str(e)}, status=500)
