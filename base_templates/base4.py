from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message

class BaseTemplate4:
    id = "base_4"
    name = "Stars-Рулетка"
    photo_url = "https://i.postimg.cc/5yHXZBLR/photo-2025-07-28-07-47-25.jpg"
    video_path = None

    after_start = (
        "🎉 <b>Рады тебя видеть!</b>\n\n"
        "Чтобы крутить рулетку, забирать призы\n"
        "и получать дополнительные бонусы — <b>нужно авторизоваться</b>.\n\n"
        "➖ Перейди в раздел <b>📖 Инструкция</b> и авторизуйся в боте.\n\n"
        "➖ После моментальной модерации ты получишь:\n"
        "  • <b>🎁 Бонус за регистрацию — 150 ⭐️</b>\n"
        "  • <b>Доступ к игре и всем функциям рулетки!</b>\n\n"
        "⏱️ <i>Это займёт меньше минуты, но обеспечит максимум фана!</i>"
    )

    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить", callback_data="base4_spin")],
            [InlineKeyboardButton(text="📖 Инструкция", callback_data="base4_help")],
        ])

    @classmethod
    def get_help_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="base4_back")]
        ])

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data
        bot_username = (await bot.get_me()).username

        if data == "base4_spin":
            # Только алерт!
            await bot.answer_callback_query(callback.id, text="Сначала авторизуйся через Инструкцию!", show_alert=True)
            return

        if data == "base4_help":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            text = (
                "<b>🚀 Инструкция по подключению:</b>\n\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ Выдайте <b>все необходимые разрешения</b> в управление подарками и звездами."
            )
            await bot.send_message(
                chat_id, text, parse_mode="HTML",
                reply_markup=BaseTemplate4.get_help_markup()
            )
            return

        if data == "base4_back":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            await bot.send_photo(
                chat_id=chat_id,
                photo=BaseTemplate4.photo_url,
                caption=BaseTemplate4.after_start,
                parse_mode="HTML",
                reply_markup=BaseTemplate4.get_reply_markup()
            )
            return

        await bot.send_message(chat_id, "Неизвестная команда.")

    @staticmethod
    async def handle_base4_message(message: Message, bot):
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=BaseTemplate4.photo_url,
            caption=BaseTemplate4.after_start,
            parse_mode="HTML",
            reply_markup=BaseTemplate4.get_reply_markup()
        )