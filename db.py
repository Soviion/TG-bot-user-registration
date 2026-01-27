import asyncpg
from typing import Any, List, Optional
import config
import logging

logger = logging.getLogger("db")

pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global pool
    if pool:
        return
    try:
        pool = await asyncpg.create_pool(
            user=config.SUPABASE["user"],
            password=config.SUPABASE["password"],
            database=config.SUPABASE["database"],
            host=config.SUPABASE["host"],
            port=config.SUPABASE["port"],
            ssl="require",
            min_size=5,
            max_size=20,
            timeout=15,
            command_timeout=10,  # если запрос >10 сек — ошибка вместо зависания
            server_settings={'statement_timeout': '10000'},  # 10 сек на стороне Postgres
        )
        logger.info("✅ Пул подключений к базе создан")
    except Exception as e:
        logger.exception("❌ Ошибка подключения к базе")
        raise e


async def close_pool():
    global pool
    if pool:
        await pool.close()
        pool = None
        logger.info("Пул базы данных закрыт")


async def execute(query: str, *args) -> str:
    if not pool:
        raise RuntimeError("Pool не инициализирован. Вызовите init_pool()")
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetchval(query: str, *args) -> Any:
    if not pool:
        raise RuntimeError("Pool не инициализирован")
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def fetchrow(query: str, *args) -> Optional[asyncpg.Record]:
    if not pool:
        raise RuntimeError("Pool не инициализирован")
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetch(query: str, *args) -> List[asyncpg.Record]:
    if not pool:
        raise RuntimeError("Pool не инициализирован")
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def is_user_verified(user_id: int) -> bool:
    try:
        val = await fetchval("SELECT is_verified FROM users WHERE telegram_id = $1", user_id)
        return bool(val)
    except Exception as e:
        logger.error(f"Ошибка проверки верификации пользователя {user_id}: {e}")
        return False


async def try_complete_verification(telegram_id: int) -> bool:
    try:
        val = await fetchval("SELECT try_verify_user($1)", telegram_id)
        return bool(val)
    except Exception as e:
        logger.error(f"Ошибка завершения верификации {telegram_id}: {e}")
        return False


def get_pool():
    if not pool:
        raise RuntimeError("Pool не инициализирован")
    return pool
