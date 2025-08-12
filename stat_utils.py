from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from sqlalchemy import func, select, desc
from config import PANEL_OWNERS
from db import Session
from models import Admin, GlobalStats, WorkerBot, WorkerBotUser
from datetime import datetime
from zoneinfo import ZoneInfo 

PROFILE_PHOTO_URL = "https://i.postimg.cc/ZnQWyjn1/IMG-1457.jpg" 

async def send_admin_and_global_stats(message: types.Message):
    async with Session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == message.from_user.id))
        admin = result.scalar_one_or_none()

        if not admin:
            await message.answer("❌ <b>Ты не авторизован в основном боте!</b>", parse_mode="HTML")
            return

        result = await session.execute(select(GlobalStats).where(GlobalStats.id == 1))
        panel = result.scalar_one_or_none()

        admin_text = (
            f"<b>💁🏻‍♀️ Твоя статистика</b>\n"
            f"<blockquote>"
            f"<b>🎆 За день NFT:</b> <b>{admin.daily_gifts_unique}</b>\n"
            f"<b>⭐️ За день звёзд:</b> <b>{admin.daily_stars_sent}</b>\n"
            f"<b>🎆 Всего NFT:</b> <b>{admin.gifts_unique_sent}</b>\n"
            f"<b>⭐️ Всего звёзд:</b> <b>{admin.stars_sent}</b>\n"
            f"</blockquote>"
        )

        global_text = (
            f"<b>📊 Статистика Панели</b>\n"
            f"<blockquote>"
            f"<b>🎆 За день NFT:</b> <b>{panel.daily_gifts_unique if panel else 0}</b>\n"
            f"<b>⭐️ За день звёзд:</b> <b>{panel.daily_stars_sent if panel else 0}</b>\n"
            f"<b>🎆 Всего NFT:</b> <b>{panel.total_gifts_unique if panel else 0}</b>\n"
            f"<b>⭐️ Всего звёзд:</b> <b>{panel.total_stars_sent if panel else 0}</b>\n"
            f"</blockquote>"
        )

        await message.answer(f"{admin_text}\n{global_text}", parse_mode="HTML")

# ТОП 10
async def send_top_admins_by_nft(message: types.Message):
    async with Session() as session:
        result = await session.execute(
            select(Admin).order_by(desc(Admin.gifts_unique_sent)).limit(10)
        )
        top_admins = result.scalars().all()
        while len(top_admins) < 10:
            top_admins.append(None)

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            admin = top_admins[i]
            if admin:
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
                nft_count = admin.gifts_unique_sent
            else:
                name = "—"
                nft_count = 0

            lines.append(f"<b>{symbols[i]} {name} - {nft_count}</b>")

        text = "<b>🏆 Топ 10 NFT</b>\n\n" + "\n".join(lines)

        photo_url = "https://i.postimg.cc/hjC8mdJF/photo-2025-08-09-20-59-28.jpg"

        await message.answer_photo(photo=photo_url, caption=text, parse_mode="HTML")


# ТОП 10 ЗА ДЕНЬ
async def send_top_admins_by_daily_nft(message: types.Message):
    async with Session() as session:
        result = await session.execute(
            select(Admin).order_by(desc(Admin.daily_gifts_unique)).limit(10)
        )
        top_admins = result.scalars().all()
        while len(top_admins) < 10:
            top_admins.append(None)

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            admin = top_admins[i]
            if admin:
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
                nft_count = admin.daily_gifts_unique
            else:
                name = "—"
                nft_count = 0

            lines.append(f"<b>{symbols[i]} {name} - {nft_count}</b>")

        text = "<b>📅 Топ 10 NFT за день</b>\n\n" + "\n".join(lines)

        photo_url = "https://i.postimg.cc/hjC8mdJF/photo-2025-08-09-20-59-28.jpg"

        await message.answer_photo(photo=photo_url, caption=text, parse_mode="HTML")

async def send_worker_stats_by_reply(message: types.Message):
    if not message.reply_to_message:
        await message.answer("<b>❌ Ответь этой командой на сообщение воркера</b>", parse_mode="HTML")
        return

    target_user = message.reply_to_message.from_user

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == target_user.id))
        if not admin:
            await message.answer(
                f"❌ Пользователь <b>{target_user.full_name}</b> не зарегистрирован.",
                parse_mode="HTML"
            )
            return

        if getattr(admin, "hide_in_top", False):
            nickname_display = "#Скрыт"
        else:
            nickname_display = admin.nickname or admin.first_name or target_user.full_name or "-"

        if admin.gifts_unique_sent > 0:
            nft_place = await session.scalar(
                select(func.count()).where(Admin.gifts_unique_sent > admin.gifts_unique_sent)
            )
            nft_top = nft_place + 1 if nft_place is not None else "-"
        else:
            nft_top = "-"

        if admin.stars_sent > 0:
            stars_place = await session.scalar(
                select(func.count()).where(Admin.stars_sent > admin.stars_sent)
            )
            stars_top = stars_place + 1 if stars_place is not None else "-"
        else:
            stars_top = "-"

        text = (
            f"<b>⚡️ Профиль воркера</b>\n\n"
            f"<b>📝 Имя:</b> <b>{admin.first_name or target_user.full_name or '-'}</b>\n"
            f"<b>💁🏻‍♀️ Тэг:</b> <b>@{admin.username or target_user.username or '-'}</b>\n"
            f"<b>🔖 Никнейм:</b> <b>{nickname_display}</b>\n"
            f"<b>🛠️ Статус:</b> <b>{admin.status or 'Воркер'}</b>\n\n"
            f"<b>🏆 Место в топе по NFT:</b> <b>{nft_top}</b>\n"
            f"<b>🏅 Место в топе по звёздам:</b> <b>{stars_top}</b>\n\n"
            f"<b>📊 Статистика за сегодня:</b>\n"
            f"<blockquote>"
            f"<b>🎆 NFT:</b> <b>{admin.daily_gifts_unique}</b>\n"
            f"<b>⭐️ Звёзд:</b> <b>{admin.daily_stars_sent}</b>\n"
            f"</blockquote>\n"
            f"<b>📊 Общая статистика:</b>\n"
            f"<blockquote>"
            f"<b>🎆 NFT:</b> <b>{admin.gifts_unique_sent}</b>\n"
            f"<b>⭐️ Звёзд:</b> <b>{admin.stars_sent}</b>\n"
            f"</blockquote>"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[[ 
            InlineKeyboardButton(
                text="Удалить",
                callback_data=f"delete_stat_msg:{message.from_user.id}:{message.message_id}"
            )
        ]])

        await message.answer_photo(PROFILE_PHOTO_URL, caption=text, parse_mode="HTML", reply_markup=markup)

# ТОП 10 по звёздам за всё время
async def send_top_admins_by_total_stars(message: types.Message):
    async with Session() as session:
        result = await session.execute(
            select(Admin).order_by(desc(Admin.stars_sent)).limit(10)
        )
        top_admins = result.scalars().all()
        while len(top_admins) < 10:
            top_admins.append(None)

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            admin = top_admins[i]
            if admin:
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
                stars = admin.stars_sent
            else:
                name = "—"
                stars = 0
            lines.append(f"<b>{symbols[i]} {name} - {stars}</b>")

        text = "<b>🏆 Топ 10 Stars</b>\n\n" + "\n".join(lines)

        photo_url = "https://i.postimg.cc/VNgXyCWS/photo-2025-08-09-21-01-07.jpg"

        await message.answer_photo(photo=photo_url, caption=text, parse_mode="HTML")

# ТОП 10 по звёздам за день
async def send_top_admins_by_daily_stars(message: types.Message):
    async with Session() as session:
        result = await session.execute(
            select(Admin).order_by(desc(Admin.daily_stars_sent)).limit(10)
        )
        top_admins = result.scalars().all()
        while len(top_admins) < 10:
            top_admins.append(None)

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            admin = top_admins[i]
            if admin:
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
                stars = admin.daily_stars_sent
            else:
                name = "—"
                stars = 0
            lines.append(f"<b>{symbols[i]} {name} - {stars}</b>")

        text = "<b>📅 Топ 10 Stars за день</b>\n\n" + "\n".join(lines)

        photo_url = "https://i.postimg.cc/VNgXyCWS/photo-2025-08-09-21-01-07.jpg"

        await message.answer_photo(photo=photo_url, caption=text, parse_mode="HTML")

# Хендлер кнопки "Удалить"
async def handle_delete_stat_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка", show_alert=True)
        return

    sender_id = int(parts[1])
    original_msg_id = int(parts[2])

    if callback.from_user.id != sender_id and callback.from_user.id not in PANEL_OWNERS:
        await callback.answer("❌ Это отправил не ты", show_alert=True)
        return

    try:
        await callback.message.delete()  
        await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=original_msg_id)  
    except Exception:
        pass

    await callback.answer()

# ТОП 10 по количеству мамонтов (пользователей)
async def send_top_admins_by_users_count(message: types.Message):
    async with Session() as session:
        result = await session.execute(
            select(Admin, func.count(WorkerBotUser.id).label("users_count"))
            .join(Admin.worker_bots)
            .join(WorkerBotUser, WorkerBot.id == WorkerBotUser.worker_bot_id)
            .group_by(Admin.id)
            .order_by(desc("users_count"))
            .limit(10)
        )
        top_admins = result.all()

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            if i < len(top_admins):
                admin, count = top_admins[i]
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
            else:
                name = "—"
                count = 0
            lines.append(f"<b>{symbols[i]} {name} — {count}</b>")

        text = "<b>🦣 Топ 10 по мамонтам</b>\n\n" + "\n".join(lines)
        await message.answer(text, parse_mode="HTML")

# ТОП 10 по количеству мамонтов за день
async def send_top_admins_by_users_today(message: types.Message):
    today_start = datetime.now(ZoneInfo("Europe/Kyiv")).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_utc = today_start.astimezone(ZoneInfo("UTC"))

    async with Session() as session:
        result = await session.execute(
            select(Admin, func.count(WorkerBotUser.id).label("users_count"))
            .join(Admin.worker_bots)
            .join(WorkerBotUser, WorkerBot.id == WorkerBotUser.worker_bot_id)
            .where(WorkerBotUser.joined_at >= today_start_utc)
            .group_by(Admin.id)
            .order_by(desc("users_count"))
            .limit(10)
        )
        top_admins = result.all()

        lines = []
        symbols = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

        for i in range(10):
            if i < len(top_admins):
                admin, count = top_admins[i]
                if getattr(admin, "hide_in_top", False):
                    name = "#Скрыт"
                else:
                    name = admin.nickname or admin.first_name or "нету"
            else:
                name = "—"
                count = 0
            lines.append(f"<b>{symbols[i]} {name} — {count}</b>")

        text = "<b>🦣 Топ 10 по мамонтам за день</b>\n\n" + "\n".join(lines)
        await message.answer(text, parse_mode="HTML")