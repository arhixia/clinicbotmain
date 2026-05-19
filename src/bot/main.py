import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis
from src.settings.config import BOT_TOKEN, REDIS_URL
from src.bot.routers import help,callback_request,certificate


logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    )

    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=redis)

    
    bot_token = BOT_TOKEN
    if not bot_token:
        raise ValueError("BOT_TOKEN не задан в переменных окружения")

    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher(storage=storage)

    dp.include_router(help.router)
    dp.include_router(callback_request.router)
    dp.include_router(certificate.router)

    logger.info("Бот запускается...")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.error(f"Ошибка в работе бота: {e}")
    finally:
        await bot.session.close()
        await redis.close()



if __name__ == "__main__":
    asyncio.run(main())