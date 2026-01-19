from aiogram import Router, F, Bot
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from db import try_complete_verification, pool, is_user_verified

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


class EditRegistration(StatesGroup):
    editing = State()


# Приветствие только на /start
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
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
        if field_key == "scholarship":
            value = "Да" if value else "Нет"
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(
                text=f"{field_name}: {value}",
                callback_data=f"edit_field_{field_key}"
            )
        ])

    keyboard.inline_keyboard.append([
        InlineKeyboardButton(text="Всё верно ✓", callback_data="confirm_registration")
    ])

    await message_or_query.answer(text, reply_markup=keyboard)


# Запрос нового значения поля (при редактировании)
@router.callback_query(F.data.startswith("edit_field_"))
async def process_edit_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.replace("edit_field_", "")

    prompts = {
        "full_name": "Введи ФИО полностью:",
        "group_number": "Теперь введи номер группы (6 цифр):",
        "faculty": "Теперь введи название факультета (например: ФИТУ, ИЭФ, ФКСиС, ФИБ, ФКП, ФРЭ)",
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

    await state.set_state(EditRegistration.editing)
    await state.update_data(editing_field=field)

    await callback.message.answer(prompts[field], reply_markup=kb)
    await callback.answer()


@router.message(EditRegistration.editing)
async def process_edit_value(message: Message, state: FSMContext):
    data = await state.get_data()
    field = data.get("editing_field")
    value = message.text.strip()

    if field == "full_name" and len(value.split()) < 3:
        await message.answer("Введи ФИО полностью (Пример: Иванова Кира Андреевна)")
        return

    if field == "group_number" and not (value.isdigit() and len(value) == 6):
        await message.answer("Группа — ровно 6 цифр")
        return

    if field == "faculty" and len(value) < 3:
        await message.answer("Название факульетат слишком короткое")
        return

    if field == "mobile_number":
        v = value.replace(" ", "").replace("-", "")
        if not (v.startswith("+") and v[1:].isdigit()):
            await message.answer("Телефон в формате +375#########")
            return
        value = v

    if field == "stud_number" and not (value.isdigit() and len(value) == 8):
        await message.answer("Студенческий — 8 цифр")
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
    if len(full_name.split()) < 3:
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
    await message.answer("Теперь введи название факультета (например: ФИТУ, ИЭФ, ФКСиС, ФИБ, ФКП, ФРЭ)")
    await state.set_state(Registration.faculty)


@router.message(Registration.faculty)
async def process_faculty(message: Message, state: FSMContext):
    faculty = message.text.strip()
    if len(faculty) < 3:
        await message.answer("Название факультета слишком короткое, попробуй ещё раз")
        return
    
    await state.update_data(faculty=faculty)
    await message.answer("Введи свой номер мобильного телефона\n(в формате +375#########)")
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
            InlineKeyboardButton(text="Всё верно ✓", callback_data="confirm_registration"),
            InlineKeyboardButton(text="Исправить ✗", callback_data="edit_registration")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)
    await state.set_state(None)

@router.callback_query(F.data == "edit_registration")
async def process_edit_registration(callback: CallbackQuery, state: FSMContext):
    # Переходим в режим редактирования
    await state.set_state(EditRegistration.editing)

    # Просто показываем меню редактирования
    await show_edit_menu(callback.message, state)

    await callback.answer()

# Подтверждение изменений — сохранение в базу
@router.callback_query(F.data == "confirm_registration")
async def process_confirm_registration(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()

    data = await state.get_data()

    form_educ_raw = data.get("form_educ", "").strip().lower()
    form_educ = "бюджет" if "бюдж" in form_educ_raw else "платное"

    try:
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
                callback.from_user.id,
                data.get("full_name"),
                data.get("group_number"),
                data.get("faculty"),
                data.get("mobile_number"),
                data.get("stud_number"),
                form_educ,
                data.get("scholarship")
            )

        success = await db.try_complete_verification(db.pool, callback.from_user.id)

        if success:
            # Убираем старую клавиатуру (Да/Нет и т.д.)
            await callback.message.answer("Регистрация завершена успешно.", reply_markup=ReplyKeyboardRemove()
            )

            # Пытаемся размутить в группе
            async with db.pool.acquire() as conn:
                group_id = await conn.fetchval(
                    "SELECT group_id FROM users WHERE telegram_id = $1",
                    callback.from_user.id
                )

            if group_id is None:
                await callback.message.answer(
                    "Группа не найдена в базе — попроси админа группы снять ограничения вручную."
                )
            else:
                try:
                    from aiogram.types import ChatPermissions

                    full_permissions = ChatPermissions(
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
                        chat_id=group_id,
                        user_id=callback.from_user.id,
                        permissions=full_permissions
                    )

                    main_menu = ReplyKeyboardMarkup(
                        keyboard=[
                            [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
                        ],
                        resize_keyboard=True,
                        one_time_keyboard=False
                    )

                    await callback.message.answer(
                        "Права в группе восстановлены 👌\n",reply_markup=main_menu
                    )
                except Exception as e:
                    print(f"Ошибка при размутывании: {e}")
                    await callback.message.answer(
                        f"Не удалось автоматически снять ограничения: {str(e)}\n"
                        "Попроси админа группы сделать это вручную."
                    )

            # Главное меню
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Статус"), KeyboardButton(text="Обновить данные")]
                ],
                resize_keyboard=True,
                one_time_keyboard=False
            )
    except Exception as e:
        print(f"Ошибка обновления: {e}")
        await callback.message.answer("Ошибка при сохранении. Попробуйте заново (/start)")

    await state.clear()
    await callback.answer()