from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "report_chat_id": None,
    "starts_thread_id": None,
    "files_thread_id": None,
}


def _parse_int(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def load_config() -> dict[str, Any]:
    config = dict(DEFAULT_CONFIG)

    if CONFIG_PATH.exists():
        try:
            raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Invalid config.json, using defaults.")
            raw = {}
        if isinstance(raw, dict):
            for key in DEFAULT_CONFIG:
                if key in raw:
                    config[key] = _parse_int(raw.get(key))

    load_dotenv()
    env_overrides = {
        "report_chat_id": _parse_int(os.getenv("REPORT_CHAT_ID")),
        "starts_thread_id": _parse_int(os.getenv("STARTS_THREAD_ID")),
        "files_thread_id": _parse_int(os.getenv("FILES_THREAD_ID")),
    }
    for key, value in env_overrides.items():
        if value is not None:
            config[key] = value

    return config


def save_config(config: dict[str, Any]) -> None:
    payload = {key: _parse_int(config.get(key)) for key in DEFAULT_CONFIG}
    CONFIG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_admin_user_ids() -> set[int]:
    load_dotenv()
    raw = os.getenv("ADMIN_USER_IDS", "")
    if not raw:
        return set()
    ids = set()
    for item in raw.split(","):
        value = _parse_int(item)
        if value is not None:
            ids.add(value)
    return ids
