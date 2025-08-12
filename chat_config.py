import asyncio
import os
from random import choice

from aiogram import Bot, F, Router, types
from aiogram.enums.chat_member_status import ChatMemberStatus
from aiogram.filters.command import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery
from sqlalchemy import func
from models import WorkerBotUser, BusinessConnection, WorkerBot
from aiogram.types import FSInputFile
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.text_decorations import html_decoration
from config import PANEL_CHAT_ID, PANEL_OWNERS
from datetime import datetime

import random
from datetime import datetime, timedelta
from aiogram.types import ChatPermissions

from sqlalchemy import select
from db import Session
from models import Admin
from stat_utils import (
    send_admin_and_global_stats as send_user_and_panel_stats,
    send_top_admins_by_nft as send_top_workers,
    send_top_admins_by_daily_nft as send_top_workers_daily,
    send_worker_stats_by_reply,
    handle_delete_stat_callback,
)

router = Router()

voice_index = 0

PROFILE_PHOTO_URL = "https://i.postimg.cc/43HBKFdT/IMG-1455.jpg"

@router.message(Command("idchat"))
async def handle_idchat_command(message: types.Message):
    if message.from_user.id not in PANEL_OWNERS:
        await message.answer("<b>Зачем тебе это?</b>", parse_mode="HTML")
        return

    await message.answer(f"<b>ID:</b> <code>{message.chat.id}</code>", parse_mode="HTML")

@router.message(Command("topmamonts"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_top_mamonts_command(message: types.Message):
    from stat_utils import send_top_admins_by_users_count
    await send_top_admins_by_users_count(message)

@router.message(Command("topmamontsday"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_top_mamonts_day_command(message: types.Message):
    from stat_utils import send_top_admins_by_users_today
    await send_top_admins_by_users_today(message)

@router.message(Command("stat"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_stat_command(message: types.Message):
    await send_user_and_panel_stats(message)

@router.message(Command("top"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_top_command(message: types.Message):
    await send_top_workers(message)

@router.message(Command("topday"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_topday_command(message: types.Message):
    await send_top_workers_daily(message)

@router.message(Command("statwork"), F.chat.type.in_({"group", "supergroup"}))
async def handle_statwork_command(message: types.Message):
    await send_worker_stats_by_reply(message)

@router.message(Command("topstars"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_topstars_command(message: types.Message):
    from stat_utils import send_top_admins_by_total_stars
    await send_top_admins_by_total_stars(message)

@router.message(Command("topstarsday"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_topstarsday_command(message: types.Message):
    from stat_utils import send_top_admins_by_daily_stars
    await send_top_admins_by_daily_stars(message)

@router.callback_query(F.data.startswith("delete_stat_msg"))
async def callback_delete_stat(call: types.CallbackQuery):
    await handle_delete_stat_callback(call)

async def setup_panel_chat(bot: Bot):
    commands = [
        BotCommand(command="/help", description="Список команд"),
        BotCommand(command="/my", description="Показать свой профиль"),
        BotCommand(command="/stat", description="Статистика"),
        BotCommand(command="/statbots", description="Общая статистика по ботам"),
        BotCommand(command="/top", description="Топ 10 по NFT"),
        BotCommand(command="/topday", description="Топ за день по NFT"),
        BotCommand(command="/topstars", description="Топ по звёздам"),
        BotCommand(command="/topstarsday", description="Топ по звёздам за день"),
        BotCommand(command="/topmamonts", description="Топ по мамонтам"),
        BotCommand(command="/topmamontsday", description="Топ по мамонтам за день"),
        BotCommand(command="/statwork", description="Статистика воркера (по ответу)"),
        BotCommand(command="/game", description="Сыграть на мут"),
        BotCommand(command="/muteme", description="В отдых на 15 минут"),
        BotCommand(command="/draw", description="Нарисовать кота"),
        BotCommand(command="/zaryad", description="Получить заряд на профит"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())

@router.message(Command("zaryad"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_zaryad_command(message: types.Message, bot: Bot):
    global voice_index

    await message.answer("🔮")

    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.full_name}</a>'

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Жестко делать", url="https://t.me/Alphasqquad_bot")]
    ])

    folder = "Ауди"
    files = sorted([f for f in os.listdir(folder) if f.endswith(".ogg")])

    if not files:
        await message.answer("⚠️ Нет доступных голосовых сообщений.")
        return

    file = files[voice_index % len(files)]  # по кругу
    voice_path = os.path.join(folder, file)

    voice = FSInputFile(voice_path)
    await message.answer_voice(
        voice=voice,
        caption=f"<b>✨ Поздравляем, {user_mention}! 🔋 Ты получил заряд.</b>",
        reply_markup=markup,
        parse_mode="HTML"
    )

    voice_index += 1

@router.message(Command("help"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_help_command(message: types.Message):
    text = (
        "<b>🎯 Команды чата</b>\n\n"
        "<b>/top</b> — Топ 10 воркеров по количеству NFT за всё время\n"
        "<b>/my</b> — Показать свой профиль\n"
        "<b>/topday</b> — Топ 10 воркеров по NFT за сегодня\n"
        "<b>/topstars</b> — Топ 10 воркеров по звёздам за всё время\n"
        "<b>/topstarsday</b> — Топ 10 воркеров по звёздам за день\n"
        "<b>/topmamonts</b> — Топ 10 по мамонтам за всё время\n"
        "<b>/topmamontsday</b> — Топ 10 по мамонтам за день\n"
        "<b>/stat</b> — Твоя статистика и общая статистика панели\n"
        "<b>/statbots</b> — Общая статистика по всем ботам\n"
        "<b>/statwork</b> — Получить статистику воркера (по ответу на сообщение)\n"
        "<b>/zaryad</b> — Получить мотивационный заряд на профит\n"
        "<b>/muteme</b> — Отойти в отдых на 15 минут\n"
        "<b>/game</b> — Дуэль на мут\n"
        "<b>/draw</b> — Нарисовать кота\n"
    )

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Удалить", callback_data=f"delete_help:{message.from_user.id}:{message.message_id}")]
    ])

    await message.answer(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data.startswith("delete_help"))
async def delete_help_handler(callback: types.CallbackQuery):
    parts = callback.data.split(":")
    if len(parts) != 3:
        await callback.answer("Ошибка", show_alert=True)
        return

    sender_id, command_msg_id = parts[1], parts[2]
    if str(callback.from_user.id) != sender_id and callback.from_user.id not in PANEL_OWNERS:
        await callback.answer("❌ Это отправил не ты", show_alert=True)
        return
    await callback.message.delete()
    try:
        await callback.message.chat.delete_message(int(command_msg_id))
    except:
        pass

    await callback.answer()

@router.message(F.new_chat_members)
async def greet_and_delete_system_message(message: Message, bot: Bot):
    try:
        await bot.delete_message(PANEL_CHAT_ID, message.message_id)
    except Exception as e:
        print(f"[ERROR] Не удалось удалить системное сообщение: {e}")

    for user in message.new_chat_members:
        name = html_decoration.quote(user.full_name)
        mention = f"<a href='tg://user?id={user.id}'>{name}</a>"

        welcome_text = (
            f"<b>👋 Привет, {mention}, добро пожаловать в наш чат.</b>\n"
            f"<b>📌 Обязательно прочитай закреп!</b>"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👆 Закреп", url="https://t.me/c/2820387167/35054")]
        ])

        try:
            await bot.send_photo(
                chat_id=PANEL_CHAT_ID,
                photo="https://i.ibb.co/1fxFBSzh/66930cd0-5ed3-4919-96c1-003241670dc1.png",
                caption=welcome_text,
                parse_mode="HTML",
                reply_markup=markup
            )
        except Exception as e:
            print(f"[ERROR] Не удалось отправить приветствие: {e}")

@router.message(F.left_chat_member)
async def handle_user_left_chat(message: types.Message, bot: Bot):
    try:
        await bot.delete_message(chat_id=PANEL_CHAT_ID, message_id=message.message_id)
    except Exception as e:
        print(f"[ERROR] Не удалось удалить сообщение о выходе: {e}")

    user = message.left_chat_member
    mention = f"<b><a href='tg://user?id={user.id}'>{html_decoration.quote(user.full_name)}</a></b>"

    try:
        await bot.send_message(
            chat_id=PANEL_CHAT_ID,
            text=f"<b>🚪 Покинул чат:</b> {mention}",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[ERROR] Не удалось отправить сообщение о выходе: {e}")

@router.message(Command("statbots"), F.chat.type.in_({"group", "supergroup", "private"}))
async def handle_stat_bots_command(message: types.Message):
    async with Session() as session:
        total_users = await session.scalar(select(func.count()).select_from(WorkerBotUser))
        total_connections = await session.scalar(select(func.count()).select_from(BusinessConnection))
        active_connections = await session.scalar(
            select(func.count()).select_from(BusinessConnection).where(BusinessConnection.is_connected == True)
        )
        premium_launches = await session.scalar(select(func.sum(WorkerBot.premium_launches)))

    text = (
        "<b>🎪 Цирк лунатиков е**чи:</b>\n\n"
        "<b>📊 Общая статистика по всем ботам:</b>\n"
        f"<blockquote>"
        f"<b>🙆🏻‍♀️ Мамонтов:</b> <b>{total_users}</b>\n"
        f"<b>💎 Премиум-мамонтов:</b> <b>{premium_launches or 0}</b>\n"
        f"<b>🎯 Подключений:</b> <b>{total_connections}</b>\n"
        f"<b>🟢 Активных:</b> <b>{active_connections}</b>\n"
        f"</blockquote>"
    )

    await message.answer(text, parse_mode="HTML")

@router.message(Command("unreg"), F.chat.type.in_({"group", "supergroup"}))
async def check_user_registration(message: types.Message, bot: Bot):
    if message.from_user.id not in PANEL_OWNERS:
        await message.answer("<b>❌ НЕТ</b>", parse_mode="HTML")
        return

    args = message.text.strip().split()[1:]
    if not args:
        await message.answer("<b>❌ Укажи хотя бы одного воркера: @username или Telegram ID</b>", parse_mode="HTML")
        return

    if len(args) > 10:
        await message.answer("<b>⚠️ Можно проверять максимум 10 воркеров за раз.</b>", parse_mode="HTML")
        return

    results = []

    async with Session() as session:
        for arg in args:
            identifier = arg.strip()

            try:
                # Получаем пользователя по username или ID
                user = await bot.get_chat(identifier if identifier.startswith("@") else int(identifier))

                if user.type != "private":
                    results.append(f"⚠️ {identifier} — это не пользователь, а {user.type}")
                    continue

                tg_user = user

            except Exception:
                results.append(f"❌ {identifier} — не найден или скрыт")
                continue

            result = await session.execute(select(Admin).where(Admin.telegram_id == tg_user.id))
            is_registered = result.scalar_one_or_none()

            if is_registered:
                results.append(f"✅ {html_decoration.quote(tg_user.full_name)} — {tg_user.id} в панели")
            else:
                results.append(f"❌ {html_decoration.quote(tg_user.full_name)} — {tg_user.id} нету в панели")

    text = "<b>" + "\n".join(results) + "</b>"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("draw"), F.chat.type.in_({"group", "supergroup"}))
async def handle_secret_mute_command(message: types.Message, bot: Bot):
    try:
        if message.from_user.id in PANEL_OWNERS:
            await message.answer(f"<b>😎 А ты крут, {message.from_user.full_name}!</b>", parse_mode="HTML")
            return

        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if chat_member.status == "creator":
            await message.answer(f"<b>👑 Владелец чата в игре — ему всё можно!</b>", parse_mode="HTML")
            return

        until_date = datetime.now() + timedelta(minutes=5)
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )

        await bot.send_sticker(
            chat_id=message.chat.id,
            sticker="CAACAgQAAyEFAASpZh67AAICp2hnPBwchTATQ2_tbZH-MWeKjzH-AAJiFgACdCuYUSEecQJ1K2NLNgQ"
        )

        await bot.send_message(
            chat_id=message.chat.id,
            text=(
                f"<b>🙃 ОЙ ОЙ ОЙ... <a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>, "
                f"зачем ты это сделал? ХАХАХА</b>\n"
                f"<b>🔇 Ты заглушил себя на 5 минут. Подумай над своим поведением 😂</b>"
            ),
            parse_mode="HTML"
        )

        await message.delete()

    except Exception as e:
        print(f"[MUTE_COMMAND ERROR]: {e}")

#@router.message(F.sticker)
#async def handle_sticker(message: types.Message):
    #sticker = message.sticker
    #await message.reply(
        #f"<b>🎯 file_id стикера:</b>\n<code>{sticker.file_id}</code>",
        #parse_mode="HTML"
    #)


# Состояния игры
mutbattle_active = False
mutbattle_creator = None
mutbattle_opponent = None
mutbattle_msg_id = None
mutbattle_chat_id = None
mutbattle_clicked = False

def build_battle_markup():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚔️ Принять вызов", callback_data="join_battle")]
        ]
    )

def build_fight_markup():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💥 Ударить первым", callback_data="hit_first")]
        ]
    )

@router.message(Command("game"), F.chat.type.in_({"group", "supergroup"}))
async def start_mutbattle(message: Message, bot: Bot):
    global mutbattle_active, mutbattle_creator, mutbattle_opponent, mutbattle_msg_id, mutbattle_chat_id, mutbattle_clicked

    if mutbattle_active:
        await message.answer("<b>Игра уже запущена. Подожди окончания.</b>", parse_mode="HTML")
        return

    mutbattle_active = True
    mutbattle_clicked = False
    mutbattle_creator = message.from_user.id
    mutbattle_opponent = None
    mutbattle_chat_id = message.chat.id

    msg = await message.answer(
        "<b>🔥 БИТВА ЗА ГОЛОС!</b>\n\n"
        "Жми — или молчи!\n"
        "Ожидаем соперника...\n\n"
        "⚠️ <i>Лузер ловит мут на 5 минут</i>",
        parse_mode="HTML",
        reply_markup=build_battle_markup()
    )

    mutbattle_msg_id = msg.message_id

    async def cancel_if_no_join():
        await asyncio.sleep(35)
        if mutbattle_opponent is None:
            await bot.edit_message_text(
                text="<b>❌ Игра отменена</b>\n\n<b>Никто не принял вызов.</b>",
                chat_id=mutbattle_chat_id,
                message_id=mutbattle_msg_id,
                parse_mode="HTML"
            )
            reset_mutbattle_state()

    asyncio.create_task(cancel_if_no_join())

def reset_mutbattle_state():
    global mutbattle_active, mutbattle_creator, mutbattle_opponent, mutbattle_msg_id, mutbattle_chat_id, mutbattle_clicked
    mutbattle_active = False
    mutbattle_creator = None
    mutbattle_opponent = None
    mutbattle_msg_id = None
    mutbattle_chat_id = None
    mutbattle_clicked = False

@router.callback_query(F.data == "join_battle")
async def join_battle_handler(callback: CallbackQuery, bot: Bot):
    global mutbattle_opponent

    if callback.from_user.id == mutbattle_creator:
        await callback.answer("Ты не можешь принять свой вызов", show_alert=True)
        return

    if mutbattle_opponent:
        await callback.answer("Игра уже началась", show_alert=True)
        return

    mutbattle_opponent = callback.from_user.id

    creator = await bot.get_chat(mutbattle_creator)
    opponent = await bot.get_chat(mutbattle_opponent)

    creator_mention = f"<a href='tg://user?id={mutbattle_creator}'>{creator.full_name}</a>"
    opponent_mention = f"<a href='tg://user?id={mutbattle_opponent}'>{opponent.full_name}</a>"

    await callback.answer()

    frames = [
        f"<b>⚔️ БИТВА НАЧИНАЕТСЯ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>\n\n"
        f"🤺                      🤺",

        f"<b>⚔️ БИТВА НАЧИНАЕТСЯ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>n\n"
        f"🤺   🏹                🏹   🤺",

        f"<b>⚔️ БИТВА НАЧИНАЕТСЯ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>\n\n"
        f"🤺       🏹        🏹       🤺",

        f"<b>⚔️ БИТВА НАЧИНАЕТСЯ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>\n\n"
        f"🤺         ➡️    ⬅️         🤺",

        f"<b>⚔️ БИТВА НАЧИНАЕТСЯ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>\n\n"
        f"🤺         💥    💥         🤺",

        f"<b>💥 ВРЕМЯ НАЖАТЬ КНОПКУ!</b>\n\n"
        f"<b>{creator_mention} vs {opponent_mention}</b>\n\n"
        f"🤺     ⚔️          ⚔️     🤺\n"
        f"<i>Кто ударит первым — выживет!</i>",
    ]

    for frame in frames:
        await bot.edit_message_text(
            text=frame,
            chat_id=mutbattle_chat_id,
            message_id=mutbattle_msg_id,
            parse_mode="HTML"
        )
        await asyncio.sleep(1)

    await bot.edit_message_text(
        text=frames[-1],
        chat_id=mutbattle_chat_id,
        message_id=mutbattle_msg_id,
        parse_mode="HTML",
        reply_markup=build_fight_markup()
    )

@router.callback_query(F.data == "hit_first")
async def handle_hit(callback: CallbackQuery, bot: Bot):
    global mutbattle_clicked, mutbattle_creator, mutbattle_opponent, mutbattle_active

    user_id = callback.from_user.id

    if mutbattle_clicked and user_id not in PANEL_OWNERS:
        await callback.answer("Ты проиграл", show_alert=True)
        return

    if mutbattle_creator in PANEL_OWNERS:
        winner_id = mutbattle_creator
        loser_id = mutbattle_opponent
    elif mutbattle_opponent in PANEL_OWNERS:
        winner_id = mutbattle_opponent
        loser_id = mutbattle_creator
    else:
        winner_id = user_id
        loser_id = mutbattle_opponent if user_id == mutbattle_creator else mutbattle_creator

    mutbattle_clicked = True

    until_date = datetime.now() + timedelta(minutes=5)
    try:
        await bot.restrict_chat_member(
            chat_id=mutbattle_chat_id,
            user_id=loser_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
    except Exception as e:
        print(f"[MUTE ERROR]: {e}")

    winner_chat = await bot.get_chat(winner_id)
    loser_chat = await bot.get_chat(loser_id)

    winner_mention = f"<a href='tg://user?id={winner_id}'>{winner_chat.full_name}</a>"
    loser_mention = f"<a href='tg://user?id={loser_id}'>{loser_chat.full_name}</a>"

    await bot.edit_message_text(
        f"<b>🏆 {winner_mention} Победитель</b>\n"
        f"<b>😂 {loser_mention} Проигравший получает мут</b>",
        chat_id=mutbattle_chat_id,
        message_id=mutbattle_msg_id,
        parse_mode="HTML"
    )

    mutbattle_active = False

@router.message(Command("my"))
async def my_profile_handler(message: types.Message):
    user_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == user_id))
        if not admin:
            await message.answer("<b>Ты не зарегистрирован.</b>", parse_mode="HTML")
            return

        if getattr(admin, "hide_in_top", False):
            nickname_display = "#Скрыт"
        else:
            nickname_display = admin.nickname or admin.first_name or "-"

        if admin.gifts_unique_sent > 0:
            nft_place = await session.scalar(
                select(func.count()).where(Admin.gifts_unique_sent > admin.gifts_unique_sent)
            )
            nft_top = nft_place + 1 if nft_place is not None else "-"
        else:
            nft_top = "-"

        if admin.stars_sent > 0:
            stars_place = await session.scalar(
                select(func.count()).where(Admin.stars_sent > admin.stars_sent)
            )
            stars_top = stars_place + 1 if stars_place is not None else "-"
        else:
            stars_top = "-"

        text = (
            f"<b>📍 Твой профиль</b>\n\n"
            f"<b>📝 Имя:</b> <b>{admin.first_name or '-'}</b>\n"
            f"<b>💁🏻‍♀️ Тэг:</b> <b>@{admin.username or '-'}</b>\n"
            f"<b>🔖 Никнейм:</b> <b>{nickname_display}</b>\n"
            f"<b>🛠️ Статус:</b> <b>{admin.status or 'Воркер'}</b>\n\n"
            f"<b>🏆 Место в топе по NFT:</b> <b>{nft_top}</b>\n"
            f"<b>🏅 Место в топе по звёздам:</b> <b>{stars_top}</b>\n\n"
            f"<b>📊 Статистика за сегодня:</b>\n"
            f"<blockquote>"
            f"<b>🎆 NFT:</b> <b>{admin.daily_gifts_unique}</b>\n"
            f"<b>⭐️ Звёзд:</b> <b>{admin.daily_stars_sent}</b>\n"
            f"</blockquote>\n"
            f"<b>📊 Общая статистика:</b>\n"
            f"<blockquote>"
            f"<b>🎆 NFT:</b> <b>{admin.gifts_unique_sent}</b>\n"
            f"<b>⭐️ Звёзд:</b> <b>{admin.stars_sent}</b>\n"
            f"</blockquote>"
        )

        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_my:{user_id}:{message.message_id}")]
        ])

        await message.answer_photo(PROFILE_PHOTO_URL, caption=text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(lambda c: c.data.startswith("delete_my:"))
async def delete_my_handler(callback: types.CallbackQuery):
    try:
        _, sender_id, command_msg_id = callback.data.split(":")
        sender_id = int(sender_id)
        command_msg_id = int(command_msg_id)
    except Exception:
        await callback.answer("Ошибка удаления", show_alert=True)
        return

    if callback.from_user.id != sender_id and callback.from_user.id not in PANEL_OWNERS:
        await callback.answer("❌ Это отправил не ты", show_alert=True)
        return

    try:
        await callback.message.delete()
    except:
        pass
    try:
        await callback.message.chat.delete_message(command_msg_id)
    except:
        pass

    await callback.answer()

@router.message(Command("muteme"), F.chat.type.in_({"group", "supergroup"}))
async def muteme_handler(message: types.Message, bot: Bot):
    try:
        if message.from_user.id in PANEL_OWNERS:
            await bot.send_message(
                chat_id=message.chat.id,
                text=f"<b>Тс, не время отдыхать</b>",
                parse_mode="HTML"
            )
            return

        until_date = datetime.now() + timedelta(minutes=15)
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date
        )
        mention = f"<a href='tg://user?id={message.from_user.id}'>{message.from_user.full_name}</a>"
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"<b>{mention} ушел отдыхать на 15 минут 💤</b>",
            parse_mode="HTML"
        )
        await message.delete()
    except Exception as e:
        print(f"[MUTEME ERROR]: {e}")