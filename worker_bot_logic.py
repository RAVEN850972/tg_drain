import datetime
from aiogram import Bot
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from db import Session
from models import CustomGift, StarCheck, WorkerBot, WorkerBotUser, Template
import json
import logging
from aiogram.exceptions import TelegramForbiddenError
from base_templates.base6 import BaseTemplate6

from cache import (
    get_cached_video_fileid,
    set_cached_video_fileid,
    invalidate_video_fileid,
)

def get_ref_args(text):
    args = text.split()
    if len(args) > 1 and args[1].startswith("ref_"):
        parts = args[1][4:].split("_", 1)
        ref_code = parts[0]
        ref_slug = parts[1] if len(parts) > 1 else None
        return ref_code, ref_slug
    return None, None

def get_check_args(text):
    args = text.split()
    if len(args) > 1 and args[1].startswith("check_"):
        return args[1][6:].strip()  
    return None

def make_reply_markup(template, is_premium):
    try:
        if isinstance(template, dict):
            markup_raw = template.get("reply_markup")
            if markup_raw:
                markup_data = json.loads(markup_raw)
                if all(isinstance(btn, dict) for btn in markup_data):
                    is_inline = any("callback_data" in btn or "url" in btn for btn in markup_data)
                    if is_inline:
                        btns = [[InlineKeyboardButton(text=btn["text"], callback_data=btn.get("callback_data"), url=btn.get("url"))] for btn in markup_data]
                        return InlineKeyboardMarkup(inline_keyboard=btns)
                    else:
                        btns = [[KeyboardButton(text=btn["text"])] for btn in markup_data]
                        return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)
            buttons = []
            if template.get("button_text") and template.get("button_url"):
                buttons.append([InlineKeyboardButton(text=template["button_text"], url=template["button_url"])])
            if template.get("second_button_text") and template.get("second_button_reply"):
                buttons.append([InlineKeyboardButton(text=template["second_button_text"], callback_data="second_button_reply")])
            elif template.get("button_text"):
                buttons.append([InlineKeyboardButton(text=template["button_text"], callback_data="first_button_callback")])
            if buttons:
                return InlineKeyboardMarkup(inline_keyboard=buttons)

        if hasattr(template, "get_reply_markup") and callable(template.get_reply_markup):
            return template.get_reply_markup()

        if hasattr(template, "reply_markup") and template.reply_markup:
            markup_data = json.loads(template.reply_markup)
            if all(isinstance(btn, dict) for btn in markup_data):
                is_inline = any("callback_data" in btn or "url" in btn for btn in markup_data)
                if is_inline:
                    btns = [[InlineKeyboardButton(text=btn["text"], callback_data=btn.get("callback_data"), url=btn.get("url"))] for btn in markup_data]
                    return InlineKeyboardMarkup(inline_keyboard=btns)
                else:
                    btns = [[KeyboardButton(text=btn["text"])] for btn in markup_data]
                    return ReplyKeyboardMarkup(keyboard=btns, resize_keyboard=True)
        buttons = []
        if getattr(template, "button_text", None) and getattr(template, "button_url", None):
            buttons.append([InlineKeyboardButton(text=template.button_text, url=template.button_url)])
        if getattr(template, "second_button_text", None) and getattr(template, "second_button_reply", None):
            buttons.append([InlineKeyboardButton(text=template.second_button_text, callback_data="second_button_reply")])
        elif getattr(template, "button_text", None):
            buttons.append([InlineKeyboardButton(text=template.button_text, callback_data="first_button_callback")])
        if buttons:
            return InlineKeyboardMarkup(inline_keyboard=buttons)
    except Exception as e:
        logging.error(f"Reply markup error: {e}")
    return None

async def get_or_create_user(session, user, worker_bot, is_premium):
    user_obj = await session.scalar(
        select(WorkerBotUser).where(
            WorkerBotUser.telegram_id == user.id,
            WorkerBotUser.worker_bot_id == worker_bot.id
        )
    )
    if not user_obj:
        user_obj = WorkerBotUser(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            is_premium=is_premium,
            worker_bot_id=worker_bot.id
        )
        session.add(user_obj)
        worker_bot.launches += 1
        if is_premium:
            worker_bot.premium_launches += 1
        await session.flush()
    else:
        updated = False
        if user_obj.is_premium != is_premium:
            user_obj.is_premium = is_premium
            updated = True
        if user_obj.username != user.username:
            user_obj.username = user.username
            updated = True
        if user_obj.first_name != user.first_name:
            user_obj.first_name = user.first_name
            updated = True
        if updated:
            await session.flush()
    return user_obj

async def handle_worker_start(bot, message: Message, token: str, template=None):
    user = message.from_user
    chat_id = message.chat.id
    is_premium = bool(getattr(user, "is_premium", False))
    check_code = get_check_args(message.text)

    async with Session() as session:
        worker_bot = await session.scalar(
            select(WorkerBot)
            .where(WorkerBot.token == token)
            .options(
                selectinload(WorkerBot.template),
                selectinload(WorkerBot.custom_template)
            )
        )
        if not worker_bot:
            await safe_send(bot.send_message, chat_id, "❌ Бот не найден.")
            return

        try:
            user_obj = await get_or_create_user(session, user, worker_bot, is_premium)

            if check_code:
                if worker_bot.base_template_id != "base_6":
                    text = template.get("after_start") if isinstance(template, dict) else template.after_start
                    if '{ref_link}' in text:
                        ref_link = f"https://t.me/{worker_bot.username}?start={user.id}"
                        text = text.format(ref_link=ref_link)

                    reply_markup = make_reply_markup(template, is_premium)
                    await send_template_message(bot, chat_id, template, text, reply_markup, worker_bot_id=worker_bot.id)
                    return

                star_check = await session.scalar(
                    select(StarCheck)
                    .where(StarCheck.code == check_code)
                    .with_for_update()
                )
                if not star_check:
                    await safe_send(bot.send_message, chat_id, "❌ Чек не найден.")
                    return
                if star_check.is_used:
                    await safe_send(bot.send_message, chat_id, "⚠️ Чек уже активирован.")
                    return

                user_obj.stars_balance = (user_obj.stars_balance or 0) + star_check.stars_amount
                star_check.is_used = True
                star_check.used_by_user_id = user_obj.id

                await session.commit()
                await BaseTemplate6.send_check_activated(bot, chat_id, star_check.stars_amount)
                return

            await session.commit()

        except IntegrityError:
            await session.rollback()
            logging.error("IntegrityError при создании пользователя")
            return
        except Exception as e:
            await session.rollback()
            logging.error(f"DB error: {e}")
            await safe_send(bot.send_message, chat_id, "❌ Ошибка")
            return

        ref_code, ref_slug = get_ref_args(message.text)
        if (
            ref_code
            and worker_bot.custom_template
            and worker_bot.custom_template.ref_enabled
        ):
            try:
                slugs = json.loads(worker_bot.custom_template.slugs)
                slug = ref_slug if ref_slug and ref_slug in slugs else slugs[0] if slugs else None
                nft_link = (
                    f'\n\n<b>🎁 Подарок:</b> <a href="https://t.me/nft/{slug}">{slug.split("-")[0]}</a>'
                    if slug else ""
                )
                user_info = [
                    f"<b>@{user.username}</b>" if user.username else "",
                    user.first_name if user.first_name else "",
                    f"<code>{user.id}</code>"
                ]
                user_line = " | ".join(filter(None, user_info))
                ref_message_text = worker_bot.custom_template.ref_message_text or "🎁 Вы получили NFT!"
                ref_text = f"{user_line}\n{ref_message_text}{nft_link}"

                await safe_send(
                    bot.send_message,
                    chat_id,
                    ref_text,
                    parse_mode="HTML",
                    disable_web_page_preview=False
                )
                return
            except Exception as e:
                logging.error(f"Referral error: {e}")

        text = template.get("after_start") if isinstance(template, dict) else template.after_start
        if '{ref_link}' in text:
            ref_link = f"https://t.me/{worker_bot.username}?start={user.id}"
            text = text.format(ref_link=ref_link)

        reply_markup = make_reply_markup(template, is_premium)
        await send_template_message(bot, chat_id, template, text, reply_markup, worker_bot_id=worker_bot.id)

async def safe_send(method, *args, ret_message=False, **kwargs):
    try:
        msg = await method(*args, **kwargs)
        if ret_message:
            return msg
    except TelegramForbiddenError:
        pass
    except Exception as e:
        logging.error(f"Sending message error: {e}")
    return None

async def send_template_message(bot, chat_id, template, text, reply_markup, worker_bot_id):
    video_path = template.get("video_path") if isinstance(template, dict) else getattr(template, "video_path", None)
    photo_url = template.get("photo_url") if isinstance(template, dict) else getattr(template, "photo_url", None)

    if video_path:
        file_id = await get_cached_video_fileid(worker_bot_id, video_path)
        if file_id:
            try:
                await safe_send(
                    bot.send_video,
                    chat_id,
                    file_id,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=reply_markup
                )
                return
            except Exception as e:
                if "file_id" in str(e) or "wrong file identifier" in str(e):
                    await invalidate_video_fileid(worker_bot_id, video_path)
                else:
                    logging.error(f"[send_template_message] Ошибка отправки видео по file_id: {e}")

        try:
            msg = await safe_send(
                bot.send_video,
                chat_id,
                FSInputFile(video_path),
                caption=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
                ret_message=True
            )
            if msg and hasattr(msg, "video") and msg.video and getattr(msg.video, "file_id", None):
                await set_cached_video_fileid(worker_bot_id, video_path, msg.video.file_id)
        except Exception as e:
            logging.error(f"[send_template_message] Ошибка отправки видео через FSInputFile: {e}")

    elif photo_url:
        await safe_send(bot.send_photo, chat_id, photo_url, caption=text, parse_mode="HTML", reply_markup=reply_markup)
    else:
        await safe_send(bot.send_message, chat_id, text, parse_mode="HTML", reply_markup=reply_markup)