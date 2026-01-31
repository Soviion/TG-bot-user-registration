# registration.py
import re
import hmac
import hashlib
import sys
import os

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ChatPermissions
)
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# добавляем родительскую папку для импорта db и utils
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import config
import db
from utils import get_user_info, log_action, log_fsm

router = Router(name="registration")

# ================= FSM =================
class Registration(StatesGroup):
    full_name = State()
    group_number = State()
    faculty = State()
    mobile_number = State()
    stud_number = State()
    form_educ = State()
    scholarship = State()
    confirm = State()

class EditRegistration(StatesGroup):
    menu = State()
    editing = State()

FACULTIES = {
    "ФКСиС": "FKSiS",
    "ФИТУ": "FITU",
    "ФКП": "FKP",
    "ФИБ": "FIB",
    "ИЭФ": "IEF",
    "ФРЭ": "FRE",
}
FACULTY_REVERSE = {v: k for k, v in FACULTIES.items()}

faculty_kb = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="ФКСиС"),
            KeyboardButton(text="ФИТУ"),
            KeyboardButton(text="ФКП"),
        ],
        [
            KeyboardButton(text="ФИБ"),
            KeyboardButton(text="ИЭФ"),
            KeyboardButton(text="ФРЭ"),
        ],
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

ALLOWED_EDIT_FIELDS = {
    "full_name", "group_number", "faculty", "mobile_number",
    "stud_number", "form_educ", "scholarship"
}

# ================= HMAC подписи =================
def sign_data(data: str) -> str:
    h = hmac.new(config.CALLBACK_SECRET.encode(), data.encode(), hashlib.sha256)
    return h.hexdigest()[:20]

def is_valid_signature(payload: str, signature: str) -> bool:
    return hmac.compare_digest(sign_data(payload), signature)

def make_signed_callback(payload: str) -> str:
    return f"{payload}:{sign_data(payload)}"

# ================= Вспомогательная функция размутывания =================
async def _try_unmute_user(bot: Bot, user_id: int, group_id: int | None, user_for_log) -> str:
    if not group_id:
        return "group_id не найден в базе — права не изменялись"

    try:
        member = await bot.get_chat_member(chat_id=group_id, user_id=user_id)
        
        if member.status in ("owner", "administrator", "creator"):
            return "Вы администратор/владелец — права менять не требуется"
        
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_polls=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_invite_users=True,
            can_pin_messages=False
        )
        await bot.restrict_chat_member(
            chat_id=group_id,
            user_id=user_id,
            permissions=permissions
        )
        return "Права в группе восстановлены ✅"
        
    except Exception as e:
        log_action("Ошибка размутывания", user_for_log, str(e), "ERROR")
        return f"Не удалось снять ограничения: {str(e)}\nОбратитесь к админу группы"

# ================= /start =================
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return

    user = message.from_user
    chat_type = message.chat.type
    chat_id = message.chat.id if chat_type in ("group", "supergroup") else None

    log_action(
        action="Пользователь запустил /start",
        user=user,
        handler="cmd_start",
        extra=f"chat_type={chat_type}, chat_id={chat_id}"
    )

    await log_fsm(state, user, None, "start command")
    await state.clear()

    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, is_verified)
            VALUES ($1, $2, FALSE)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username
        """, user.id, user.username)

    verified = await db.is_user_verified(user.id)

    log_action(
        action="Проверен статус верификации после /start",
        user=user,
        handler="cmd_start",
        extra=f"verified={verified}"
    )

    status_emoji = "✅" if verified else "⏳"
    status_text = "зарегистрирован" if verified else "ещё не зарегистрирован"

    text = (
        f"Привет, {user.first_name or '@'+(user.username or 'пользователь')}! 👋\n\n"
        "Этот бот создан для регистрации участников группы УИВР.\n\n"
        "❗️Данные будут использоваться для формирования документов и премий. "
        "Пожалуйста, вводите корректные данные.\n\n"
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Статус в базе: {status_emoji} {status_text}\n\n"
    )

    keyboard_buttons = [
        [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
    ]
    if not verified:
        text += "Чтобы писать в группе — пройди регистрацию /reg или нажми кнопку ниже."
        keyboard_buttons.append([KeyboardButton(text="Начать регистрацию")])

    keyboard = ReplyKeyboardMarkup(keyboard=keyboard_buttons, resize_keyboard=True)

    await message.answer(text=text, reply_markup=keyboard)
    log_action("Отправлено приветствие на /start", user)

# ================= /reg =================
@router.message(F.text.in_(("/reg", "Начать регистрацию")))
async def start_registration(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return

    user_id = message.from_user.id
    user = message.from_user

    log_action("Нажата кнопка /reg или Начать регистрацию", user, handler="start_registration")

    verified = await db.is_user_verified(user_id)

    if verified:
        await message.answer("Вы уже зарегистрированы и можете писать в группе.")
        log_action("Попытка повторной регистрации (уже verified)", user)
        return

    await state.clear()
    await state.set_state(Registration.full_name)
    await message.answer("Начнём регистрацию!\n\nВведи своё ФИО полностью:")
    

# ──────────────────────────────────────────────────────────────
# Обработчики шагов регистрации (без изменений)
# ──────────────────────────────────────────────────────────────

@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    text = message.text.strip()
    words = text.split()

    # Проверка: минимум 3 слова
    if len(words) < 3:
        return await message.answer("ФИО должно содержать минимум 3 слова (Фамилия Имя Отчество).")

    # Проверка: каждое слово минимум 3 символа (игнорируя дефисы и точки)
    invalid_words = [word for word in words if len(word.replace('-', '').replace('.', '')) < 3]
    if invalid_words:
        return await message.answer(
            f"Некорректный ввод ФИО: {', '.join(invalid_words)}"
        )

    await state.update_data(full_name=text)
    await state.set_state(Registration.group_number)
    await message.answer("Введите номер группы (6 цифр):")

@router.message(Registration.group_number)
async def process_group_number(message: Message, state: FSMContext):
    text = message.text.strip()
    if not re.fullmatch(r"\d{6}", text):
        return await message.answer("Номер группы должен быть 6 цифр.")
    await state.update_data(group_number=text)
    await state.set_state(Registration.faculty)
    await message.answer("Выберите факультет:", reply_markup=faculty_kb)

@router.message(Registration.faculty)
async def process_faculty(message: Message, state: FSMContext):
    text = message.text.strip()
    if text not in FACULTIES:
        return await message.answer("Выберите факультет с кнопок")
    await state.update_data(faculty=FACULTIES[text])
    await state.set_state(Registration.mobile_number)
    await message.answer("Введите номер телефона (+375XXXXXXXXX):")

@router.message(Registration.mobile_number)
async def process_mobile(message: Message, state: FSMContext):
    text = message.text.replace(" ", "").replace("-", "")
    if not re.fullmatch(r"\+375\d{9}", text):
        return await message.answer("Телефон должен быть в формате +375XXXXXXXXX")
    await state.update_data(mobile_number=text)
    await state.set_state(Registration.stud_number)
    await message.answer("Введите номер студенческого (8 цифр):")

@router.message(Registration.stud_number)
async def process_stud_number(message: Message, state: FSMContext):
    text = message.text.strip()
    if not re.fullmatch(r"\d{8}", text):
        return await message.answer("Студенческий билет — 8 цифр")
    await state.update_data(stud_number=text)
    await state.set_state(Registration.form_educ)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Бюджет"), KeyboardButton(text="Платное")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Выберите форму обучения:", reply_markup=kb)

@router.message(Registration.form_educ)
async def process_form_educ(message: Message, state: FSMContext):
    text = message.text.lower()
    if text not in ("бюджет", "платное"):
        return await message.answer("Бюджет или Платное")
    await state.update_data(form_educ=text)
    await state.set_state(Registration.scholarship)
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Получаете стипендию? (Да/Нет)", reply_markup=kb)

@router.message(Registration.scholarship)
async def process_scholarship(message: Message, state: FSMContext, bot: Bot):
    text = message.text.lower()
    if text not in ("да", "нет"):
        return await message.answer("Да или Нет")
    await state.update_data(scholarship=(text == "да"))

    data = await state.get_data()
    user = message.from_user
    user_id = user.id

    try:
        async with db.pool.acquire() as conn:
            # Сохраняем данные, НЕ ТРОГАЕМ is_verified и group_id
            await conn.execute("""
                INSERT INTO users (
                    telegram_id, username, full_name, group_number, faculty,
                    mobile_number, stud_number, form_educ, scholarship,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    group_number = EXCLUDED.group_number,
                    faculty = EXCLUDED.faculty,
                    mobile_number = EXCLUDED.mobile_number,
                    stud_number = EXCLUDED.stud_number,
                    form_educ = EXCLUDED.form_educ,
                    scholarship = EXCLUDED.scholarship,
                    updated_at = NOW()
            """, 
                user_id,
                user.username or None,
                data.get("full_name"),
                data.get("group_number"),
                data.get("faculty"),
                data.get("mobile_number"),
                data.get("stud_number"),
                data.get("form_educ"),
                data.get("scholarship")
            )

            # Явно ставим is_verified = TRUE
            await conn.execute("""
                UPDATE users
                SET is_verified = TRUE,
                    updated_at = NOW()
                WHERE telegram_id = $1
            """, user_id)

            # Получаем group_id
            group_id = await conn.fetchval("SELECT group_id FROM users WHERE telegram_id = $1", user_id)

        log_action("Регистрация завершена успешно, is_verified = TRUE", user, handler="process_scholarship")

        # Размут ТОЛЬКО если group_id существует
        if group_id:
            unmute_text = await _try_unmute_user(bot, user_id, group_id, user)
        else:
            unmute_text = "group_id не найден — размут не выполнен (пользователь не был замучен в группе)"

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
            ],
            resize_keyboard=True
        )

        await message.answer(f"Регистрация завершена ✅\n{unmute_text}", reply_markup=keyboard)
        await state.clear()

        # Финальная проверка
        verified = await db.is_user_verified(user_id)
        log_action("Финальная проверка после регистрации", user, extra=f"verified={verified}, group_id={group_id}")

    except Exception as e:
        log_action("Ошибка в process_scholarship", user, str(e), level="ERROR")
        await message.answer("Ошибка при сохранении. Попробуйте заново (/start)")

# ================= Статус =================
@router.message(F.text == "Статус")
async def show_status(message: Message):
    if message.chat.type != "private":
        return
    
    user = message.from_user
    user_id = user.id

    # Всегда свежий запрос
    verified = await db.is_user_verified(user_id)

    text = (
        f"Telegram ID: <code>{user.id}</code>\n"
        f"Username: @{user.username or 'None'}\n"
        f"Статус: {'✅ зарегистрирован' if verified else '⏳ ещё не зарегистрирован -> /reg'}"
    )
    await message.answer(text)
    

# ================= Обновить данные =================
@router.message(F.text.in_(("Обновить данные", "/update")))
async def update_data(message: Message, state: FSMContext):
    if message.chat.type != "private":
        return
    
    user = message.from_user
    user_id = message.from_user.id

    log_action("Нажата кнопка - обновить данные", user, handler="update_data")

    # Свежая проверка верификации
    verified = await db.is_user_verified(user_id)
    if not verified:
        await message.answer("Вы ещё не зарегистрированы. /reg чтобы начать")
        return

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT full_name, group_number, faculty, mobile_number,
                   stud_number, form_educ, scholarship
            FROM users WHERE telegram_id=$1
        """, user_id)

    if not row:
        await message.answer("Данные не найдены, начнём регистрацию заново.")
        await state.clear()
        await state.set_state(Registration.full_name)
        await message.answer("Введи ФИО полностью:")
        return

    await state.update_data(**row)
    await show_edit_menu(message, state)
    log_action("Нажата кнопка - обновить данные", user)

# ================= Показ меню редактирования =================
async def show_edit_menu(message_or_query, state: FSMContext):
    data = await state.get_data()
    fields = [
        ("full_name", "ФИО"),
        ("group_number", "Группа"),
        ("faculty", "Факультет"),
        ("mobile_number", "Телефон"),
        ("stud_number", "Студ. билет"),
        ("form_educ", "Форма обучения"),
        ("scholarship", "Стипендия")
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for key, label in fields:
        value = data.get(key, "—")
        if key == "faculty":
            value = FACULTY_REVERSE.get(value, "—")
        if key == "scholarship":
            value = "Да" if value else "Нет"
        keyboard.inline_keyboard.append([InlineKeyboardButton(
            text=f"{label}: {value}",
            callback_data=make_signed_callback(f"edit_field_{key}")
        )])
    keyboard.inline_keyboard.append([InlineKeyboardButton(
        text="Всё верно ✓",
        callback_data=make_signed_callback("confirm_registration")
    )])

    text = "Что нужно изменить?" if isinstance(message_or_query, Message) else "Выберите поле для изменения:"
    await message_or_query.answer(text, reply_markup=keyboard)
    await state.set_state(EditRegistration.menu)

# ================= Обработка callback =================
@router.callback_query()
async def secure_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = callback.from_user
    if ':' not in callback.data:
        await callback.answer("Неверный запрос", show_alert=True)
        return
    payload, signature = callback.data.rsplit(':', 1)
    if not is_valid_signature(payload, signature):
        await callback.answer("Подпись не совпадает!", show_alert=True)
        return

    if payload == "confirm_registration":
        await process_confirm_registration(callback, state, bot)
    elif payload.startswith("edit_field_"):
        await process_edit_field(callback, state)
    else:
        await callback.answer("Неизвестная команда", show_alert=True)

# ================= Редактирование поля =================
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(':', 1)[0].replace("edit_field_", "")
    await state.update_data(editing_field=field)
    prompts = {
        "full_name": "Введи ФИО полностью:",
        "group_number": "Введите номер группы (6 цифр):",
        "faculty": "Выбери факультет:",
        "mobile_number": "Введите номер телефона (+375XXXXXXXXX):",
        "stud_number": "Введите номер студенческого (8 цифр):",
        "form_educ": "Выберите форму обучения:",
        "scholarship": "Получаете стипендию? (Да/Нет)"
    }
    kb = None
    if field == "faculty":
        kb = faculty_kb
    elif field == "form_educ":
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Бюджет"), KeyboardButton(text="Платное")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    elif field == "scholarship":
        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Да"), KeyboardButton(text="Нет")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    await state.set_state(EditRegistration.editing)
    await callback.message.answer(prompts[field], reply_markup=kb)
    await callback.answer()

# ================= Обработка редактирования (ввод нового значения) =================
@router.message(EditRegistration.editing)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("editing_field")
    if not field:
        await message.answer("Ошибка. Попробуйте /update")
        await show_edit_menu(message, state)
        return

    value = message.text.strip()
    if field == "full_name" and len(value.split()) < 3:
        return await message.answer("ФИО полностью (3 слова)")
    if field == "group_number" and not re.fullmatch(r"\d{6}", value):
        return await message.answer("Группа — 6 цифр")
    if field == "faculty" and value not in FACULTIES:
        return await message.answer("Выберите факультет с кнопок")
    if field == "mobile_number":
        cleaned = value.replace(" ", "").replace("-", "")
        if not re.fullmatch(r"\+375\d{9}", cleaned):
            return await message.answer("Телефон +375XXXXXXXXX")
        value = cleaned
    if field == "stud_number" and not re.fullmatch(r"\d{8}", value):
        return await message.answer("Студ. билет 8 цифр")
    if field == "form_educ" and value.lower() not in ("бюджет", "платное"):
        return await message.answer("Бюджет или Платное")
    if field == "scholarship" and value.lower() not in ("да", "нет"):
        return await message.answer("Да или Нет")

    if field == "faculty":
        value = FACULTIES[value]
    if field == "form_educ":
        value = value.lower()
    if field == "scholarship":
        value = value.lower() == "да"

    await state.update_data({field: value})
    await state.set_state(EditRegistration.menu)
    await message.answer("✅ Поле обновлено", reply_markup=ReplyKeyboardRemove())
    await show_edit_menu(message, state)

# ================= Подтверждение изменений =================
async def process_confirm_registration(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user = callback.from_user
    user_id = user.id
    data = await state.get_data()

    await callback.message.delete()

    log_action("Пользователь подтвердил редактирование данных", user, handler="process_confirm_registration")

    chat_id = callback.message.chat.id if callback.message.chat.type in ("group", "supergroup") else None

    try:
        async with db.pool.acquire() as conn:
            # Сохраняем данные, НЕ ТРОГАЕМ is_verified и group_id
            await conn.execute("""
                INSERT INTO users (
                    telegram_id, username, full_name, group_number, faculty,
                    mobile_number, stud_number, form_educ, scholarship,
                    created_at, updated_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW(), NOW())
                ON CONFLICT (telegram_id) DO UPDATE SET
                    username = EXCLUDED.username,
                    full_name = EXCLUDED.full_name,
                    group_number = EXCLUDED.group_number,
                    faculty = EXCLUDED.faculty,
                    mobile_number = EXCLUDED.mobile_number,
                    stud_number = EXCLUDED.stud_number,
                    form_educ = EXCLUDED.form_educ,
                    scholarship = EXCLUDED.scholarship,
                    updated_at = NOW()
            """, 
                user_id,
                user.username or None,
                data.get("full_name"),
                data.get("group_number"),
                data.get("faculty"),
                data.get("mobile_number"),
                data.get("stud_number"),
                data.get("form_educ"),
                data.get("scholarship")
            )

            # Явно верифицируем
            await conn.execute("""
                UPDATE users
                SET is_verified = TRUE,
                    updated_at = NOW()
                WHERE telegram_id = $1
            """, user_id)

            group_id = await conn.fetchval("SELECT group_id FROM users WHERE telegram_id = $1", user_id)

        log_action("Редактирование завершено успешно, is_verified = TRUE", user, handler="process_confirm_registration")

        if group_id:
            unmute_text = await _try_unmute_user(bot, user_id, group_id, user)
        else:
            unmute_text = "group_id не найден — размут не выполнен"

        await callback.message.answer(f"Данные успешно сохранены ✅\n{unmute_text}")

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
            ],
            resize_keyboard=True
        )
        await callback.message.answer("Меню:", reply_markup=keyboard)

    except Exception as e:
        log_action("Ошибка при подтверждении редактирования", user, str(e), "ERROR")
        await callback.message.answer("Произошла ошибка. Попробуйте заново (/start)")

    await state.clear()
    await callback.answer()
    