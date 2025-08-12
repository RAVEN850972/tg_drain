import asyncio
import os
from aiogram import Router, types, F, Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, func
from db import Session
from models import Admin, WorkerBot, WorkerBotUser
import datetime
from datetime import timezone
from aiogram.client.default import DefaultBotProperties
from sqlalchemy.orm import selectinload
from aiogram.exceptions import TelegramRetryAfter
from loader import bot as main_bot
from asyncio import Semaphore, gather, sleep
from imgbb_api import upload_image_from_file

router = Router()

TEMP_IMG_DIR = "temp_images"

class EditNickname(StatesGroup):
    waiting_for_nickname = State()

class SpamAllBotsState(StatesGroup):
    waiting_for_spam_text = State()
    confirm_photo = State()
    waiting_for_photo = State()

async def build_profile_text_and_kb(tg_id: int):
    async with Session() as session:
        stmt = select(Admin).where(Admin.telegram_id == tg_id)
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            return None, None
        count_stmt = select(func.count(WorkerBot.id)).where(WorkerBot.owner_id == admin.id)
        bot_count = (await session.execute(count_stmt)).scalar_one()

    payout_status = "✅ Подключена передача" if admin.worker_added_payout_id_flag else "❌ Передача не подключена"
    days_in_team = (
        (datetime.datetime.now(datetime.timezone.utc) - admin.created_at).days + 1
        if admin.created_at else "неизвестно"
    )
    top_btn_text = "Скрыть в топе" if not admin.hide_in_top else "Показывать в топе"
    top_btn_data = "toggle_hide_in_top"
    nickname_display = "Скрыт" if admin.hide_in_top else (admin.nickname or '🤫')

    text = (
        f"📍 <b>Твой профиль:</b>\n\n"
        f"🆔 <b>Telegram ID:</b> <code>{admin.telegram_id}</code>\n"
        f"📝 <b>Имя:</b> <b>{admin.first_name or '🤫'}</b>\n"
        f"🔖 <b>Твой тэг:</b> <b>#{nickname_display}</b>\n"
        f"🛠️ <b>Статус:</b> <b>{admin.status or 'Воркер'}</b>\n"
        f"🤖 <b>Количество ботов:</b> <b>{bot_count}</b>\n\n"
        f"📊 <b>Статистика за сегодня:</b>\n"
        f"<blockquote>🎆 <b>NFT:</b> <b>{admin.daily_gifts_unique}</b>\n"
        f"⭐ <b>Звёзд:</b> <b>{admin.daily_stars_sent}</b></blockquote>\n\n"
        f"📊 <b>Общая статистика:</b>\n"
        f"<blockquote>🎆 <b>NFT:</b> <b>{admin.gifts_unique_sent}</b>\n"
        f"⭐ <b>Звёзд:</b> <b>{admin.stars_sent}</b></blockquote>\n\n"
        f"💰 <b>Комиссия:</b>\n"
        f"• Твоя комиссия каждая {admin.commission_every}-я NFT\n\n"
        f"{payout_status}\n\n"
        f"⏳ <b>Ты с нами:</b> {days_in_team} {'день' if days_in_team == 1 else 'дней'}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=top_btn_text, callback_data=top_btn_data),
            InlineKeyboardButton(text="Изменить тэг", callback_data="edit_nickname"),
        ],
        [InlineKeyboardButton(text="Рефералка", callback_data="referral")],
        [InlineKeyboardButton(text="Проспамить всех ботов", callback_data="spam_all_bots")],
    ])
    return text, kb

@router.message(F.text == "💁🏻‍♀️ Мой профиль")
async def profile_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return
    text, kb = await build_profile_text_and_kb(message.from_user.id)
    if text is None:
        await message.answer("Профиль не найден")
        return
    await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "edit_nickname")
async def edit_nickname_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="cancel_edit_nickname")]
    ])
    await callback.message.edit_text(
        "<b>✏️ Отправь тэг:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await state.set_state(EditNickname.waiting_for_nickname)
    await callback.answer()

@router.callback_query(F.data == "cancel_edit_nickname")
async def cancel_edit_nickname(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await build_profile_text_and_kb(callback.from_user.id)
    if text:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@router.message(EditNickname.waiting_for_nickname)
async def save_new_nickname(message: types.Message, state: FSMContext):
    new_nick = message.text.strip()
    tg_id = message.from_user.id
    async with Session() as session:
        stmt = select(Admin).where(Admin.telegram_id == tg_id)
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            await message.answer("Профиль не найден")
            await state.clear()
            return
        admin.nickname = new_nick
        session.add(admin)
        await session.commit()
    await state.clear()
    text, kb = await build_profile_text_and_kb(tg_id)
    if text:
        await message.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data == "cancel_spam_all_bots")
async def cancel_spam_all_bots(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await build_profile_text_and_kb(callback.from_user.id)
    if text:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "spam_all_bots")
async def spam_all_bots_prompt(callback: types.CallbackQuery, state: FSMContext):
    async with Session() as session:
        admin_stmt = select(Admin).where(Admin.telegram_id == callback.from_user.id)
        admin = (await session.execute(admin_stmt)).scalar_one_or_none()
        
        if not admin:
            await callback.answer("Ошибка профиля.", show_alert=True)
            return

        bots_stmt = select(WorkerBot).where(WorkerBot.owner_id == admin.id)
        bots = (await session.execute(bots_stmt)).scalars().all()

        if not bots:
            await callback.answer("⚠️ У вас нету подключённых ботов.", show_alert=True)
            return

    await state.set_state(SpamAllBotsState.waiting_for_spam_text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="cancel_spam_all_bots")]
    ])
    text = (
        "<b>Введите текст рассылки для пользователей всех ваших ботов</b>\n\n"
        "<b>Можно использовать любое форматирование текста</b>\n"
        "<b>кроме фото и других вложений.</b>"
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.message(SpamAllBotsState.waiting_for_spam_text)
async def handle_spam_all_bots_text(message: types.Message, state: FSMContext):
    await state.update_data(spam_text=message.html_text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="spam_all_bots_photo_yes"),
             InlineKeyboardButton(text="Нет", callback_data="spam_all_bots_photo_no")]
        ]
    )
    await state.set_state(SpamAllBotsState.confirm_photo)
    await message.answer(
        "<b>Добавить к рассылке фото?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "spam_all_bots_photo_no", SpamAllBotsState.confirm_photo)
async def spam_all_bots_no_photo(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    spam_text = data["spam_text"]
    tg_id = cb.from_user.id
    await state.clear()
    await cb.message.answer("<b>✅ Рассылка запустилась, ожидайте статистику.</b>", parse_mode="HTML")
    asyncio.create_task(run_spam_to_all_bots(tg_id, spam_text))

@router.callback_query(F.data == "spam_all_bots_photo_yes", SpamAllBotsState.confirm_photo)
async def spam_all_bots_yes_photo(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(SpamAllBotsState.waiting_for_photo)
    await cb.message.answer(
        "<b>Отправь фото, которое нужно добавить к рассылке.</b>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(SpamAllBotsState.waiting_for_photo)
async def handle_spam_all_bots_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("<b>❌ Отправь именно фото!</b>", parse_mode="HTML")
        return
    data = await state.get_data()
    tg_id = message.from_user.id
    spam_text = data["spam_text"]
    file = await message.bot.get_file(message.photo[-1].file_id)
    file_path = file.file_path
    temp_path = os.path.join(TEMP_IMG_DIR, f"{message.photo[-1].file_id}.jpg")  # Вот тут исправлено
    await message.bot.download_file(file_path, temp_path)
    img_url = await upload_image_from_file(temp_path)
    try:
        os.remove(temp_path)
    except Exception:
        pass
    if not img_url:
        await message.answer("<b>❌ Не удалось загрузить фото на imgbb. Попробуй позже или другое фото.</b>", parse_mode="HTML")
        return
    await state.clear()
    await message.answer("<b>✅ Рассылка с фото запущена, ожидайте статистику.</b>", parse_mode="HTML")
    asyncio.create_task(run_spam_to_all_bots_with_photo(tg_id, spam_text, img_url))

async def run_spam_to_all_bots(tg_id: int, spam_text: str):
    sem = Semaphore(10)
    total = success = failed = 0

    async with Session() as session:
        stmt = (
            select(Admin)
            .options(selectinload(Admin.worker_bots))
            .where(Admin.telegram_id == tg_id)
        )
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            return

        bots = admin.worker_bots

        for bot in bots:
            result = await session.execute(
                select(WorkerBotUser.telegram_id).where(WorkerBotUser.worker_bot_id == bot.id)
            )
            user_ids = [row[0] for row in result.fetchall()]
            total += len(user_ids)

            bot_client = Bot(token=bot.token, default=DefaultBotProperties(parse_mode="HTML"))

            async def send_one(uid):
                nonlocal success, failed
                async with sem:
                    try:
                        await bot_client.send_message(chat_id=uid, text=spam_text, parse_mode="HTML")
                        success += 1
                    except TelegramRetryAfter as e:
                        await sleep(e.retry_after)
                        return await send_one(uid)
                    except Exception:
                        failed += 1

            for i in range(0, len(user_ids), 20):
                chunk = user_ids[i:i + 20]
                await gather(*(send_one(uid) for uid in chunk))
                await sleep(2)

            await bot_client.session.close()

    result_text = (
        f"<b>📊 Рассылка по всем ботам завершена</b>\n\n"
        f"<b>👥 Всего мамонтов: {total}</b>\n"
        f"<b>✅ Успешно отправлено: {success}</b>\n"
        f"<b>❌ Не доставлено: {failed}</b>"
    )
    try:
        await main_bot.send_message(chat_id=tg_id, text=result_text, parse_mode="HTML")
    except Exception:
        pass

async def run_spam_to_all_bots_with_photo(tg_id: int, spam_text: str, img_url: str):
    sem = Semaphore(10)
    total = success = failed = 0
    from loader import bot as main_bot

    async with Session() as session:
        stmt = (
            select(Admin)
            .options(selectinload(Admin.worker_bots))
            .where(Admin.telegram_id == tg_id)
        )
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            return

        bots = admin.worker_bots

        for bot in bots:
            result = await session.execute(
                select(WorkerBotUser.telegram_id).where(WorkerBotUser.worker_bot_id == bot.id)
            )
            user_ids = [row[0] for row in result.fetchall()]
            total += len(user_ids)

            bot_client = Bot(token=bot.token, default=DefaultBotProperties(parse_mode="HTML"))

            async def send_one(uid):
                nonlocal success, failed
                async with sem:
                    try:
                        await bot_client.send_photo(chat_id=uid, photo=img_url, caption=spam_text, parse_mode="HTML")
                        success += 1
                    except TelegramRetryAfter as e:
                        await sleep(e.retry_after)
                        return await send_one(uid)
                    except Exception:
                        failed += 1

            for i in range(0, len(user_ids), 20):
                chunk = user_ids[i:i + 20]
                await gather(*(send_one(uid) for uid in chunk))
                await sleep(2)

            await bot_client.session.close()

    result_text = (
        f"<b>📊 Рассылка с фото по всем ботам завершена</b>\n\n"
        f"<b>👥 Всего мамонтов: {total}</b>\n"
        f"<b>✅ Успешно отправлено: {success}</b>\n"
        f"<b>❌ Не доставлено: {failed}</b>"
    )
    try:
        await main_bot.send_message(chat_id=tg_id, text=result_text, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "toggle_hide_in_top")
async def toggle_hide_in_top_callback(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    async with Session() as session:
        stmt = select(Admin).where(Admin.telegram_id == tg_id)
        admin = (await session.execute(stmt)).scalar_one_or_none()
        if not admin:
            await callback.answer("Профиль не найден", show_alert=True)
            return
        admin.hide_in_top = not admin.hide_in_top
        session.add(admin)
        await session.commit()
    text, kb = await build_profile_text_and_kb(tg_id)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer("Готово!")