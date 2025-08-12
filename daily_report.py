import asyncio
from datetime import datetime, timedelta, time
from sqlalchemy import select, func, desc
from db import Session
from models import WorkerBotUser, Admin, GlobalStats
from config import PANEL_CHAT_ID

try:
    from zoneinfo import ZoneInfo  
except ImportError:
    from pytz import timezone as ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")

def format_worker_name(worker):
    if not worker:
        return "Нет"
    return worker.nickname or worker.first_name or worker.username or "-"

async def reset_daily_statistics_auto():
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

async def send_daily_report(bot):
    now_kyiv = datetime.now(KYIV_TZ)
    yesterday = (now_kyiv - timedelta(days=1)).date()
    start = datetime.combine(yesterday, time.min, tzinfo=KYIV_TZ)
    end = datetime.combine(yesterday, time.max, tzinfo=KYIV_TZ)

    async with Session() as session:
        new_users = await session.scalar(
            select(func.count()).select_from(WorkerBotUser).where(
                WorkerBotUser.joined_at >= start,
                WorkerBotUser.joined_at <= end
            )
        )

        new_workers = await session.scalar(
            select(func.count()).select_from(Admin).where(
                Admin.created_at >= start,
                Admin.created_at <= end
            )
        )

        nft_worker_res = await session.execute(
            select(Admin).where(Admin.daily_gifts_unique > 0).order_by(desc(Admin.daily_gifts_unique))
        )
        nft_worker = nft_worker_res.scalars().first()
        nft_worker_name = (
            f"<b>{nft_worker.nickname or nft_worker.first_name or nft_worker.username or '-'}</b>"
            if nft_worker else "<b>Нет</b>"
        )

        stars_worker_res = await session.execute(
            select(Admin).where(Admin.daily_stars_sent > 0).order_by(desc(Admin.daily_stars_sent))
        )
        stars_worker = stars_worker_res.scalars().first()
        stars_worker_name = (
            f"<b>{stars_worker.nickname or stars_worker.first_name or stars_worker.username or '-'}</b>"
            if stars_worker else "<b>Нет</b>"
        )

        global_stats = await session.execute(select(GlobalStats).order_by(desc(GlobalStats.id)))
        stats = global_stats.scalars().first()
        profits_count = stats.daily_gifts_unique if stats else 0

    text = (
        "➖➖➖➖➖➖➖➖➖➖\n"
        "<b>📊 Подведем итоги за вчера</b>\n"
        f"<b>🗓 Дата: {yesterday.strftime('%d.%m.%Y')} г.</b>\n\n"
        f"├ <b>💸 Количество профитов NFT:</b> <b>{profits_count or 0}</b>\n"
        f"├ <b>🙆‍♂️ Новых мамонтов:</b> <b>{new_users or 0}</b>\n"
        f"├ <b>👨‍💻 Новых воркеров:</b> <b>{new_workers or 0}</b>\n"
        f"├ <b>🏅 Воркер дня по NFT:</b> {nft_worker_name}\n"
        f"└ <b>⭐️ Воркер дня по звёздам:</b> {stars_worker_name}\n"
        "➖➖➖➖➖➖➖➖➖➖"
    )

    await bot.send_message(PANEL_CHAT_ID, text, parse_mode="HTML")

async def daily_report_task(bot):
    while True:
        now_kyiv = datetime.now(KYIV_TZ)
        next_run = (now_kyiv + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        wait_seconds = (next_run - now_kyiv).total_seconds()
        await asyncio.sleep(wait_seconds)
        await send_daily_report(bot)
        await reset_daily_statistics_auto() 