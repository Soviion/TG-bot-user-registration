import asyncpg
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def create_pool():
    return await asyncpg.create_pool(DATABASE_URL)

@asynccontextmanager
async def get_connection(pool):
    async with pool.acquire() as conn:
        yield conn

async def is_user_registered(pool, telegram_id: int) -> bool:
    async with get_connection(pool) as conn:
        result = await conn.fetchval(
            "SELECT is_verified FROM students WHERE telegram_id = $1",
            telegram_id
        )
        return bool(result)

async def register_user(pool, telegram_id: int, username: str | None, full_name: str, group_name: str, phone: str):
    async with get_connection(pool) as conn:
        await conn.execute("""
            INSERT INTO students (telegram_id, username, full_name, group_name, phone, is_verified)
            VALUES ($1, $2, $3, $4, $5, true)
            ON CONFLICT (telegram_id) DO UPDATE SET
                username = EXCLUDED.username,
                full_name = EXCLUDED.full_name,
                group_name = EXCLUDED.group_name,
                phone = EXCLUDED.phone,
                is_verified = true
        """, telegram_id, username, full_name, group_name, phone)