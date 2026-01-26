# admin_logger.py
import datetime
import db  # твой модуль с asyncpg pool

TABLE_NAME = "admin_action_logs"

async def log_admin_action(
    admin_id: int,
    action: str,
    admin_username: str | None = None,
    target_id: int | None = None,
    target_username: str | None = None,
    chat_id: int | None = None,
):
    """Логирование действий админов в таблицу admin_action_logs"""
    if admin_username is None:
        admin_username = ""

    if target_username is None:
        target_username = ""

    now = datetime.datetime.utcnow()

    try:
        async with db.pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {TABLE_NAME} (
                    action,
                    admin_telegram_id,
                    admin_username,
                    target_telegram_id,
                    target_username,
                    chat_id,
                    created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                action,
                admin_id,
                admin_username,
                target_id,
                target_username,
                chat_id,
                now,
            )
    except Exception as e:
        print(f"[ADMIN_LOG ERROR] {e}")