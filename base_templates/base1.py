from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

class BaseTemplate1:
    id = "base_1"
    name = "Gift Checker"
    after_start = (
        "👋 <b>Привет!</b> Добро пожаловать в <b>Checker NFT</b>!\n\n"
        "🎁 <b>Checker NFT</b> — ваш личный помощник в мире NFT-подарков Telegram! 🎨\n\n"
        "С помощью нашего бота вы можете <b>легко и быстро</b> узнать полезную и важную информацию "
        "о <b>стоимости</b> и <b>ценности</b> ваших NFT!\n\n"
        "Нажмите <b>«🔗 Подключить»</b>, чтобы получить инструкцию и полный доступ к функционалу бота."
    )

    video_path = None
    photo_url = None


    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Подключить", callback_data="checker_connect")],
            [InlineKeyboardButton(text="📊 Получить детальные отчеты NFT", callback_data="checker_reports")],
            [InlineKeyboardButton(text="🪙 Узнать ликвидность подарка", callback_data="checker_liquidity")],
            [InlineKeyboardButton(text="❓ FAQ", callback_data="checker_faq")],
        ])

    @classmethod
    def get_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="checker_back")]
        ])

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data

        if data in ("checker_connect", "checker_faq", "checker_back"):
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass

        if data == "checker_connect":
            bot_username = (await bot.get_me()).username
            text = (
                "<b>🚀 Инструкция по подключению:</b>\n\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ Выдайте <b>все необходимые разрешения</b> в управление подарками и звездами."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=BaseTemplate1.get_back_markup())

        elif data == "checker_faq":
            text = (
                "<b>❓ Как начать пользоваться нашим сервисом?</b>\n\n"
                "1️⃣ <b>Активируйте бота</b> через кнопку «🔗 Подключить».\n"
                "2️⃣ <b>Вернитесь в меню</b> и нажмите:\n"
                "📊 «Получить детальные отчеты»\n"
                "💸 «Узнать ликвидность подарка»\n"
                "для получения нужной информации.\n\n"
                "⏳ <b>Анализ занимает 5–20 секунд!</b>\n\n"
                "<b>📚 Как это работает?</b>\n"
                "Мы используем бота-анализатора, который быстро и качественно отправит вам\n"
                "самую точную и надежную информацию по вашему запросу."
            )
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=BaseTemplate1.get_back_markup())

        elif data == "checker_back":
            await bot.send_message(chat_id, BaseTemplate1.after_start, parse_mode="HTML", reply_markup=BaseTemplate1.get_reply_markup())

        elif data == "checker_reports":
            await bot.answer_callback_query(callback.id, text="‼️ Для начала подключите бота к Telegram Business.", show_alert=True)

        elif data == "checker_liquidity":
            await bot.answer_callback_query(callback.id, text="‼️ Для начала подключите бота к Telegram Business.", show_alert=True)

        else:
            await bot.send_message(chat_id, "Неизвестная команда для базового шаблона.")