from db import Session
from models import Admin, WorkerBot
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import asyncio

user_fsm_states = {}
user_fsm_data = {}

async def is_admin_for_worker(bot_token, user_id):
    async with Session() as session:
        worker_bot = await session.scalar(
            select(WorkerBot)
            .where(WorkerBot.token == bot_token)
            .options(selectinload(WorkerBot.owner))
        )
        if not worker_bot or not worker_bot.owner:
            return False
        return worker_bot.owner.telegram_id == user_id

async def handle_gift_fsm(message, bot, bot_token):
    user_id = message.from_user.id
    text = message.text.strip()
    state = user_fsm_states.get(user_id)

    if text == "/start":
        user_fsm_states.pop(user_id, None)
        user_fsm_data.pop(user_id, None)
        return False

    if text == "/gift":
        if not await is_admin_for_worker(bot_token, user_id):
            await bot.send_message(user_id, "<b>Ты не админ этого бота.</b>", parse_mode="HTML")
            return True
        user_fsm_states[user_id] = "waiting_user_id"
        await bot.send_message(
            user_id,
            "<b>Введи Telegram ID(ы) (до 20 штук, через пробел или с новой строки):</b>\n"
            "<i>Можно указывать ID пользователей, чатов и каналов (например, -1002742402019)</i>",
            parse_mode="HTML"
        )
        return True

    if state == "waiting_user_id":
        ids = text.replace(",", " ").replace("\n", " ").split()
        if not all(i.lstrip("-").isdigit() for i in ids):
            await bot.send_message(user_id, "<b>Все ID должны быть числами. /start для выхода.</b>", parse_mode="HTML")
            user_fsm_states.pop(user_id, None)
            user_fsm_data.pop(user_id, None)
            return True
        if len(ids) > 20:
            await bot.send_message(user_id, "<b>Максимум можно указать 20 ID за раз. /start для выхода.</b>", parse_mode="HTML")
            user_fsm_states.pop(user_id, None)
            user_fsm_data.pop(user_id, None)
            return True
        user_fsm_data[user_id] = {"user_ids": [int(i) for i in ids]}
        user_fsm_states[user_id] = "waiting_gift_id"

        gift_examples = (
            "<b>Введи gift_id:</b>\n\n"
            "<b>Примеры:</b>\n"
            "💝 - <code>5170145012310081615</code>\n"
            "🧸 - <code>5170233102089322756</code>\n"
            "🎁 - <code>5170250947678437525</code>\n"
            "🌹 - <code>5168103777563050263</code>\n"
            "🎂 - <code>5170144170496491616</code>\n"
            "💐 - <code>5170314324215857265</code>\n"
            "🚀 - <code>5170564780938756245</code>\n"
            "🏆 - <code>5168043875654172773</code>\n"
            "💍 - <code>5170690322832818290</code>\n"
            "💎 - <code>5170521118301225164</code>\n"
            "🍾 - <code>6028601630662853006</code>"
        )
        await bot.send_message(user_id, gift_examples, parse_mode="HTML")
        return True

    if state == "waiting_gift_id":
        user_fsm_data[user_id]["gift_id"] = text
        user_fsm_states[user_id] = "waiting_gift_text"
        await bot.send_message(user_id, "<b>Введи текст для подарка (до 128 символов):</b>", parse_mode="HTML")
        return True

    if state == "waiting_gift_text":
        if len(text) > 128:
            await bot.send_message(user_id, "<b>Слишком длинный текст. Максимум 128 символов. Введи снова:</b>", parse_mode="HTML")
            return True

        data = user_fsm_data[user_id]
        gift_text = text or "Поздравляю! 🎁"
        user_ids = data["user_ids"]
        gift_id = data["gift_id"]

        async def send_one(uid):
            try:
                kwargs = dict(gift_id=gift_id, text=gift_text)
                if str(uid).startswith("-100") or (isinstance(uid, int) and uid < 0):
                    kwargs["chat_id"] = uid
                else:
                    kwargs["user_id"] = uid
                res = await bot.send_gift(**kwargs)
                return res is True
            except Exception as e:
                if "BALANCE_TOO_LOW" in str(e):
                    raise RuntimeError("BALANCE_TOO_LOW")
                print(f"[SEND_GIFT_ERROR] {uid}: {repr(e)}")
                return False

        try:
            results = await asyncio.gather(*[send_one(uid) for uid in user_ids])
            ok = sum(results)
            fail = len(user_ids) - ok

            await bot.send_message(
                user_id,
                f"<b>Отправка завершена:</b>\n✅ Успешно: <b>{ok}</b>\n❌ Не удалось: <b>{fail}</b>",
                parse_mode="HTML"
            )
        except RuntimeError as e:
            if str(e) == "BALANCE_TOO_LOW":
                await bot.send_message(user_id, "<b>Недостаточно звёзд на балансе бота для отправки подарков.</b>", parse_mode="HTML")
        finally:
            user_fsm_states.pop(user_id, None)
            user_fsm_data.pop(user_id, None)

        return True

    if state:
        await bot.send_message(user_id, "<b>Действие отменено. Начни заново: /start</b>", parse_mode="HTML")
        user_fsm_states.pop(user_id, None)
        user_fsm_data.pop(user_id, None)
        return True

    return False