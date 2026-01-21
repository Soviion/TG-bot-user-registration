# registration.py
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import config
from db import try_complete_verification, pool, is_user_verified

import hmac
import hashlib

def sign_data(data: str) -> str:
    h = hmac.new(config.CALLBACK_SECRET.encode(), data.encode(), hashlib.sha256)
    return h.hexdigest()[:12]  # 12 символов достаточно для защиты


def is_valid_signature(payload: str, signature: str) -> bool:
    expected = sign_data(payload)
    return hmac.compare_digest(expected, signature)

def make_signed_callback(payload: str) -> str:
    return f"{payload}:{sign_data(payload)}"

import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import db

router = Router(name="registration")


class Registration(StatesGroup):
    full_name = State()
    group_number = State()
    faculty = State()
    mobile_number = State()
    stud_number = State()
    form_educ = State()
    scholarship = State()
    confirm = State()

FACULTIES = {
    "ФКСиС": "FKSiS",
    "ФИТУ": "FITU",
    "ФКП": "FKP",
    "ФИБ": "FIB",
    "ИЭФ": "IEF",
    "ФРЭ": "FRE",
}

FACULTY_REVERSE = {
        "FKSiS": "ФКСиС",
        "FITU": "ФИТУ",
        "FKP": "ФКП",
        "FIB": "ФИБ",
        "IEF": "ИЭФ",
        "FRE": "ФРЭ",
}

faculty_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="ФКСиС"), KeyboardButton(text="ФИТУ"), KeyboardButton(text="ФКП")],
        [KeyboardButton(text="ФИБ"), KeyboardButton(text="ИЭФ"), KeyboardButton(text="ФРЭ")],
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)


class EditRegistration(StatesGroup):
    editing = State()


# Приветствие только на /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # проверка на личку
    if message.chat.type != "private":
        return  
     
    user = message.from_user
    user_id = user.id

    await state.clear()

    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, is_verified)
            VALUES ($1, $2, FALSE)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username
        """, user_id, user.username)

    verified = await db.is_user_verified(user_id)

    status_emoji = "✅" if verified else "⏳"
    status_text = "зарегистрирован" if verified else "ещё не зарегистрирован"

    text = (
        f"Привет, {user.first_name or '@' + (user.username or 'пользователь')}! 👋\n\n"
        "Этот бот создан для регистрации участников группы УИВР.\n\n"
        "Регистрируясь в боте, вы соглашаетесь на обработку своих персональных данных "
        "(ФИО, номер группы, телефона, студенческого билета и т.д.) в соответствии "
        "с политикой конфиденциальности группы.\n\n"
        "❗️Данные так же будут использоваться для формирования особождений, премий и "
        "других докладных записок и документов с вашим участием. По этой причине просим "
        "вносить правильные данные и в случае их изменений, обновлять их в этом боте.\n\n"
        f"Твой telegram_id: <code>{user_id}</code>\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Статус в базе: {status_emoji} {status_text}\n\n"
    )

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

    if not verified:
        text += "Чтобы получить возможность писать в группе — нужно пройти регистрацию. Нажми кнопку ниже или напиши /reg."
        keyboard.keyboard.append([KeyboardButton(text="Начать регистрацию")])

    await message.answer(text, reply_markup=keyboard)


# /reg — сразу регистрация
@router.message(F.text == "/reg")
async def cmd_reg(message: Message, state: FSMContext):

    # проверка на личку
    if message.chat.type != "private":
        return 

    user_id = message.from_user.id
    verified = await db.is_user_verified(user_id)

    if verified:
        await message.answer("Вы уже зарегистрированы и можете писать в группе.")
        return

    await state.clear()
    await message.answer("Отлично! Начинаем регистрацию.\n\nВведи своё ФИО полностью (Пример - Иванова Кира Андреевна):")
    await state.set_state(Registration.full_name)


# Статус — 3 строчки
@router.message(F.text == "Статус")
async def show_status(message: Message):

    # проверка на личку
    if message.chat.type != "private":
        return 

    user = message.from_user
    user_id = user.id

    verified = await db.is_user_verified(user_id)

    text = (
        f"Твой telegram_id: <code>{user_id}</code>\n"
        f"Username: @{user.username or 'нет'}\n"
        f"Статус в базе: {'✅ зарегистрирован' if verified else '⏳ ещё не зарегистрирован'}"
    )

    await message.answer(text)


# Обновить данные
@router.message(F.text == "Обновить данные")
@router.message(F.text == "/update")
async def update_data(message: Message, state: FSMContext):

    # проверка на личку
    if message.chat.type != "private":
        return 

    user_id = message.from_user.id
    verified = await db.is_user_verified(user_id)

    if not verified:
        await message.answer(
            "Вы ещё не зарегистрированы.\n"
            "Нажмите /reg или кнопку «Начать регистрацию», чтобы зарегистрироваться."
        )
        return

    async with db.pool.acquire() as conn:
        row = await conn.fetchrow("""
            SELECT full_name, group_number, faculty, mobile_number, 
                   stud_number, form_educ, scholarship
            FROM users 
            WHERE telegram_id = $1
        """, user_id)

    if not row:
        await message.answer("Не удалось найти твои полные данные. Начинаем заново.")
        await state.clear()
        await message.answer("Введи своё ФИО полностью:")
        await state.set_state(Registration.full_name)
        return

    await state.update_data(
        full_name=row["full_name"],
        group_number=row["group_number"],
        faculty=row["faculty"],
        mobile_number=row["mobile_number"],
        stud_number=row["stud_number"],
        form_educ=row["form_educ"],
        scholarship=row["scholarship"]
    )

    await show_edit_menu(message, state)


# Начать регистрацию (кнопка)
@router.message(F.text == "Начать регистрацию")
async def start_registration_button(message: Message, state: FSMContext):

    # проверка на личку
    if message.chat.type != "private":
        return 

    user_id = message.from_user.id
    verified = await db.is_user_verified(user_id)

    if verified:
        await message.answer("Вы уже зарегистрированы и можете писать в группе.")
        return

    await state.clear()
    await message.answer("Отлично! Начинаем регистрацию.\n\nВведи своё ФИО полностью:")
    await state.set_state(Registration.full_name)


# Функция показа меню редактирования
async def show_edit_menu(message_or_query, state: FSMContext):
    data = await state.get_data()

    text = "Что нужно изменить?\n\n"
    fields = [
        ("full_name", "ФИО"),
        ("group_number", "Группа"),
        ("faculty", "Факультет"),
        ("mobile_number", "Телефон"),
        ("stud_number", "Студ. билет"),
        ("form_educ", "Форма обучения"),
        ("scholarship", "Стипендия"),
    ]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[])

    for field_key, field_name in fields:
        value = data.get(field_key, "—")

        if field_key == "faculty":
            value = FACULTY_REVERSE.get(value, "—")

        if field_key == "scholarship":
            value = "Да" if value else "Нет"

        # Подписываем payload
        payload = f"edit_field_{field_key}"
        signature = sign_data(payload)
        signed_data = f"{payload}:{signature}"

        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{field_name}: {value}",
                callback_data=signed_data
            )
        ])

    # Кнопка "Всё верно ✓"
    payload_confirm = "confirm_registration"
    signature_confirm = sign_data(payload_confirm)
    signed_confirm = f"{payload_confirm}:{signature_confirm}"

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(
            text="Всё верно ✓",
            callback_data=signed_confirm
        )
    ])

    await message_or_query.answer(text, reply_markup=keyboard)



# Запрос нового значения поля (при редактировании)
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    payload = callback.data.split(':', 1)[0]
    field = payload.replace("edit_field_", "")

    prompts = {
        "full_name": "Введи ФИО полностью:",
        "group_number": "Теперь введи номер группы (6 цифр):",
        "faculty": "Выбери факультет:",
        "mobile_number": "Введи номер телефона (+375#########):",
        "stud_number": "Введи номер студенческого (8 цифр):",
        "form_educ": "Выбери форму обучения:",
        "scholarship": "Получаешь стипендию? (Да/Нет)",
    }

    kb = None
    if field == "form_educ":
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
    elif field == "faculty":
        kb = faculty_kb

    await state.set_state(EditRegistration.editing)
    await state.update_data(editing_field=field)

    await callback.message.answer(prompts[field], reply_markup=kb)
    await callback.answer()


@router.message(EditRegistration.editing)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("editing_field")

    if not message.text:
        await message.answer("Поле не может быть пустым")
        return

    value = message.text.strip()

    if field == "full_name":
        if len(value) > 150 or len(value.split()) < 3:
            await message.answer("Введи ФИО полностью (Пример: Иванова Кира Андреевна)")
            return

    if field == "group_number":
        if not re.fullmatch(r"\d{6}", value):
            await message.answer("Группа — ровно 6 цифр")
            return

    if field == "faculty":
        if value not in FACULTIES:
            await message.answer("Выбери факультет с кнопок 👇")
            return
        value = FACULTIES[value]

    if field == "mobile_number":
        v = value.replace(" ", "").replace("-", "")
        if not re.fullmatch(r"\+375\d{9}", v):
            await message.answer("Телефон в формате +375XXXXXXXXX")
            return
        value = v

    if field == "stud_number":
        if not re.fullmatch(r"\d{8}", value):
            await message.answer("Студенческий — ровно 8 цифр")
            return

    if field == "form_educ":
        if value.lower() not in ("бюджет", "платное"):
            await message.answer("Только Бюджет или Платное")
            return
        value = value.lower()

    if field == "scholarship":
        if value.lower() not in ("да", "нет"):
            await message.answer("Ответь Да или Нет")
            return
        value = value.lower() == "да"

    await state.update_data({field: value})
    await state.set_state(None)

    main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

    await message.answer("Поле обновлено ✅", reply_markup=main_menu)
    await show_edit_menu(message, state)


# Обычная регистрация — шаг за шагом (без редактирования)
@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()

    if len(full_name) > 150 or len(full_name.split()) < 3:
        await message.answer("Пожалуйста, введи ФИО полностью (Пример: Иванова Кира Андреевна)")
        return
    
    await state.update_data(full_name=full_name)
    await message.answer("Отлично!\nТеперь введи номер группы (ровно 6 цифр)")
    await state.set_state(Registration.group_number)


@router.message(Registration.group_number)
async def process_group_number(message: Message, state: FSMContext):
    group = message.text.strip()
    if not (group.isdigit() and len(group) == 6):
        await message.answer("Номер группы должен состоять ровно из 6 цифр")
        return
    
    await state.update_data(group_number=group)
    await message.answer(
        "Выбери свой факультет:",
        reply_markup=faculty_kb
    )
    await state.set_state(Registration.faculty)


@router.message(Registration.faculty)
async def process_faculty(message: Message, state: FSMContext):
    faculty_label = message.text.strip()

    if faculty_label not in FACULTIES:
        await message.answer("Пожалуйста, выбери факультет с кнопок ниже 👇")
        return

    faculty_code = FACULTIES[faculty_label]

    await state.update_data(faculty=faculty_code)
    
    await message.answer(
        "Введи свой номер мобильного телефона\n(в формате +375#########)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(Registration.mobile_number)


@router.message(Registration.mobile_number)
async def process_mobile(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not (phone.startswith("+") and 10 <= len(phone) <= 13 and phone[1:].isdigit()):
        await message.answer("Номер телефона введён некорректно. Пример: +375#########")
        return
    
    await state.update_data(mobile_number=phone)
    await message.answer("Теперь введи номер студенческого билета (8 цифр)")
    await state.set_state(Registration.stud_number)


@router.message(Registration.stud_number)
async def process_stud_number(message: Message, state: FSMContext):
    num = message.text.strip()
    if not (num.isdigit() and len(num) == 8):
        await message.answer("Номер студенческого должен состоять из 8 цифр")
        return
    
    await state.update_data(stud_number=num)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Бюджет"), KeyboardButton(text="Платное")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("Выбери форму обучения:", reply_markup=kb)
    await state.set_state(Registration.form_educ)


@router.message(Registration.form_educ)
async def process_form_educ(message: Message, state: FSMContext):
    form = message.text.strip()
    allowed = {"бюджет", "платное"}
    if form.lower() not in allowed:
        await message.answer("Выбери один из вариантов на клавиатуре")
        return
    
    await state.update_data(form_educ=form)
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer("Получаешь стипендию?", reply_markup=kb)
    await state.set_state(Registration.scholarship)


@router.message(Registration.scholarship)
async def process_scholarship(message: Message, state: FSMContext):
    ans = message.text.strip().lower()
    scholarship = ans == "да"
    
    await state.update_data(scholarship=scholarship)
    
    data = await state.get_data()
    
    text = (
        "Проверьте, всё ли верно:\n\n"
        f"ФИО: {data.get('full_name', '—')}\n"
        f"Группа: {data.get('group_number', '—')}\n"
        f"Факультет: {data.get('faculty', '—')}\n"
        f"Телефон: {data.get('mobile_number', '—')}\n"
        f"Студ. билет: {data.get('stud_number', '—')}\n"
        f"Форма обучения: {data.get('form_educ', '—')}\n"
        f"Стипендия: {'Да' if data.get('scholarship') else 'Нет'}\n\n"
        "Данные верные?"
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Всё верно ✓", callback_data=make_signed_callback("confirm_registration")),
            InlineKeyboardButton(text="Исправить ✗", callback_data=make_signed_callback("edit_registration"))
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)


async def process_edit_registration(callback: CallbackQuery, state: FSMContext):
    await state.set_state(EditRegistration.editing)
    await show_edit_menu(callback.message, state)
    await callback.answer()

# Подтверждение изменений — сохранение в базу
async def process_confirm_registration(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback.from_user.id

    already_verified = await db.is_user_verified(user_id)

    await callback.message.delete()  # убираем сообщение с данными и кнопками

    data = await state.get_data()

    # Нормализация формы обучения
    form_educ_raw = (data.get("form_educ") or "").strip().lower()
    form_educ = "бюджет" if "бюдж" in form_educ_raw else "платное"

    try:
        # 1️⃣ Обновляем данные ВСЕГДА
        async with db.pool.acquire() as conn:
            await conn.execute("""
                UPDATE users
                SET 
                    full_name     = $2,
                    group_number  = $3,
                    faculty       = $4,
                    mobile_number = $5,
                    stud_number   = $6,
                    form_educ     = $7,
                    scholarship   = $8,
                    updated_at    = NOW()
                WHERE telegram_id = $1
            """,
                user_id,
                data.get("full_name"),
                data.get("group_number"),
                data.get("faculty"),
                data.get("mobile_number"),
                data.get("stud_number"),
                form_educ,
                data.get("scholarship")
            )

        # 2️⃣ Если пользователь НЕ был верифицирован — завершаем верификацию
        if not already_verified:
            success = await db.try_complete_verification(db.pool, user_id)

            if not success:
                await callback.message.answer(
                    "Не удалось завершить верификацию.\n"
                    "Проверьте данные или напишите администратору."
                )
                await state.clear()
                await callback.answer()
                return

        # 3️⃣ Сообщение об успехе (общее)
        await callback.message.answer(
            "Данные успешно сохранены ✅",
            reply_markup=ReplyKeyboardRemove()
        )

        # 4️⃣ Размучиваем ТОЛЬКО при первой регистрации
        if not already_verified:
            async with db.pool.acquire() as conn:
                group_id = await conn.fetchval(
                    "SELECT group_id FROM users WHERE telegram_id = $1",
                    user_id
                )

            if group_id:
                try:
                    from aiogram.types import ChatPermissions

                    permissions = ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_invite_users=True
                    )

                    await bot.restrict_chat_member(
                        chat_id=group_id,
                        user_id=user_id,
                        permissions=permissions
                    )

                    await callback.message.answer(
                        "Права в группе полностью восстановлены ✅"
                    )

                except Exception as e:
                    print(f"Ошибка размутывания: {e}")
                    await callback.message.answer(
                        "Не удалось автоматически снять ограничения.\n"
                        "Попроси администратора сделать это вручную."
                    )

        # 5️⃣ Главное меню
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
            ],
            resize_keyboard=True
        )

        await callback.message.answer("Меню:", reply_markup=keyboard)

    except Exception as e:
        print(f"Ошибка при подтверждении регистрации: {e}")
        await callback.message.answer(
            "Произошла ошибка при сохранении данных. Попробуйте заново (/start)"
        )

    await state.clear()
    await callback.answer()

@router.callback_query()
async def secure_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    cb_data = callback.data

    if ':' not in cb_data:
        await callback.answer("Неверный запрос", show_alert=True)
        return

    payload, signature = cb_data.rsplit(':', 1)

    if not is_valid_signature(payload, signature):
        await callback.answer("Подпись не совпадает! Действие отклонено.", show_alert=True)
        return

    # Всё безопасно — вызываем нужную функцию
    if payload == "confirm_registration":
        await process_confirm_registration(callback, state, bot)

    elif payload.startswith("edit_field_"):
        field = payload.replace("edit_field_", "")
        await process_edit_field(callback, state)

    elif payload == "edit_registration":
        await process_edit_registration(callback, state)
        
    else:
        await callback.answer("Неизвестная команда", show_alert=True)
    