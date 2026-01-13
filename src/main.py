import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

try:
    from .config import load_config
    from .handlers import router
except ImportError:  # pragma: no cover - allow running as a script
    from config import load_config
    from handlers import router


def get_bot_token() -> str:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN is not set in .env")
    return token


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    config = load_config()
    logging.getLogger(__name__).info(
        "Loaded report config: report_chat_id=%s starts_thread_id=%s files_thread_id=%s",
        config.get("report_chat_id"),
        config.get("starts_thread_id"),
        config.get("files_thread_id"),
    )
    bot = Bot(token=get_bot_token())
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
