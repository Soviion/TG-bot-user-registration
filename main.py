import asyncio
import logging
import sys
import os


project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import config
import db
from handlers import group
from handlers import registration
from handlers import reg_mode

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("main")


async def main():
    bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем роутеры
    dp.include_router(group.router)
    dp.include_router(registration.router)
    dp.include_router(reg_mode.router)

    try:
        # Инициализация пула БД
        await db.init_pool()
        logger.info("✅ Подключение к базе данных успешно")
        logging.getLogger("aiogram").setLevel(logging.WARNING)

        logger.info("🚀 Бот запускается...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки (Ctrl+C)")

    except Exception as e:
        logger.exception("❌ Неожиданная ошибка при запуске бота")

    finally:
        logger.info("Завершение работы...")
        await db.close_pool()
        await bot.session.close()
        logger.info("Бот остановлен полностью")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
