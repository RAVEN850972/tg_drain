from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from sqlalchemy.future import select

from config import LOG_BOT_TOKEN
from db import Session
from models import Admin

log_router = Router()
log_bot_instance: Bot | None = None

async def get_main_log_text(chat_id: int) -> str:
    return "<b>✅ Отстук успешно активирован.</b>"

async def send_main_log_menu(bot: Bot, chat_id: int):
    text = await get_main_log_text(chat_id)
    await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
    )

@log_router.message(Command("start"))
async def handle_start(message: Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    telegram_id = message.from_user.id

    async with Session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == telegram_id))
        admin = result.scalar_one_or_none()

        if not admin:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Перейти к основному боту", url="https://t.me/Alphasqquad_bot")]
            ])
            await message.answer(
                "<b>Ошибка:</b> сначала запустите <b>основной бот</b>.",
                parse_mode="HTML",
                reply_markup=keyboard
            )
            return

        if not admin.log_bot_enabled:
            admin.log_bot_enabled = True
            await session.commit()

        await send_main_log_menu(message.bot, telegram_id)

async def setup_log_bot():
    bot = Bot(token=LOG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(log_router)
    return bot, dp

async def get_log_bot() -> Bot:
    global log_bot_instance
    if not log_bot_instance:
        log_bot_instance = Bot(token=LOG_BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    return log_bot_instance

async def send_log(chat_id: int, text: str, photo_url: str = None, disable_web_page_preview: bool = True):
    bot = await get_log_bot()
    try:
        if photo_url:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo_url,
                caption=text,
                parse_mode="HTML"
            )
        else:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=disable_web_page_preview
            )
    except Exception:
        pass

    async with Session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == chat_id))
        admin = result.scalar_one_or_none()

        if admin and admin.log_channel_id:
            try:
                await bot.send_message(
                    chat_id=admin.log_channel_id,
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=disable_web_page_preview
                )
            except Exception:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "⚠️ <b>Внимание!</b>\n"
                            f"<b>Не удалось отправить лог в канал</b> <code>{admin.log_channel_id}</code>.\n"
                            "<b>Убедись, что бот добавлен в админы и имеет право отправки сообщений.</b>"
                        ),
                        parse_mode="HTML",
                        disable_web_page_preview=disable_web_page_preview
                    )
                except Exception:
                    pass