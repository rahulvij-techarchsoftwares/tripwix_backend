import json
from typing import Literal, TypedDict

from . import kv

WEBAPP_SETTINGS_KEY = "webapp_settings"


class WebappSettings(TypedDict):
    auto_delete_old_traces: bool
    default_text_editor: Literal["vscode", "pycharm"]


default_webapp_settings: WebappSettings = {
    "auto_delete_old_traces": True,
    "default_text_editor": "vscode",
}


def get_webapp_settings() -> WebappSettings:
    try:
        value = kv.get_value(WEBAPP_SETTINGS_KEY)
    except KeyError:
        return default_webapp_settings
    saved_settings: WebappSettings = json.loads(value) if value else {}  # type: ignore
    return {**default_webapp_settings, **saved_settings}


def save_webapp_settings(settings: WebappSettings):
    kv.set(WEBAPP_SETTINGS_KEY, json.dumps(settings))
