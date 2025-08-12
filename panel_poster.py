import asyncio
from config import PANEL_CHAT_ID
from loader import bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

POST_TEXT = (
    "<b>🃏 ЙОУ-ЙОУ</b>\n\n"
    "<b>‼️ Напоминание ‼️</b>\n"
    "<blockquote>"
    "TG может кидать личных ботов в <b>SaveMode</b> и не только!\n"
    "Не забывайте чаще менять своих воркер-ботов!\n"
    "Если что-то не работает — дело именно в этом."
    "</blockquote>\n"
    "<blockquote>"
    "‼️ Для успешного перевода NFT не забываем запускать своих ворк-ботов на аккаунте передачи."
    "</blockquote>\n"
    "<blockquote><b>🥇Топы по NFT будут получать уменьшение комиссии</b></blockquote>\n\n"
    "<b>💡 За помощью с подводом, настройке ботов и поиску мамонтов писать админу — @durovedeleted</b>"
)

POST_PHOTO_URL = "https://i.ibb.co/8DwMQG40/66930cd0-5ed3-4919-96c1-003241670dc1.png"

POST_BUTTONS = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🤦🏻‍♀️ Тр@хать мамонтов",
                url="https://t.me/Alphasqquad_bot"
            )
        ]
    ]
)

async def panel_poster_loop():
    while True:
        try:
            await bot.send_photo(
                PANEL_CHAT_ID,
                POST_PHOTO_URL,
                caption=POST_TEXT,
                parse_mode="HTML",
                reply_markup=POST_BUTTONS
            )
        except Exception as e:
            pass
        await asyncio.sleep(9000)