import asyncpg
from typing import Optional

import config

pool: Optional[asyncpg.Pool] = None


async def init_pool():
    global pool
    pool = await asyncpg.create_pool(
        user     = config.SUPABASE["user"],
        password = config.SUPABASE["password"],
        database = config.SUPABASE["database"],
        host     = config.SUPABASE["host"],
        port     = config.SUPABASE["port"],
        ssl      = "require",                        # обязательно для Supabase
        min_size = 1,
        max_size = 10,
    )



async def close_pool():
    if pool:
        await pool.close()


async def is_user_verified(user_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            """
            SELECT is_verified 
            FROM users 
            WHERE telegram_id = $1
            """,
            user_id
        )
        return bool(result)
    
async def try_complete_verification(pool, telegram_id: int) -> bool:
    """
    Пытается завершить верификацию пользователя.
    Возвращает True, если все обязательные поля заполнены и пользователь был успешно верифицирован.
    """
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT try_verify_user($1)",
            telegram_id
        )
        return bool(result)