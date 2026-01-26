# db.py
import asyncpg
from typing import Any, List, Optional

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

async def execute(query: str, *args) -> str:
    """
    Выполняет SQL-запрос, ничего не возвращая кроме статуса.
    """
    if not pool:
        raise RuntimeError("Pool not initialized. Call init_pool() first.")
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)


# Функция fetchval — для одного значения
async def fetchval(query: str, *args) -> Any:
    if not pool:
        raise RuntimeError("Pool not initialized. Call init_pool() first.")
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)

# Функция fetchrow — для одной строки
async def fetchrow(query: str, *args) -> Optional[asyncpg.Record]:
    if not pool:
        raise RuntimeError("Pool not initialized. Call init_pool() first.")
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

# Функция fetch — для нескольких строк
async def fetch(query: str, *args) -> List[asyncpg.Record]:
    if not pool:
        raise RuntimeError("Pool not initialized. Call init_pool() first.")
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)
    

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
    
async def try_complete_verification(telegram_id: int) -> bool:
    async with pool.acquire() as conn:
        result = await conn.fetchval(
            "SELECT try_verify_user($1)",
            telegram_id
        )
        return bool(result)
    

