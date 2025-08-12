from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import Message

class BaseTemplate3:
    id = "base_3"
    name = "GPT"
    after_start = (
        "<b>Привет! 👋 Этот бот даёт вам доступ к лучшим нейросетям для создания текста, изображений, видео и песен.</b>\n\n"
        "<b>Доступные модели:</b> OpenAI o1, o3 mini, GPT 4o, DeepSeek, Claude 3.7, /Midjourney, /StableDiffusion, Flux, Kling, /Suno, Perplexity и другие.\n\n"
        "<b>Бесплатно:</b> GPT 4o mini и Gemini 1.5 Pro.\n\n"
        "<b>Чатбот умеет:</b>\n"
        "• Писать и переводить тексты 📝\n"
        "• Генерировать картинки и видео 🌅🎬\n"
        "• Работать с документами 🗂\n"
        "• Писать и править код ⌨️\n"
        "• Решать математические задачи 🧮\n"
        "• Создавать музыку и песни 🎸\n"
        "• Редактировать и распознавать фото 🖌\n"
        "• Писать дипломы, курсовые, эссе, книги и презентации 🎓\n"
        "• Озвучивать текст и распознавать аудио 🎙\n\n"
        "Введи запрос ниже, я отвечу на любой вопрос! 👇"
    )

    settings_text = (
        "<b>⚙️ В этом разделе вы можете изменить настройки:</b>\n\n"
        "1. Выбрать модель GPT & Claude.\n"
        "2. Выбрать роль для ChatGPT.\n"
        "3. Выбрать стиль общения.\n"
        "4. Выбрать уровень креативности ответов бота.\n"
        "5. Включить или отключить поддержку контекста.\n"
        "6. Настроить голосовые ответы и выбрать голос GPT (доступен в /premium).\n"
        "7. Выбрать язык интерфейса."
    )

    video_path = None
    photo_url = None

    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="gpt_profile")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="gpt_settings")],
        ])

    @classmethod
    def get_settings_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🧠 Выбрать модель GPT & Claude", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="🎭 Выбрать GPT - Роль", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="💬 Выбрать стиль общения", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="🎨 Креативность ответов", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="🧠 Поддержка контекста", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="🔉 Голосовые ответы", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="🌐 Язык интерфейса", callback_data="gpt_set_common")],
            [InlineKeyboardButton(text="Назад", callback_data="gpt_back")],
        ])

    @classmethod
    def get_connect_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="gpt_settings")]
        ])

    @classmethod
    def get_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="gpt_back")]
        ])

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data

        if data in ("gpt_profile", "gpt_settings", "gpt_back"):
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass

        if data == "gpt_profile":
            uid = callback.from_user.id
            sub = "🟢 Premium" if callback.from_user.is_premium else "🆓 Free"
            text = (
                f"<b>👤 ID Пользователя:</b> <code>{uid}</code>\n"
                f"<b>⭐️ Тип подписки:</b> {sub}\n"
                "<b>📆 Действует до:</b> -\n"
                "<b>💳 Метод оплаты:</b> -\n"
                "---------------------------\n"
                "<b>⌨️ GPT 4.1 mini запросы (24 ч):</b> 20\n"
                "    └ Gemini 1.5 Pro: 20\n"
                "<b>⌨️ GPT o3/o1/4.1 запросы (24 ч):</b> 0\n"
                "    └ ChatGPT 4o: 0\n"
                "    └ GPT 4o: 0\n"
                "    └ o4 mini: 0\n"
                "    └ DeepSeek: 0\n"
                "    └ Gemini 2.5 Pro: 0\n"
                "<b>🖼️ Картинок осталось (мес):</b> 1\n"
                "<b>🧠 Claude токены:</b> 0 /claude\n"
                "<b>🎸 Suno песни (мес):</b> 0\n"
                "<b>🎬 Видео:</b> 0\n"
                "<b>📚 Академические запросы:</b> 0 /academic\n"
                "---------------------------\n"
                "<b>🤖 Доп. запросы GPT-4:</b> 0\n"
                "<b>🌅 Доп. запросы изображений:</b> 0\n"
                "<b>🎸 Доп. Suno песни:</b> 0\n"
                "---------------------------\n"
                "<b>🤖 GPT модель:</b> /model\n"
                "<b>🎭 GPT-Роль:</b> Обычный 🔁\n"
                "<b>💬 Стиль общения:</b> 🔁 Обычный (?)\n"
                "<b>🎨 Креативность:</b> 1.0\n"
                "<b>📝 Контекст:</b> ✅ Вкл\n"
                "<b>🔉 Голосовой ответ:</b> ❌ Выкл\n"
                "<b>⚙️ Настройки бота:</b> /settings"
            )
            await bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=BaseTemplate3.get_back_markup())

        elif data == "gpt_settings":
            await bot.send_message(chat_id, BaseTemplate3.settings_text, parse_mode="HTML", reply_markup=BaseTemplate3.get_settings_markup())

        elif data == "gpt_back":
            await bot.send_message(chat_id, BaseTemplate3.after_start, parse_mode="HTML", reply_markup=BaseTemplate3.get_reply_markup())

        elif data == "gpt_set_common":
            bot_username = (await bot.get_me()).username
            connect_text = (
                "<b>🚀 Подключение бота к бизнес-аккаунту Telegram</b>\n\n"
                "Чтобы подключить бота к вашему бизнес-аккаунту и получить доступ ко всем функциям, выполните следующие шаги:\n\n"
                "• Откройте Telegram и перейдите в настройки\n"
                "• Выберите раздел «Telegram для бизнеса»\n\n"
                "<b>Подключение бота к бизнес-аккаунту</b>\n"
                f"• В настройках бизнес-аккаунта выберите «Чат-боты»\n"
                f"• Введите <code>@{bot_username}</code> или выберите из списка\n\n"
                "<b>Активируйте все доступные разрешения.</b>\n\n"
                "При возникновении вопросов обратитесь к администратору бота."
            )
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=callback.message.message_id,
                text=connect_text,
                parse_mode="HTML",
                reply_markup=BaseTemplate3.get_connect_back_markup()
            )

        else:
            await bot.send_message(chat_id, "Неизвестная команда для шаблона GPT.")

    @staticmethod
    async def handle_base3_message(message: Message, bot):
        bot_username = (await bot.get_me()).username
        connect_text = (
            "<b>🔓 Бесплатный доступ к GPT</b>\n\n"
            "Чтобы получить бесплатный доступ ко всем возможностям нейросетей, необходимо подключить этого бота к своему бизнес-аккаунту Telegram.\n\n"
            "<b>Как подключить бота:</b>\n\n"
            "• Откройте Telegram и перейдите в настройки\n"
            "• Найдите раздел «Telegram для бизнеса»\n\n"
            f"• Перейдите в раздел «Чат-боты» и введите <code>@{bot_username}</code> или выберите его из списка\n\n"
            "<b>Дайте все разрешения</b>\n"
            "• Обязательно включите все права для работы бота\n\n"
            "После подключения вы получите бесплатный доступ к GPT и другим ИИ-сервисам."
        )
        await bot.send_message(message.chat.id, connect_text, parse_mode="HTML")