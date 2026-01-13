from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from aiogram import Bot
from aiogram.types import FSInputFile, User

try:
    from .config import load_config
except ImportError:  # pragma: no cover - allow running as a script
    from config import load_config

logger = logging.getLogger(__name__)


async def send_start_report(bot: Bot, user: User) -> None:
    config = load_config()
    chat_id = config.get("report_chat_id")
    thread_id = config.get("starts_thread_id")
    if not chat_id or not thread_id:
        logger.warning("Start reports not configured. report_chat_id=%s starts_thread_id=%s", chat_id, thread_id)
        return

    username = f"@{user.username}" if user.username else "нет username"
    name_parts = [user.first_name, user.last_name]
    name = " ".join(part for part in name_parts if part) or "без имени"
    time_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        "🚀 Запуск бота\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"UserID: {user.id}\n"
        f"Time: {time_value}"
    )
    try:
        await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text)
    except Exception:  # noqa: BLE001 - logging for external API errors
        logger.exception("Failed to send start report.")


async def send_doc_start_report(bot: Bot, user: User, doc_label: str) -> None:
    config = load_config()
    chat_id = config.get("report_chat_id")
    thread_id = config.get("starts_thread_id")
    if not chat_id or not thread_id:
        logger.warning("Start reports not configured. report_chat_id=%s starts_thread_id=%s", chat_id, thread_id)
        return

    username = f"@{user.username}" if user.username else "нет username"
    name_parts = [user.first_name, user.last_name]
    name = " ".join(part for part in name_parts if part) or "без имени"
    time_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    text = (
        f"📝 Начало заполнения ({doc_label})\n"
        f"Имя: {name}\n"
        f"Username: {username}\n"
        f"UserID: {user.id}\n"
        f"Time: {time_value}"
    )
    try:
        await bot.send_message(chat_id=chat_id, message_thread_id=thread_id, text=text)
    except Exception:  # noqa: BLE001 - logging for external API errors
        logger.exception("Failed to send document start report.")


async def send_file_report(bot: Bot, doc_path: str | Path, caption: str) -> None:
    config = load_config()
    chat_id = config.get("report_chat_id")
    thread_id = config.get("files_thread_id")
    if not chat_id or not thread_id:
        logger.warning("File reports not configured. report_chat_id=%s files_thread_id=%s", chat_id, thread_id)
        return

    try:
        await bot.send_document(
            chat_id=chat_id,
            message_thread_id=thread_id,
            document=FSInputFile(str(doc_path)),
            caption=caption,
        )
    except Exception:  # noqa: BLE001 - logging for external API errors
        logger.exception("Failed to send file report.")
