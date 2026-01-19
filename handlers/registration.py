from aiogram import Bot, types
from aiogram.types import CallbackQuery
from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
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


@router.message(CommandStart())
@router.message(F.chat.type == "private", F.text.lower().in_({"начать", "регистрация", "/start"}))
async def start_or_welcome(message: Message, state: FSMContext):
    user = message.from_user

    # Создаём или обновляем минимальную запись в базе
    async with db.pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, username, is_verified)
            VALUES ($1, $2, FALSE)
            ON CONFLICT (telegram_id) DO UPDATE
            SET username = EXCLUDED.username
        """, user.id, user.username)

    await state.clear()

    verified = await db.is_user_verified(user.id)

    status_emoji = "✅" if verified else "⏳"
    status_text = "зарегистрирован" if verified else "ещё не зарегистрирован"

    text = (
        f"Привет, {message.from_user.first_name or 'путешественник'}! 👋\n\n"
        f"Твой telegram_id: <code>{user.id}</code>\n"
        f"Username: @{user.username}\n"
        f"Статус в базе: {status_emoji} {status_text}\n\n"
    )

    if verified:
        text += (
            "Ты уже успешно зарегистрирован и можешь писать в группе.\n"
            "Если нужно обновить данные — напиши /update или просто «Изменить данные»"
        )
        keyboard = None
    else:
        text += (
            "Чтобы получить возможность писать в группе — пройди быструю регистрацию ↓\n\n"
            "Готов начать?"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Начать регистрацию →", callback_data="start_registration")]
        ])

    await message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "start_registration")
async def callback_start_registration(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "Отлично! Начинаем.\n\n"
        "Сначала введи своё ФИО полностью (как в зачётке - Иванова Кира Андреевна):"
    )
    await state.set_state(Registration.full_name)
    await callback.answer()


@router.message(Registration.full_name)
async def process_full_name(message: Message, state: FSMContext):
    full_name = message.text.strip()
    if len(full_name.split()) < 2:
        await message.answer("Пожалуйста, введи ФИО полностью (фамилия имя отчество)")
        return
    
    await state.update_data(full_name=full_name)
    
    await message.answer(
        "Отлично!\nТеперь введи номер группы (ровно 6 цифр, например: 320601)"
    )
    await state.set_state(Registration.group_number)


@router.message(Registration.group_number)
async def process_group_number(message: Message, state: FSMContext):
    group = message.text.strip()
    if not (group.isdigit() and len(group) == 6):
        await message.answer("Номер группы должен состоять ровно из 6 цифр")
        return
    
    await state.update_data(group_number=group)
    
    await message.answer("Теперь введи название факультета (например: ФКСиС, ФИТУ, ФКП, ФРЭ, ИЭФ, ФИБ)")
    await state.set_state(Registration.faculty)


@router.message(Registration.faculty)
async def process_faculty(message: Message, state: FSMContext):
    faculty = message.text.strip()
    if len(faculty) < 3:
        await message.answer("Название факультета слишком короткое, попробуй ещё раз")
        return
    
    await state.update_data(faculty=faculty)
    
    await message.answer("Введи свой номер мобильного телефона\n(в формате +375xxxxxxxxx)")
    await state.set_state(Registration.mobile_number)


@router.message(Registration.mobile_number)
async def process_mobile(message: Message, state: FSMContext):
    phone = message.text.strip().replace(" ", "").replace("-", "")
    if not (phone.startswith("+") and 10 <= len(phone) <= 13 and phone[1:].isdigit()):
        await message.answer("Номер телефона введён некорректно. Пример: +375291234567")
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
    
    # Инлайн-кнопки для подтверждения
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Всё верно ✓", callback_data="confirm_registration"),
            InlineKeyboardButton(text="Исправить ✗", callback_data="edit_registration")
        ]
    ])
    
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data.in_({"confirm_registration", "edit_registration"}))
async def process_confirm_callback(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.message.delete()  # убираем сообщение с данными и кнопками
    
    if callback.data == "confirm_registration":
        data = await state.get_data()
        
        # Нормализация формы обучения — только "платное" или "бюджет"
        form_educ_raw = data.get("form_educ", "").strip().lower()
        if "бюдж" in form_educ_raw:
            form_educ = "бюджет"
        else:
            form_educ = "платное"  # всё остальное считаем платным
        
        # Сохраняем данные в базу
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
            
            # Завершаем верификацию
            success = await db.try_complete_verification(db.pool, callback.from_user.id)
            
            if success:
                # Пытаемся размутить в группе
                async with db.pool.acquire() as conn:
                    group_id = await conn.fetchval(
                        "SELECT group_id FROM users WHERE telegram_id = $1",
                        callback.from_user.id
                    )
                
                if group_id:
                    try:
                        from aiogram.types import ChatPermissions
                        
                        full_permissions = ChatPermissions(
                            can_send_messages=True,
                            can_send_media_messages=True,
                            can_send_polls=True,
                            can_send_other_messages=True,
                            can_add_web_page_previews=True,
                            can_change_info=False,          # обычно не даём
                            can_invite_users=True,
                            can_pin_messages=False          # обычно не даём
                        )
                        
                        await bot.restrict_chat_member(
                            chat_id=group_id,
                            user_id=callback.from_user.id,
                            permissions=full_permissions
                        )
                        
                        await callback.message.answer(
                            "Регистрация успешно завершена!\n"
                            "Права в группе полностью восстановлены ✅\n"
                            "Теперь ты можешь свободно общаться в группе."
                        )
                    except Exception as e:
                        print(f"Ошибка при снятии ограничений: {e}")
                        await callback.message.answer(
                            "Регистрация завершена!\n"
                            "Но не удалось автоматически снять ограничения в группе.\n"
                            "Попроси админа группы сделать это вручную."
                        )
                else:
                    await callback.message.answer(
                        "Регистрация завершена успешно!\n"
                        "(Группа не найдена — права нужно снять вручную)"
                    )
        
        except Exception as e:
            print(f"Ошибка сохранения данных: {e}")
            await callback.message.answer("Произошла ошибка при сохранении. Попробуй заново (/start)")
    
    else:  # edit_registration
        await callback.message.answer(
            "Хорошо, давай исправим.\n"
            "Введи ФИО заново:"
        )
        await state.set_state(Registration.full_name)
    
    await callback.answer()
    await state.clear()