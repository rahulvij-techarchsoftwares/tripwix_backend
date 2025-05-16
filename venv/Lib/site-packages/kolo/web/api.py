from __future__ import annotations

import datetime
import json
import mimetypes
import os
import xml.etree.ElementTree as ET
from itertools import chain
from pathlib import Path
from typing import Optional, Tuple
from urllib.request import urlopen

import platformdirs

from .. import kv
from ..config import create_kolo_directory, load_config
from ..db import (
    db_connection,
    delete_traces_before,
    delete_traces_by_id,
    load_trace_from_db,
    setup_db,
    vacuum_db,
)
from ..generate_tests import build_test_context, create_test_plan
from ..open_in_pycharm import open_in_pycharm
from ..settings import WebappSettings, get_webapp_settings, save_webapp_settings


def latest_traces(show_next, anchor=None):
    db_path = setup_db()
    with db_connection(db_path) as connection:
        needs_reversed_order = False
        reached_top = False

        if anchor is not None:
            limit = abs(show_next)

            # Positive show_next value means we're going back in time (loading _more_ traces),
            # negative value is for going forward in time (loading traces the user has previously seen before going back).

            if show_next > 0:
                # going back in time, trying to access older traces than the anchor

                query = "SELECT id FROM traces WHERE id < ? ORDER BY id desc LIMIT ?"
                cursor = connection.execute(query, (anchor, limit))
                rows = cursor.fetchall()
            else:
                # going forward in time, trying to access newer traces than the anchor

                query = "SELECT id FROM traces WHERE id > ? ORDER BY id LIMIT ?"
                needs_reversed_order = True
                # In order to get 10 newer traces, they need to be sorted in ascending order.
                # They have to be reversed later because the endpoint should always return traces from newest to oldest.

                cursor = connection.execute(query, (anchor, limit))
                rows = cursor.fetchall()

                if len(rows) < abs(limit):
                    # If there are less than 10 newer traces, we need to fetch some older traces to fill up the response.
                    cursor = connection.execute(
                        "SELECT id FROM traces ORDER BY id desc LIMIT ?", (abs(limit),)
                    )
                    rows = cursor.fetchall()

                    reached_top = True
                    needs_reversed_order = False
        else:
            # not a pagination request, we just want N latest traces

            cursor = connection.execute(
                "SELECT id FROM traces ORDER BY id desc LIMIT ?", (show_next,)
            )

            rows = cursor.fetchall()
            reached_top = True

    traces = list(chain.from_iterable(rows))

    if needs_reversed_order:
        traces = traces[::-1]

    return {"traces": traces, "isTop": reached_top}


def get_trace(trace_id):
    db_path = setup_db()
    return load_trace_from_db(db_path, trace_id)


def delete_trace(trace_id):
    db_path = setup_db()
    count = delete_traces_by_id(db_path, (trace_id,))
    return {"deleted": count}


def generate_test(trace_id):
    test_class = "MyTestCase"
    test_name = "test_my_view"

    config = load_config()
    context = build_test_context(
        trace_id, test_class=test_class, test_name=test_name, config=config
    )
    plan = create_test_plan(config, context)

    return {"test_code": plan.render(), "plan": plan.as_json()}


def get_project_root() -> Path:
    """Returns the absolute path of the project."""
    # Daniel: I'm not sure if this is correct, it just works on a simple
    # Django project.
    kolo_dir = create_kolo_directory()
    project_folder = kolo_dir.parent
    return project_folder


def read_source_file(file_path):
    assert file_path.endswith(".py")

    if not os.path.isabs(file_path):
        project_path = get_project_root()
        file_path = os.path.join(project_path, file_path)

    with open(file_path, "r") as f:
        content = f.read()

    return {"path": file_path, "content": content}


def delete_old_traces_and_vacuum():
    db_path = setup_db()
    delete_traces_before(db_path, datetime.datetime.now() - datetime.timedelta(days=30))
    vacuum_db(db_path)
    last_vacuumed = datetime.datetime.now().isoformat()
    kv.set("last_vacuumed", last_vacuumed)
    return last_vacuumed


def get_user_data_dir() -> Path:
    # Get the appropriate user data directory for the current platform
    user_data_dir = Path(platformdirs.user_data_dir(appname="kolo", appauthor="kolo"))

    # Check if the directory exists, create it if it doesn't
    if not os.path.exists(user_data_dir):
        try:
            os.makedirs(user_data_dir)
        except OSError:
            pass

    # Check if the directory is writable.
    # Important in order not to get stuck reading a directory we can never write to.
    if os.access(user_data_dir, os.W_OK):
        return user_data_dir
    # Otherwise, use the Kolo project directory.
    # User info won't be persisted across projects.
    else:
        return create_kolo_directory()


def get_user_data_filepath() -> Path:
    return get_user_data_dir() / Path("user-info.json")


def get_user_info() -> dict:
    file_path = get_user_data_filepath()
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
            return data
    except OSError:
        return {}


def is_valid_email(email: str) -> bool:
    if not email:
        return False
    handle, at, domain = email.partition("@")
    return bool(handle) and bool(at) and bool(domain)


def save_user_info(data: dict):
    file_path = get_user_data_filepath()
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)


def handle_static_file(static_path: str) -> Tuple[bytes, str]:
    """Handle static file requests, returns (file_contents, mime_type)"""
    source_dir = os.path.dirname(__file__)
    static_file = f"{source_dir}/static/{static_path}"

    with open(static_file, "rb") as f:
        contents = f.read()

    mime_type, _ = mimetypes.guess_type(static_path)
    return contents, mime_type or "application/octet-stream"


def handle_open_editor(file_path: str, editor: str) -> None:
    """Handle opening files in external editors"""
    assert file_path.endswith(".py")
    assert editor == "pycharm"  # Currently only support PyCharm

    if not os.path.isabs(file_path):
        project_path = get_project_root()
        file_path = os.path.join(project_path, file_path)

    open_in_pycharm(file_path)


def save_settings_data(settings_data: WebappSettings) -> None:
    """Save webapp settings"""
    save_webapp_settings(settings_data)


def handle_user_info_update(email: str) -> None:
    """Handle user info updates with validation"""
    if not is_valid_email(email):
        raise ValueError("Invalid email")
    save_user_info({"email": email})


def get_latest_version_info() -> str:
    """Get latest version from PyPI RSS feed"""
    # We have an implementation of this in TypeScript (see extension/version.ts).
    # But we are re-implementing it here because PyPI doesn't support CORS, so we
    # can't use that implementation on the client-side.

    url = "https://pypi.org/rss/project/kolo/releases.xml"
    with urlopen(url) as response:
        rss_content = response.read()

    root = ET.fromstring(rss_content)
    channel = root.find("channel")
    if channel is None:
        raise ValueError("Could not find channel in RSS feed")

    first_item = channel.find("item")
    if first_item is None:
        raise ValueError("Could not find item in RSS feed")

    title = first_item.find("title")
    if title is None or title.text is None:
        raise ValueError("Could not extract Kolo version from RSS feed")

    return title.text


def check_vacuum_needed() -> Tuple[bool, Optional[str]]:
    """Check if vacuum is needed and perform it if necessary"""
    did_vacuum = False
    try:
        last_vacuumed = kv.get_value("last_vacuumed")
    except KeyError:
        last_vacuumed = None

    settings = get_webapp_settings()
    if settings["auto_delete_old_traces"]:
        one_day_ago = datetime.datetime.now() - datetime.timedelta(days=1)
        if (
            last_vacuumed is None
            or datetime.datetime.fromisoformat(last_vacuumed) < one_day_ago
        ):
            last_vacuumed = delete_old_traces_and_vacuum()
            did_vacuum = True

    return did_vacuum, last_vacuumed
