# reg_mode.py
from aiogram import Router, F, Bot
from aiogram.types import Message, ChatPermissions
from utils import log_action
import db
import config
from handlers.admin_logger import log_admin_action

router = Router(name="reg_mode")

# 🔴 глобальный флаг
REG_MODE_ENABLED = False

def is_super_admin(user_id: int) -> bool:
    return user_id == config.SUPER_ADMIN_ID

# =====================
# /reg_mode on|off
# =====================
@router.message(F.text.startswith("/reg_mode"))
async def cmd_reg_mode(message: Message):
    global REG_MODE_ENABLED

    if message.chat.type not in ("group", "supergroup"):
        return
    if not is_super_admin(message.from_user.id):
        await message.answer("⛔ Только супер админ может изменять режим регистрации")
        return

    parts = message.text.split()
    if len(parts) != 2 or parts[1] not in ("on", "off"):
        await message.answer("Использование: /reg_mode on|off")
        return

    REG_MODE_ENABLED = parts[1] == "on"

    log_action(
        action="REG_MODE переключён",
        user=message.from_user,
        handler="reg_mode",
        extra=f"state={REG_MODE_ENABLED}"
    )

    await message.answer(
        f"🛡 Режим регистрации: {'ВКЛЮЧЕН' if REG_MODE_ENABLED else 'ВЫКЛЮЧЕН'}"
    )

    await log_admin_action(
        admin_id=message.from_user.id,
        admin_username=message.from_user.username,
        action=f"reg_mode_change: mode={'ON' if REG_MODE_ENABLED else 'OFF'}",
        chat_id=message.chat.id
    )

# =====================
# ЛОВУШКА СООБЩЕНИЙ — мут + запись/обновление group_id
# =====================
@router.message(F.chat.type.in_(["group", "supergroup"]))
async def reg_mode_guard(message: Message, bot: Bot):
    if not REG_MODE_ENABLED:
        return

    if message.from_user.is_bot:
        return

    user = message.from_user
    user_id = user.id
    chat_id = message.chat.id

    # Супер-админ и верифицированные — пропускаем
    if is_super_admin(user_id):
        return
    if await db.is_user_verified(user_id):
        return

    log_action(
        action="REG_MODE: попытка писать без верификации",
        user=user,
        handler="reg_mode_guard",
        extra=f"chat_id={chat_id}"
    )

    # 1. Удаляем сообщение
    try:
        await message.delete()
    except Exception as e:
        log_action("REG_MODE: ошибка удаления сообщения", user, str(e), level="WARNING")

    # 2. Мут + создание/обновление записи в БД
    try:
        await bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=ChatPermissions(can_send_messages=False)
        )

        # Записываем или обновляем запись в users
        async with db.pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (
                    telegram_id, 
                    username, 
                    is_verified, 
                    group_id, 
                    created_at, 
                    updated_at
                )
                VALUES ($1, $2, FALSE, $3, NOW(), NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    group_id = EXCLUDED.group_id,
                    updated_at = NOW()
            """, user_id, user.username or None, chat_id)

        log_action(
            action="REG_MODE: пользователь замучен + запись/обновление group_id",
            user=user,
            handler="reg_mode_guard",
            extra=f"chat_id={chat_id}, user_id={user_id}"
        )

    except Exception as e:
        log_action(
            action="REG_MODE: ошибка мута или записи в БД",
            user=user,
            handler="reg_mode_guard",
            extra=str(e),
            level="ERROR"
        )

    # 3. Сообщение пользователю
    mention = f"@{user.username}" if user.username else user.full_name
    try:
        await bot.send_message(
            chat_id,
            f"⛔ {mention}, чтобы писать в группе — пройди регистрацию:\n👉 @{config.BOT_USERNAME}"
        )
    except Exception as e:
        log_action("REG_MODE: ошибка отправки сообщения", user, str(e), level="WARNING")