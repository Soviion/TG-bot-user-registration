# group.py

import os
from aiogram import F, Router, Bot
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from datetime import datetime, timedelta
import pytz


import db
from utils import log_action

router = Router(name="group_events")

minsk_tz = pytz.timezone("Europe/Minsk")
now_minsk = datetime.now(minsk_tz).replace(tzinfo=None)


keyboard = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="Перейти к боту", url="https://t.me/register_yivrbot")]
])

@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(IS_NOT_MEMBER >> IS_MEMBER)))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    user = event.new_chat_member.user
    log_action(
        "Пользователь зашёл в группу",
        user,
        handler="group_join",
        extra=f"chat_id={event.chat.id}"
    )
    chat_id = event.chat.id
   
    async with db.pool.acquire() as conn:
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

    # 1. Ограничиваем пользователя сразу
    await bot.restrict_chat_member(
        chat_id=event.chat.id,
        user_id=user.id,
        permissions={
            "can_send_messages": False,
            "can_send_media_messages": False,
            "can_send_polls": False,
            "can_send_other_messages": False,
            "can_add_web_page_previews": False,
            "can_change_info": False,
            "can_invite_users": False,
            "can_pin_messages": False,
        }
    )

    # 2. Приветственное сообщение с упоминанием
    await event.answer(
        f"👋 {user.mention_html()} добро пожаловать!\n\n"
        "Чтобы получить возможность писать в чате — пройди регистрацию в личных сообщениях у бота.\n"
        "Просто напиши ему /start",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID"))
ROOT_ID = int(os.getenv("ROOT_ID"))



import asyncio
from aiogram.types import Message, ChatPermissions


async def is_bot_admin(user_id: int) -> bool:
    if user_id == SUPER_ADMIN_ID:
        return True
    async with db.pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT TRUE FROM bot_admins WHERE telegram_id = $1",
            user_id
        ) is True

# Таймер для временного сообщения
async def send_temp_message(message: Message, text: str, delay: int = 15):
    msg = await message.answer(text)
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass


# Проверка, что команда используется только админом бота и ответом на сообщение
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

# ===================== КОМАНДЫ =====================
from aiogram.types import User

async def get_target_username(user: User | None) -> str | None:
    if user is None:
        return None

    if user.username:
        return f"@{user.username}"

    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    return name or None

# /kick
from admin_logger import log_admin_action
@router.message(F.text == "/kick")
async def cmd_kick(message: Message, bot: Bot):

    if message.chat.type not in ("group", "supergroup"):
        return

    if not await admin_only(message):
        return
    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    target = message.reply_to_message.from_user

    await bot.ban_chat_member(chat_id, user_id)
    await bot.unban_chat_member(chat_id, user_id)

    username = await get_target_username(target)
    await send_temp_message(message, f"👢 Пользователь {username} кикнут.")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{now} | INFO | /kick выполнен | {message.from_user.first_name} (@{message.from_user.username}) | target={username} | chat_id={chat_id}")

    await log_admin_action(
        admin_id=message.from_user.id,
        action="kick",
        target_id=target.id,
        target_username=await get_target_username(target),
        details=f"chat_id={message.chat.id}"
    )

# /mute24
@router.message(F.text == "/mute")
async def cmd_mute_24(message: Message, bot: Bot):

    if message.chat.type not in ("group", "supergroup"):
        return

    if not await admin_only(message):
        return
    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    until = datetime.utcnow() + timedelta(hours=24)
    await bot.restrict_chat_member(chat_id, user_id, permissions={"can_send_messages": False}, until_date=until)
    await send_temp_message(message, "🔇 Пользователь замьючен на 24 часа.")

# /pmute
@router.message(F.text == "/pmute")
async def cmd_perma_mute(message: Message, bot: Bot):

    if message.chat.type not in ("group", "supergroup"):
        return

    if not await admin_only(message):
        return
    user_id = message.reply_to_message.from_user.id
    chat_id = message.chat.id
    await bot.restrict_chat_member(chat_id, user_id, permissions={
        "can_send_messages": False,
        "can_send_media_messages": False,
        "can_send_other_messages": False,
        "can_add_web_page_previews": False,
    })
    await send_temp_message(message, "🔒 Пользователь замьючен перманентно.")

# /up @username
@router.message(F.text.startswith("/up"))
async def cmd_up(message: Message, bot: Bot):

    if message.chat.type not in ("group", "supergroup"):
        return

    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав использовать эту команду.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(message, "Использование: /up @username")
        return
    username = parts[1][1:]
    async with db.pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT telegram_id FROM users WHERE username = $1", username)
    if not user_id:
        await send_temp_message(message, f"Пользователь @{username} не найден в базе.")
        return
    perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True
    )
    await bot.restrict_chat_member(chat_id=message.chat.id, user_id=user_id, permissions=perms)
    async with db.pool.acquire() as conn:
        await conn.execute("UPDATE users SET is_verified = TRUE WHERE telegram_id = $1", user_id)
    await send_temp_message(message, f"✅ Пользователю @{username} выданы права без регистрации.")

# /addadmin @username
@router.message(F.text.startswith("/addadmin"))
async def cmd_add_admin(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        return

    if message.from_user.id != SUPER_ADMIN_ID:
        await send_temp_message(message, "⛔ Только владелец бота может добавлять админов.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(message, "Использование: /addadmin @username")
        return
    username = parts[1][1:]
    async with db.pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT telegram_id FROM users WHERE username = $1", username)
        if not user_id:
            await send_temp_message(message, f"Пользователь @{username} не найден.")
            return
        await conn.execute("INSERT INTO bot_admins (telegram_id) VALUES ($1) ON CONFLICT DO NOTHING", user_id)
    await send_temp_message(message, f"👑 Пользователь @{username} добавлен админом бота.")

# /deladmin @username
@router.message(F.text.startswith("/deladmin"))
async def cmd_del_admin(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        return

    if message.from_user.id != ROOT_ID:
        await send_temp_message(message, "⛔ Только владелец бота может удалять админов.")
        return
    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(message, "Использование: /deladmin @username")
        return
    username = parts[1][1:]
    async with db.pool.acquire() as conn:
        user_id = await conn.fetchval("SELECT telegram_id FROM users WHERE username = $1", username)
        if not user_id:
            await send_temp_message(message, f"Пользователь @{username} не найден.")
            return
        if user_id == ROOT_ID:
            await send_temp_message(message, "❌ Невозможно удалить root администратора.")
            return
        await conn.execute("DELETE FROM bot_admins WHERE telegram_id = $1", user_id)
    await send_temp_message(message, f"🗑 Пользователь @{username} удалён из админов бота.")

# /help
@router.message(F.text == "/help")
async def cmd_help(message: Message):

    if message.chat.type not in ("group", "supergroup"):
        return

    user_id = message.from_user.id
    if user_id == SUPER_ADMIN_ID:
        help_text = (
            "🛠 Команды бота (Супер админ):\n"
            "/kick — кикнуть пользователя\n"
            "/mute — замутить на 24 часа\n"
            "/pmute — перманентный мут\n"
            "/umnute — снять мут\n"
            "/up — выдать права без регистрации\n"
            "/addadmin — добавить админа бота\n"
            "/deladmin — удалить админа бота\n"
            "/reg_mode on/off - режим контроля регистрации\n"
            "/help — показать это сообщение"
        )
        await send_temp_message(message, help_text)
        return
    async with db.pool.acquire() as conn:
        is_admin = await conn.fetchval("SELECT TRUE FROM bot_admins WHERE telegram_id = $1", user_id)
    if is_admin:
        help_text = (
            "🛠 Команды бота (админ):\n"
            "/kick — кикнуть пользователя\n"
            "/mute — замутить на 24 часа\n"
            "/pmute — перманентный мут\n"
            "/umnute — снять мут\n"
            "/up — выдать права без регистрации\n"
            "/help — показать это сообщение"
        )
        await send_temp_message(message, help_text)

@router.message(F.text.startswith("/unmute"))
async def cmd_unmute(message: Message, bot: Bot):
    if message.chat.type not in ("group", "supergroup"):
        return

    # Проверка прав
    if not await is_bot_admin(message.from_user.id):
        await send_temp_message(message, "⛔ У вас нет прав использовать эту команду.")
        return

    parts = message.text.split()
    if len(parts) != 2 or not parts[1].startswith("@"):
        await send_temp_message(message, "Использование: /unmute @username")
        return

    username = parts[1][1:]  # убираем @

    async with db.pool.acquire() as conn:
        user_id = await conn.fetchval(
            "SELECT telegram_id FROM users WHERE username = $1",
            username
        )

    if not user_id:
        await send_temp_message(message, f"Пользователь @{username} не найден в базе.")
        return

    # Размьючиваем
    from aiogram.types import ChatPermissions
    perms = ChatPermissions(
        can_send_messages=True,
        can_send_media_messages=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_change_info=False,
        can_invite_users=True,
        can_pin_messages=False
    )

    await bot.restrict_chat_member(
        chat_id=message.chat.id,
        user_id=user_id,
        permissions=perms
    )

    await send_temp_message(message, f"✅ Пользователь @{username} размьючен.")