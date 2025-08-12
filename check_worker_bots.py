import asyncio
import os
import aiohttp

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from config import BOT_TOKEN
from db import Session
from models import BusinessConnection, WorkerBot, WorkerBotUser, UserGiftHistory
from cache import del_token_port, remove_token_from_port

LOG_FILE_PATH = "logs/worker_bot_check.log"
os.makedirs("logs", exist_ok=True)

def write_log(text: str):
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(text.strip() + "\n")

async def check_token_alive(token: str) -> tuple[bool, dict]:
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=8) as resp:
                data = await resp.json()
                return data.get("ok", False), data
    except Exception as e:
        return False, {"error": str(e)}

async def send_owner_notification(owner_tg_id: int, notify_text: str):
    main_bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        await main_bot.send_message(chat_id=owner_tg_id, text=notify_text)
    except Exception as e:
        write_log(f"[NOTIFY_ERROR] Не удалось отправить уведомление: {e}")
    finally:
        await main_bot.session.close()

async def check_worker_bots_once():
    write_log("[CHECK_WORKER_BOTS] Запуск проверки воркер-ботов...")

    async with Session() as session:
        result = await session.execute(
            select(WorkerBot).options(selectinload(WorkerBot.owner))
        )
        bots = result.scalars().all()

        for bot_data in bots:
            token = bot_data.token
            ok, data = await check_token_alive(token)

            if ok:
                username = data['result'].get('username', None)
                log_name = f"@{username}" if username else f"ID {bot_data.telegram_id}"
                write_log(f"[OK] {log_name} — бот работает")
            else:
                write_log(f"[DELETED] Bot ID {bot_data.telegram_id}: токен недействителен или бот удалён")

                try:
                    username = f"@{bot_data.username}" if bot_data.username else f"ID {bot_data.telegram_id}"

                    stats_text = (
                        f"<b>📉 Последняя статистика бота</b>\n"
                        f"• Запусков: <b>{bot_data.launches}</b>\n"
                        f"• Премиум запусков: <b>{bot_data.premium_launches}</b>\n"
                        f"• Подключений: <b>{bot_data.connection_count}</b>"
                    )

                    notify_text = (
                        f"<b>🤖 Бот {username} был удалён или токен стал недействителен.</b>\n"
                        f"Он автоматически удалён из панели.\n\n"
                        f"{stats_text}\n\n"
                        f"🔁 Вы можете добавить нового бота через меню панели."
                    )

                    if bot_data.owner:
                        await send_owner_notification(bot_data.owner.telegram_id, notify_text)

                except Exception as e:
                    write_log(f"[NOTIFY_ERROR] Не удалось подготовить уведомление: {e}")

                try:
                    user_ids_result = await session.execute(
                        select(WorkerBotUser.id).where(WorkerBotUser.worker_bot_id == bot_data.id)
                    )
                    user_ids = [row[0] for row in user_ids_result.all()]
                    if user_ids:
                        await session.execute(
                            delete(UserGiftHistory).where(UserGiftHistory.user_id.in_(user_ids))
                        )
                    await session.execute(
                        delete(BusinessConnection).where(BusinessConnection.worker_bot_id == bot_data.id)
                    )
                    await session.execute(
                        update(WorkerBotUser)
                        .where(WorkerBotUser.worker_bot_id == bot_data.id)
                        .values(worker_bot_id=None)
                    )
                    await session.delete(bot_data)
                    await session.commit()
                    write_log(f"[DB] Удалены данные бота ID {bot_data.telegram_id}")

                    try:
                        await del_token_port(token)  
                        if getattr(bot_data, "port", None):  
                            await remove_token_from_port(bot_data.port, token)
                        write_log(f"[REDIS] Токен и порт удалены из Redis для бота {token}")
                    except Exception as redis_err:
                        write_log(f"[REDIS_ERROR] Ошибка при удалении токена/порта из Redis: {redis_err}")

                except Exception as db_error:
                    await session.rollback()
                    write_log(f"[DB_ERROR] Ошибка при удалении: {db_error}")

            await asyncio.sleep(0.5)

    write_log("[CHECK_WORKER_BOTS] Проверка завершена")

async def check_worker_bots_loop():
    while True:
        await check_worker_bots_once()
        await asyncio.sleep(3700)