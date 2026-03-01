import asyncio
import logging

from aiogram import Bot, Dispatcher

from bot.config import settings
from bot.handlers.start import router as start_router
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.subscription import SubscriptionMiddleware
from bot.middlewares.throttle import ThrottleMiddleware


async def main() -> None:
    logging.basicConfig(level=logging.INFO)

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Роутеры
    dp.include_router(start_router)

    # Порядок middleware: throttle → auth → subscription
    # (throttle первым, чтобы отсечь спам до запросов в БД)
    dp.update.outer_middleware(ThrottleMiddleware())
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.outer_middleware(SubscriptionMiddleware())

    logging.info("Бот запускается…")
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
