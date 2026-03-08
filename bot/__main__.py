import asyncio

from aiogram import Bot, Dispatcher
from aiogram.types import ErrorEvent

from bot.config import settings
from bot.handlers.build import router as build_router
from bot.handlers.draft import router as draft_router
from bot.handlers.help import router as help_router
from bot.handlers.match import router as match_router
from bot.handlers.menu import router as menu_router
from bot.handlers.meta import router as meta_router
from bot.handlers.profile import router as profile_router
from bot.handlers.settings import router as settings_router
from bot.handlers.start import router as start_router
from bot.handlers.subscription import router as subscription_router
from bot.middlewares.auth import AuthMiddleware
from bot.middlewares.subscription import SubscriptionMiddleware
from bot.middlewares.throttle import ThrottleMiddleware
from core.error_messages import classify_api_error
from core.logging import get_logger, setup_logging
from scheduler.setup import create_scheduler

logger = get_logger(__name__)

_GLOBAL_ERROR_TEXT = "Произошла непредвиденная ошибка. Попробуй позже."


async def main() -> None:
    setup_logging()

    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher()

    # Роутеры
    dp.include_router(start_router)
    dp.include_router(meta_router)
    dp.include_router(build_router)
    dp.include_router(draft_router)
    dp.include_router(match_router)
    dp.include_router(profile_router)
    dp.include_router(settings_router)
    dp.include_router(subscription_router)
    dp.include_router(help_router)
    dp.include_router(menu_router)

    # Порядок middleware: throttle → auth → subscription
    # (throttle первым, чтобы отсечь спам до запросов в БД)
    dp.update.outer_middleware(ThrottleMiddleware())
    dp.update.outer_middleware(AuthMiddleware())
    dp.update.outer_middleware(SubscriptionMiddleware())

    # Глобальный обработчик ошибок — пользователь всегда получает сообщение
    @dp.error()
    async def global_error_handler(event: ErrorEvent) -> bool:
        logger.exception(
            "Необработанное исключение в update",
            exc_info=event.exception,
        )
        # Пытаемся отправить сообщение пользователю
        update = event.update
        user_message = classify_api_error(event.exception)
        try:
            if update.message:
                await update.message.answer(user_message)
            elif update.callback_query and update.callback_query.message:
                await update.callback_query.answer(
                    user_message or _GLOBAL_ERROR_TEXT,
                    show_alert=True,
                )
        except Exception:
            logger.warning("Не удалось отправить сообщение об ошибке пользователю")
        return True

    # Планировщик задач
    scheduler = create_scheduler(bot)
    scheduler.start()

    logger.info("Бот запускается…")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
