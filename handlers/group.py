# group.py
from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated, Message
from aiogram.filters import ChatMemberUpdatedFilter, IS_MEMBER, IS_NOT_MEMBER

from datetime import datetime, timedelta
import pytz

import db

router = Router(name="group_events")

minsk_tz = pytz.timezone("Europe/Minsk")
now_minsk = datetime.now(minsk_tz).replace(tzinfo=None)


@router.chat_member(ChatMemberUpdatedFilter(member_status_changed=(IS_NOT_MEMBER >> IS_MEMBER)))
async def on_user_join(event: ChatMemberUpdated, bot: Bot):
    user = event.new_chat_member.user
    chat_id = event.chat.id
    
    # Самое важное — создаём запись в базе, если её ещё нет
    if db.pool is None:
        await db.init_pool()  # на всякий случай, если пул не инициализирован
    
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
        parse_mode="HTML"
    )

