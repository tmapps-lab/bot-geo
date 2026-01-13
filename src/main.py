import asyncio
import os

from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

try:
    from .handlers import router
except ImportError:  # pragma: no cover - allow running as a script
    from handlers import router


def get_bot_token() -> str:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN is not set in .env")
    return token


async def main() -> None:
    bot = Bot(token=get_bot_token())
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
