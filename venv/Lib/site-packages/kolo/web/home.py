from __future__ import annotations

import json
import os

from ..config import create_kolo_directory
from ..settings import get_webapp_settings
from ..version import __version__


def web_home_html(running_in_user_django: bool):
    kolo_dir = create_kolo_directory()
    project_folder = kolo_dir.parent
    settings = get_webapp_settings()

    source_dir = os.path.dirname(__file__)
    with open(f"{source_dir}/templates/home.html") as f:
        html = f.read().format(
            settings=json.dumps(settings),
            __version__=json.dumps(__version__),
            project_folder=json.dumps(str(project_folder)),
            running_in_user_django=json.dumps(running_in_user_django),
        )
    return html
