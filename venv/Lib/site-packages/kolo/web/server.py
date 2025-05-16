from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from functools import cached_property
from hashlib import sha1
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import parse_qsl, urlparse

from ..config import load_config
from ..db import get_db_last_modified
from ..open_in_pycharm import OpenInPyCharmError
from ..settings import get_webapp_settings
from .api import (
    check_vacuum_needed,
    delete_trace,
    get_latest_version_info,
    get_trace,
    get_user_info,
    handle_open_editor,
    handle_static_file,
    handle_user_info_update,
    latest_traces,
    read_source_file,
    save_settings_data,
)
from .home import web_home_html

logger = logging.getLogger("kolo")


class KoloRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        # Skip logging for latest-traces endpoint
        if "/latest-traces/" in args[0]:
            return

        if "/static/" in args[0] or "favicon.ico" in args[0]:
            return

        if "/api/init/" in args[0] or "favicon.ico" in args[0]:
            return

        # Keep default logging for all other requests
        super().log_message(format, *args)

    @cached_property
    def url(self):
        return urlparse(self.path)

    @cached_property
    def query_data(self):
        return dict(parse_qsl(self.url.query))

    def set_cache_headers(
        self,
        max_age: int,
        etag: Optional[str] = None,
        last_modified: Optional[str | float | int | datetime] = None,
        immutable: bool = False,
    ) -> None:
        """Set common caching headers.

        Args:
            max_age: Cache duration in seconds
            etag: Optional ETag value
            last_modified: Optional timestamp (accepts datetime, string, float, or int)
            immutable: Whether to mark the response as immutable
        """
        cache_control = f"max-age={max_age}"
        if immutable:
            cache_control += ", immutable"
        self.send_header("Cache-Control", cache_control)
        if etag:
            self.send_header("ETag", etag)  # Django doesn't quote these either
        if last_modified is not None:
            if isinstance(last_modified, datetime):
                timestamp = last_modified.timestamp()
            elif isinstance(last_modified, (int, float)):
                timestamp = float(last_modified)
            else:
                # Try parsing as datetime string
                timestamp = datetime.fromisoformat(str(last_modified)).timestamp()
            self.send_header("Last-Modified", self.date_time_string(int(timestamp)))
            # Add Expires header to match Django
            expires = datetime.now() + timedelta(seconds=max_age)
            self.send_header("Expires", self.date_time_string(int(expires.timestamp())))

    def is_not_modified(self, etag: str) -> bool:
        """Check if the client's cached version is still valid."""
        if_none_match = self.headers.get("If-None-Match")
        return if_none_match == etag

    def send_not_modified(self) -> None:
        """Send a 304 Not Modified response."""
        self.send_response(HTTPStatus.NOT_MODIFIED)
        self.end_headers()

    def send_response_with_content(
        self,
        content: bytes,
        content_type: str,
        status: HTTPStatus = HTTPStatus.OK,
        max_age: Optional[int] = None,
        etag: Optional[str] = None,
        last_modified: Optional[str | float | int | datetime] = None,
        immutable: bool = False,
    ) -> None:
        """Send a response with proper HTTP headers."""
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))

        if max_age is not None:
            self.set_cache_headers(max_age, etag, last_modified, immutable)

        self.end_headers()
        self.wfile.write(content)
        self.wfile.flush()

    def send_error_response(self, code: HTTPStatus, message: str):
        """Send a complete error response with message."""
        # Use the parent class's send_response_only for the status line
        super().send_response_only(code, message)
        message_bytes = message.encode("utf-8")
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(message_bytes)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(message_bytes)

    def do_GET(self):
        if self.path.startswith("/_kolo/static/"):
            self.handle_static()
        elif self.path.startswith("/_kolo/api/traces/"):
            self.get_trace()
        elif self.path.startswith("/_kolo/api/latest-traces/"):
            self.latest_traces()
        elif self.path.startswith("/_kolo/api/source-file/"):
            self.get_source_file()
        elif self.path.startswith("/_kolo/api/config/"):
            self.get_config()
        elif self.path.startswith("/_kolo/api/init/"):
            self.init()
        elif self.path.startswith("/_kolo/api/settings/"):
            self.get_settings()
        elif self.path.startswith("/_kolo/api/open-editor/"):
            self.open_editor()
        elif self.path.startswith("/_kolo/api/user-info/"):
            self.get_user_info()
        elif self.path.startswith("/_kolo/api/latest-version/"):
            self.get_latest_version()
        elif self.path.startswith("/_kolo/api"):
            self.send_error_response(HTTPStatus.NOT_FOUND, "Kolo Web API: Not Found")
        elif self.path.startswith("/_kolo/"):
            self.web_home()
        else:
            self.send_response(HTTPStatus.PERMANENT_REDIRECT)
            self.send_header("Location", "/_kolo/")
            self.end_headers()

    def do_DELETE(self):
        if self.path.startswith("/_kolo/api/traces/"):
            self.delete_trace()
        else:
            self.send_error_response(HTTPStatus.NOT_FOUND, "Kolo Web API: Not Found")

    def do_POST(self):
        if self.path.startswith("/_kolo/api/settings/"):
            self.save_settings()
        elif self.path.startswith("/_kolo/api/user-info/"):
            self.save_user_info()
        else:
            self.send_error_response(HTTPStatus.NOT_FOUND, "Kolo Web API: Not Found")

    def web_home(self):
        html = web_home_html(running_in_user_django=False)

        self.send_response_with_content(
            content=html.encode("utf-8"), content_type="text/html; charset=utf-8"
        )

    def write_json(self, json_data):
        self.send_response_with_content(
            content=json_data.encode("utf-8"), content_type="application/json"
        )

    def get_trace(self):
        trace_id = self.path.replace("/_kolo/api/traces/", "").replace("/", "")
        msgpack_data, created_at = get_trace(trace_id)

        self.send_response_with_content(
            content=msgpack_data,
            content_type="application/msgpack",
            max_age=2419200,  # 28 days
            etag=trace_id,
            last_modified=created_at,
            immutable=True,  # Mark trace responses as immutable
        )

    def delete_trace(self):
        trace_id = self.path.replace("/_kolo/api/traces/", "").replace("/", "")
        deleted = delete_trace(trace_id)
        self.write_json(json.dumps(deleted))

    def latest_traces(self):
        last_modified = get_db_last_modified()
        etag = (
            sha1(last_modified.isoformat().encode("utf-8")).hexdigest()
            if last_modified
            else None
        )
        if etag and self.is_not_modified(etag):
            return self.send_not_modified()

        if "anchor" in self.query_data and "showNext" in self.query_data:
            anchor = self.query_data["anchor"]
            show_next = int(self.query_data["showNext"])
        else:
            anchor = None
            show_next = int(self.query_data.get("show_next", 10))

        trace_json = json.dumps(latest_traces(show_next, anchor))

        self.send_response_with_content(
            content=trace_json.encode("utf-8"),
            content_type="application/json",
            max_age=1,
            etag=etag,
            last_modified=last_modified.timestamp() if last_modified else None,
        )

    def get_source_file(self):
        path = self.query_data["path"]
        source = read_source_file(path)
        self.write_json(json.dumps(source))

    def handle_static(self):
        file_path = self.path[len("/_kolo/static/") :]
        try:
            contents, mime_type = handle_static_file(file_path)
            self.send_response_with_content(content=contents, content_type=mime_type)
        except FileNotFoundError:
            self.send_error_response(HTTPStatus.NOT_FOUND, "File not found")

    def get_config(self):
        config = load_config()
        self.write_json(json.dumps(config))

    def init(self):
        did_vacuum, last_vacuumed = check_vacuum_needed()
        self.write_json(
            json.dumps({"did_vacuum": did_vacuum, "last_vacuumed": last_vacuumed})
        )

    def get_settings(self):
        settings = get_webapp_settings()
        self.write_json(json.dumps(settings))

    def save_settings(self):
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        settings = json.loads(body.decode("utf-8"))
        save_settings_data(settings)
        self.write_json(json.dumps({"ok": True}))

    def open_editor(self):
        file_path = self.query_data["path"]
        editor = self.query_data["editor"]
        try:
            handle_open_editor(file_path, editor)
            self.write_json(json.dumps({"ok": True}))
        except OpenInPyCharmError as e:
            self.send_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, e.message)

    def get_user_info(self):
        self.write_json(json.dumps(get_user_info()))

    def save_user_info(self):
        content_length = int(self.headers["Content-Length"])
        body = self.rfile.read(content_length)
        data = json.loads(body.decode("utf-8"))
        email = data["email"]

        try:
            handle_user_info_update(email)
            self.write_json(json.dumps({"ok": True}))
        except ValueError as e:
            self.send_error_response(HTTPStatus.BAD_REQUEST, str(e))
        except IOError as e:
            logger.error("Could not save user details", e)
            self.send_error_response(
                HTTPStatus.INTERNAL_SERVER_ERROR, "Could not save user details"
            )

    def get_latest_version(self):
        try:
            version = get_latest_version_info()
            self.write_json(json.dumps({"latest_version": version}))
        except ValueError as e:
            self.send_error_response(HTTPStatus.INTERNAL_SERVER_ERROR, str(e))
