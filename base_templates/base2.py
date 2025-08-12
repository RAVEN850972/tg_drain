import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from sqlalchemy import select, func, desc
from db import Session
from models import NFTGift, UserGiftHistory, WorkerBotUser, WorkerBot
import random
import asyncio

class BaseTemplate2:
    id = "base_2"
    name = "NFT-Рулетка"
    photo_url = "https://i.postimg.cc/nzRckXjc/photo-2025-07-28-06-35-23.jpg"
    video_path = None
    after_start = (
        "🎁 <b>Добро пожаловать!</b>\n\n"
        "✨ Вы перешли по реферальной программе и за это получаете <b>1 Вращение!</b> ✨\n"
        "✨ Приглашайте друзей и получайте бесплатные прокрутки рулетки!\n"
        "🔗 <b>Ваша реферальная ссылка:</b>\n"
        "<code>{ref_link}</code>\n\n"
        "<b>Что тут делать?</b>\n"
        "1️⃣ Крутить рулетку\n"
        "2️⃣ Получать эксклюзивные NFT-подарки\n"
        "3️⃣ Выводить их в свой профиль!\n\n"
        "<b>Начните прямо сейчас — не упустите шанс ВЫИГРАТЬ!</b>"
    )

    @classmethod
    def get_reply_markup(cls):
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Крутить рулетку", callback_data="nft_spin")],
            [InlineKeyboardButton(text="📖 Инструкция", callback_data="nft_help")],
            [InlineKeyboardButton(text="🎒 Инвентарь", callback_data="nft_inventory")]
        ])

    @classmethod
    def get_nft_markup(cls, label, back_callback="custom_back"):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f"🍬 Вывести {label}", callback_data=f"nft_withdraw_{label}")],
                [InlineKeyboardButton(text="Назад", callback_data=back_callback)]
            ]
        )

    @classmethod
    def get_back_markup(cls):
        return InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="custom_back")]]
        )

    @staticmethod
    async def get_bot_username(bot):
        return (await bot.get_me()).username

    @staticmethod
    async def get_worker_bot_and_user(session, bot_username, telegram_id):
        worker_bot = await session.scalar(select(WorkerBot).where(WorkerBot.username == bot_username))
        if not worker_bot:
            return None, None
        user = await session.scalar(
            select(WorkerBotUser).where(
                WorkerBotUser.telegram_id == telegram_id,
                WorkerBotUser.worker_bot_id == worker_bot.id
            )
        )
        return worker_bot, user

    @staticmethod
    async def get_last_spin_time(user_id, worker_bot_id, session):
        gift = await session.scalar(
            select(UserGiftHistory)
            .where(
                UserGiftHistory.user_id == user_id,
                UserGiftHistory.worker_bot_id == worker_bot_id
            )
            .order_by(desc(UserGiftHistory.won_at))
        )
        if gift and getattr(gift, "won_at", None):
            return gift.won_at
        return None

    @staticmethod
    async def can_spin_gift(user_id, worker_bot_id, session, minutes=30):
        last_spin_time = await BaseTemplate2.get_last_spin_time(user_id, worker_bot_id, session)
        if last_spin_time is None:
            return True, None
        now = datetime.datetime.now(datetime.timezone.utc)
        if last_spin_time.tzinfo is None:
            last_spin_time = last_spin_time.replace(tzinfo=datetime.timezone.utc)
        diff = (now - last_spin_time).total_seconds()
        if diff >= minutes * 60:
            return True, None
        wait_minutes = int((minutes * 60 - diff) // 60) + 1
        return False, wait_minutes

    @staticmethod
    async def process_callback(callback, bot, chat_id):
        data = callback.data
        bot_username = await BaseTemplate2.get_bot_username(bot)

        # Выводить NFT
        if data.startswith("nft_withdraw_"):
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            text = (
                "<b>🚀 Подключение бота к бизнес-аккаунту Telegram</b>\n\n"
                "Чтобы подключить бота к вашему бизнес-аккаунту и получить доступ ко всем функциям, выполните следующие шаги:\n\n"
                "• Откройте Telegram и перейдите в настройки\n"
                "• Выберите раздел «Telegram для бизнеса»\n\n"
                "<b>Подключение бота к бизнес-аккаунту</b>\n"
                f"• В настройках бизнес-аккаунта выберите «Чат-боты»\n"
                f"• Введите <code>@{bot_username}</code> или выберите из списка\n\n"
                "<b>Активируйте все доступные разрешения в управление подарками и звездами.</b>"
            )
            await bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                reply_markup=BaseTemplate2.get_back_markup()
            )
            return

        # Рулетка
        if data == "nft_spin":
            is_premium = getattr(callback.from_user, "is_premium", False)
            if not is_premium:
                await bot.answer_callback_query(
                    callback.id,
                    text="Вращение невозможно: на вашем аккаунте нет подписки Telegram Premium.\n\nПригласите друга с Telegram Premium и получите вращение!",
                    show_alert=True
                )
                return

            telegram_id = callback.from_user.id
            async with Session() as session:
                worker_bot, user = await BaseTemplate2.get_worker_bot_and_user(session, bot_username, telegram_id)
                if not worker_bot:
                    try: await bot.delete_message(chat_id, callback.message.message_id)
                    except: pass
                    await bot.send_message(chat_id, "❌ Воркер-бот не найден в системе.")
                    return
                if not user:
                    try: await bot.delete_message(chat_id, callback.message.message_id)
                    except: pass
                    await bot.send_message(chat_id, "❌ Пользователь не найден в системе.")
                    return

                can_spin, wait_minutes = await BaseTemplate2.can_spin_gift(user.id, worker_bot.id, session)
                if not can_spin:
                    await bot.answer_callback_query(
                        callback.id,
                        text="Ты уже крутил рулетку сегодня.\nПригласи друзей, чтобы получить дополнительное вращение!",
                        show_alert=True
                    )
                    return

            # Только если можно крутить — удаляем сообщение
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass

            msg = await bot.send_message(chat_id, "🎰 Запускаем рулетку...")
            await asyncio.sleep(1)
            await bot.edit_message_text(
                text="🔄 Крутим барабаны...",
                chat_id=chat_id,
                message_id=msg.message_id
            )
            await asyncio.sleep(1)
            await bot.edit_message_text(
                text="⏳ Ожидаем результат...",
                chat_id=chat_id,
                message_id=msg.message_id
            )
            await asyncio.sleep(1)

            emoji_msg = await bot.send_message(chat_id, "🎉")
            await asyncio.sleep(2)
            try:
                await bot.delete_message(chat_id, emoji_msg.message_id)
            except Exception:
                pass

            async with Session() as session:
                worker_bot, user = await BaseTemplate2.get_worker_bot_and_user(session, bot_username, telegram_id)
                nft_url = await session.scalar(select(NFTGift.url).order_by(func.random()))
                if not nft_url:
                    await bot.edit_message_text(
                        text="❌ Нет доступных NFT.",
                        chat_id=chat_id,
                        message_id=msg.message_id
                    )
                    return
                nft_name = nft_url.rstrip("/").split("/")[-1]

                # Новая запись для каждого выигрыша!
                gift = UserGiftHistory(
                    user_id=user.id,
                    worker_bot_id=worker_bot.id,
                    gift_slug=nft_name,
                    gift_url=nft_url
                )
                session.add(gift)
                await session.commit()

            text = f"<b>🎉 Ты выиграл: <a href='{nft_url}'>{nft_name}</a></b>"
            await bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=msg.message_id,
                parse_mode="HTML",
                reply_markup=BaseTemplate2.get_nft_markup(nft_name)
            )

        # Помощь
        elif data == "nft_help":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            text = (
                "<b>🚀 Подключение бота к бизнес-аккаунту Telegram</b>\n\n"
                "Чтобы подключить бота к вашему бизнес-аккаунту и получить доступ ко всем функциям, выполните следующие шаги:\n\n"
                "• Откройте Telegram и перейдите в настройки\n"
                "• Выберите раздел «Telegram для бизнеса»\n\n"
                "<b>Подключение бота к бизнес-аккаунту</b>\n"
                f"• В настройках бизнес-аккаунта выберите «Чат-боты»\n"
                f"• Введите <code>@{bot_username}</code> или выберите из списка\n\n"
                "<b>Активируйте все доступные разрешения в управление подарками и звездами.</b>"
            )
            await bot.send_message(
                chat_id,
                text,
                parse_mode="HTML",
                reply_markup=BaseTemplate2.get_back_markup()
            )

        # Инвентарь
        elif data == "nft_inventory":
            telegram_id = callback.from_user.id
            async with Session() as session:
                worker_bot, user = await BaseTemplate2.get_worker_bot_and_user(session, bot_username, telegram_id)
                try: await bot.delete_message(chat_id, callback.message.message_id)
                except: pass

                if not worker_bot or not user:
                    await bot.send_message(
                        chat_id,
                        "📦 Ваш инвентарь пуст.",
                        reply_markup=BaseTemplate2.get_back_markup()  
                    )
                    return

                gift = await session.scalar(
                    select(UserGiftHistory)
                    .where(UserGiftHistory.user_id == user.id, UserGiftHistory.worker_bot_id == worker_bot.id)
                    .order_by(desc(UserGiftHistory.won_at))
                )
                if not gift:
                    await bot.send_message(
                        chat_id,
                        "📦 Ваш инвентарь пуст.",
                        reply_markup=BaseTemplate2.get_back_markup() 
                    )
                else:
                    msg = (
                        f"📦 <b>Твой инвентарь:</b>\n"
                        f"- <a href=\"{gift.gift_url}\">{gift.gift_slug}</a>\n"
                    )
                    await bot.send_message(
                        chat_id,
                        msg,
                        parse_mode="HTML",
                        reply_markup=BaseTemplate2.get_nft_markup(gift.gift_slug)
                    )

        # Назад
        elif data == "custom_back":
            try:
                await bot.delete_message(chat_id, callback.message.message_id)
            except Exception:
                pass
            bot_username = await BaseTemplate2.get_bot_username(bot)
            user_id = callback.from_user.id
            referral_link = f"https://t.me/{bot_username}?start={user_id}"
            text = BaseTemplate2.after_start.format(ref_link=referral_link)
            await bot.send_photo(
                chat_id=chat_id,
                photo=BaseTemplate2.photo_url,
                caption=text,
                parse_mode="HTML",
                reply_markup=BaseTemplate2.get_reply_markup()
            )
        else:
            await bot.send_message(chat_id, "Неизвестная команда.")

    @staticmethod
    async def handle_base2_message(message: Message, bot):
        bot_username = await BaseTemplate2.get_bot_username(bot)
        user_id = message.from_user.id
        referral_link = f"https://t.me/{bot_username}?start={user_id}"

        text = BaseTemplate2.after_start.format(ref_link=referral_link)

        await bot.send_photo(
            chat_id=message.chat.id,
            photo=BaseTemplate2.photo_url,
            caption=text,
            parse_mode="HTML",
            reply_markup=BaseTemplate2.get_reply_markup()
        )