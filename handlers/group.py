# group.py
import os
import asyncio
from datetime import datetime, timedelta
import pytz

from aiogram import F, Router, Bot
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import (
    ChatMemberUpdated, Message, ChatPermissions,
    InlineKeyboardMarkup, InlineKeyboardButton
)

import db
from utils import log_action
from handlers.admin_logger import log_admin_action

router = Router(name="group_events")
SUPER_ADMIN_ID = 8350043917

# Временная зона Минск
minsk_tz = pytz.timezone("Europe/Minsk")

keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Перейти к боту", url="https://t.me/register_yivrbot")]
])

SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID"))
ROOT_ID = int(os.getenv("ROOT_ID"))

# ====================== Событие входа пользователя ======================
@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(IS_NOT_MEMBER >> IS_MEMBER)))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    user = event.new_chat_member.user
    chat_id = event.chat.id

    log_action(
        "Пользователь зашёл в группу",
        user,
        handler="group_join",
        extra=f"chat_id={chat_id}"
    )

    now_minsk = datetime.now(minsk_tz).replace(tzinfo=None)

    async with db.get_pool().acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, is_verified, group_id, scholarship, created_at)
            VALUES ($1, $2, FALSE, $3, FALSE, $4)
            ON CONFLICT (telegram_id) DO UPDATE
            SET 
                username     = EXCLUDED.username,
                is_verified  = FALSE,
                group_id     = EXCLUDED.group_id,
                full_name    = NULL,
                group_number = NULL,
                faculty      = NULL,
                mobile_number= NULL,
                stud_number  = NULL,
                form_educ    = NULL,
                scholarship  = FALSE,
                updated_at   = $4
        """, user.id, user.username, chat_id, now_minsk)

    # Ограничение прав пользователя до регистрации
    await bot.restrict_chat_member(
        chat_id=chat_id,
        user_id=user.id,
        permissions=ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
    )

    await event.answer(
        f"👋 {user.mention_html()} добро пожаловать!\n\n"
        "Чтобы получить возможность писать в чате — пройди регистрацию в личных сообщениях у бота.\n"
        "Просто напиши ему /start",
        reply_markup=keyboard,
        parse_mode="HTML"
    )


# ====================== Проверка прав админа ======================
async def is_bot_admin(user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    async with db.get_pool().acquire() as conn:
        return await conn.fetchval(
            "SELECT TRUE FROM bot_admins WHERE telegram_id = $1",
            user_id
        ) is True


async def send_temp_message(message: Message, text: str, delay: int = 15):
    msg = await message.answer(text)
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass


async def admin_only(message: Message) -> bool:
    if message.chat.type not in ("group", "supergroup"):
        return False
    if not message.reply_to_message:
        await send_temp_message(message, "Команду нужно использовать ответом на сообщение пользователя.")
        return False
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав для использования этой команды.")
        return False
    return True


# ====================== Утилита ======================
async def get_target_username(user) -> str:
    if user.username:
        return f"@{user.username}"
    return f"{user.first_name or ''} {user.last_name or ''}".strip() or str(user.id)


# ====================== Команды админа ======================
@router.message(F.text.startswith("/kick"))
async def cmd_kick(message: Message, bot: Bot):
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав")
        return
    user = message.from_user
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    try:
        await bot.ban_chat_member(message.chat.id, target_id)
        await bot.unban_chat_member(message.chat.id, target_id)
        await log_admin_action("/kick", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
        await send_temp_message(message, f"👢 @{target_username} кикнут")
    except Exception as e:
        print("Kick error:", e)
        await send_temp_message(message, f"❌ Не удалось кикнуть @{target_username}")
    log_action("Использована команда /kick", user)


@router.message(F.text.startswith("/mute"))
async def cmd_mute(message: Message, bot: Bot):
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав для использования этой команды")
        return

    target = await get_target_by_username(message)
    if not target:
        return

    target_id, target_username = target
    until = datetime.utcnow() + timedelta(hours=24)
    permissions = ChatPermissions(can_send_messages=False)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=permissions, until_date=until)
        await log_admin_action("/mute", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
        await send_temp_message(message, f"🔇 @{target_username} замучен на 24 часа")
    except Exception as e:
        print("Mute error:", e)
        await send_temp_message(message, f"❌ Не удалось замутить @{target_username}")
    user = message.from_user
    log_action("Использована команда /mute", user)


@router.message(F.text.startswith("/pmute"))
async def cmd_pmute(message: Message, bot: Bot):
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав")
        return
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    permissions = ChatPermissions(can_send_messages=False)
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=permissions)
        await log_admin_action("/pmute", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
        await send_temp_message(message, f"🔇 @{target_username} замучен навсегда")
    except Exception as e:
        print("Pmute error:", e)
        await send_temp_message(message, f"❌ Не удалось замутить @{target_username}")
    user = message.from_user
    log_action("Использована команда /pmute", user)

@router.message(F.text.startswith("/unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав")
        return
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
        can_pin_messages=False
    )
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=permissions)
        await log_admin_action("/unmute", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
        await send_temp_message(message, f"🔊 @{target_username} размучен")
    except Exception as e:
        print("Unmute error:", e)
        await send_temp_message(message, f"❌ Не удалось размучить @{target_username}")
    user = message.from_user
    log_action("Использована команда /unmute", user)


# ====================== /up @username ======================
@router.message(F.text.startswith("/up"))
async def cmd_up(message: Message, bot: Bot):
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав")
        return
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_verified = TRUE, verified_at = NOW() WHERE telegram_id = $1", target_id)
    permissions = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True
    )
    try:
        await bot.restrict_chat_member(message.chat.id, target_id, permissions=permissions)
    except: pass
    await log_admin_action("/up", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
    await send_temp_message(message, f"✅ @{target_username} получил права")
    user = message.from_user
    log_action("Использована команда /up", user)


# ====================== /addadmin @username  ======================
@router.message(F.text.startswith("/addadmin"))
async def cmd_addadmin(message: Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await send_temp_message(message, "⛔ Только супер-админ")
        return
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    async with db.get_pool().acquire() as conn:
        await conn.execute("INSERT INTO bot_admins (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", target_id)
    await log_admin_action("/addadmin", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
    await send_temp_message(message, f"✅ @{target_username} добавлен в админы бота")
    user = message.from_user
    log_action("Использована команда /addadmin", user)

# ====================== /deladmin @username  ======================
@router.message(F.text.startswith("/deladmin"))
async def cmd_deladmin(message: Message):
    if message.from_user.id != SUPER_ADMIN_ID:
        await send_temp_message(message, "⛔ Только супер-админ")
        return
    target = await get_target_by_username(message)
    if not target: return
    target_id, target_username = target
    async with db.get_pool().acquire() as conn:
        await conn.execute("DELETE FROM bot_admins WHERE telegram_id = $1", target_id)
    await log_admin_action("/deladmin", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
    await send_temp_message(message, f"🗑 @{target_username} удалён из админов бота")
    user = message.from_user
    log_action("Использована команда /deladmin", user)

# ====================== /help  ======================
@router.message(F.text == "/help")
async def cmd_help(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        return

    user_id = message.from_user.id

    # Супер-админ
    if user_id == SUPER_ADMIN_ID:
        help_text = (
            "🛠 Команды бота (Супер админ):\n"
            "/kick — кикнуть пользователя\n"
            "/mute — замутить на 24 часа\n"
            "/pmute — перманентный мут\n"
            "/unmute — снять мут\n"
            "/up — выдать права без регистрации\n"
            "/addadmin — добавить админа бота\n"
            "/deladmin — удалить админа бота\n"
            "/help — показать это сообщение"
        )
        await send_temp_message(message, help_text)
        return

    # Админ бота
    async with db.get_pool().acquire() as conn:
        is_admin = await conn.fetchval(
            "SELECT TRUE FROM bot_admins WHERE telegram_id = $1",
            user_id
        )

    if is_admin:
        help_text = (
            "🛠 Команды бота (админ):\n"
            "/kick — кикнуть пользователя\n"
            "/mute — замутить на 24 часа\n"
            "/pmute — перманентный мут\n"
            "/unmute — снять мут\n"
            "/up — выдать права без регистрации\n"
            "/help — показать это сообщение"
        )
        await send_temp_message(message, help_text)
    user = message.from_user
    log_action("Использована команда /help", user)

async def get_target_by_username(message: Message):
    """
    Получаем цель команды через @username в сообщении.
    Возвращает (telegram_id, username) или None.
    """
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(message, "Использование: /команда @username")
        return None

    username = parts[1][1:]  # убираем @
    async with db.get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT telegram_id, username FROM users WHERE username = $1",
            username
        )

    if not row:
        await send_temp_message(message, f"Пользователь @{username} не найден в базе")
        return None

    return row["telegram_id"], row["username"]


async def get_target(message: Message):
    """
    Возвращает (telegram_id, username) цели.
    username может быть None.
    Поддержка:
    - reply на сообщение
    - /command @username
    """
    # Через reply
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        username = u.username or f"{u.first_name} {u.last_name or ''}".strip()
        return u.id, username

    # Через аргумент
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(
            message,
            "Использование команды:\n"
            "— ответом на сообщение пользователя\n"
            "— или: /команда @username"
        )
        return None

    username = parts[1][1:]  # убираем @
    async with db.get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT telegram_id, username FROM users WHERE username = $1",
            username
        )

    if not row:
        await send_temp_message(message, f"Пользователь @{username} не найден в базе")
        return None

    return row["telegram_id"], row["username"] or username  # если в базе нет username, используем введённый


async def get_user_by_username(username: str):
    async with db.get_pool().acquire() as conn:
        return await conn.fetchrow(
            "SELECT telegram_id, username FROM users WHERE username = $1",
            username
        )

async def get_target_username_only(message: Message):
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await message.answer("Использование: /команда @username")
        return None
    username = parts[1][1:]
    user = await db.pool.fetchrow("SELECT telegram_id, username FROM users WHERE username = $1", username)
    if not user:
        await message.answer(f"Пользователь @{username} не найден в базе")
        return None
    return user["telegram_id"], user["username"]

async def log_admin_action(action, admin_id, admin_username, target_id=None, target_username=None, chat_id=None):
    async with db.pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO admin_action_logs
            (action, admin_telegram_id, admin_username, target_telegram_id, target_username, chat_id, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """,
            action, admin_id, admin_username, target_id, target_username, chat_id
        )

async def get_target_reply_or_username(message: Message):
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        return u.id, u.username

    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await message.answer(
            "Использование:\n— ответом на сообщение\n— или: /команда @username"
        )
        return None

    username = parts[1][1:]
    user = await db.pool.fetchrow("SELECT telegram_id, username FROM users WHERE username = $1", username)
    if not user:
        await message.answer(f"Пользователь @{username} не найден в базе")
        return None
    return user["telegram_id"], user["username"]

async def get_target_user(message: Message):
    """
    Возвращает (telegram_id, username) или None
    Поддержка:
    - ответом
    - /cmd @username
    """
    # 1️⃣ Через reply
    if message.reply_to_message:
        u = message.reply_to_message.from_user
        return u.id, u.username

    # 2️⃣ Через аргумент
    parts = message.text.strip().split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(
            message,
            "Использование команды:\n"
            "— ответом на сообщение пользователя\n"
            "— или: /команда @username"
        )
        return None

    username = parts[1][1:]

    async with db.get_pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT telegram_id, username FROM users WHERE username = $1",
            username
        )

    if not row:
        await send_temp_message(message, f"Пользователь @{username} не найден в базе")
        return None

    return row["telegram_id"], row["username"]


# ====================== /addadmin @username  ======================
@router.message(F.text.startswith("/addadmin"))
async def cmd_addadmin(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    # Только супер-админ
    if message.from_user.id != SUPER_ADMIN_ID:
        await send_temp_message(message, "⛔ Только супер-админ может добавлять админов")
        return

    target = await get_target_user(message)
    if not target:
        return
    target_id, target_username = target

    async with db.get_pool().acquire() as conn:
        await conn.execute(
            "INSERT INTO bot_admins (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING",
            target_id
        )

    await log_admin_action("/addadmin", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
    await send_temp_message(message, f"✅ @{target_username} добавлен в админы бота")


# ====================== /deladmin @username  ======================
@router.message(F.text.startswith("/deladmin"))
async def cmd_deladmin(message: Message):
    if message.chat.type not in ("group", "supergroup"):
        return

    # Только супер-админ
    if message.from_user.id != SUPER_ADMIN_ID:
        await send_temp_message(message, "⛔ Только супер-админ может удалять админов")
        return

    target = await get_target_user(message)
    if not target:
        return
    target_id, target_username = target

    async with db.get_pool().acquire() as conn:
        await conn.execute(
            "DELETE FROM bot_admins WHERE telegram_id = $1",
            target_id
        )

    await log_admin_action("/deladmin", message.from_user.id, message.from_user.username, target_id, target_username, message.chat.id)
    await send_temp_message(message, f"🗑 @{target_username} удалён из админов бота")