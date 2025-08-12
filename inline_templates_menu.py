from aiogram import Router, F, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, delete
from db import Session
from models import Admin, CustomGift
import re
import json

router = Router()

TEMPLATES_PER_PAGE = 6

class InlineTemplateState(StatesGroup):
    waiting_name = State()
    waiting_nft = State()
    waiting_button_text = State()
    waiting_message_text = State()
    waiting_ref_message_text = State()  
    editing_message_text = State()
    editing_button_text = State()
    editing_links = State()
    editing_ref_message_text = State()  

async def get_inline_templates_content() -> tuple[str, InlineKeyboardMarkup]:
    text = (
        "<b>⚡️ Inline Mod - Шаблоны</b>\n\n"
        "<b>Создай свой кастомный шаблон</b>\n"
        "<b>❓ Как включить инлайн</b> <a href=\"https://teletype.in/@bebe3414/Fq3aeGKZbHx\"><b>Мануал</b></a>\n"
        "<blockquote>"
        "<b>🔗 Как привязать Inline-шаблон к боту:</b>\n"
        "1. Открой меню <b>Боты</b>\n"
        "2. Выбери своего бота\n"
        "3. Нажми <b>Подключить Инлайн</b>\n"
        "4. Выбери нужный инлайн-шаблон\n"
        "</blockquote>\n"
        "<i>Теперь твой бот сможет работать с Inline-превью!</i>"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Создать", callback_data="inline_tpl_create")],
            [InlineKeyboardButton(text="Мои шаблоны", callback_data="inline_tpl_list")]
        ]
    )
    return text, kb

@router.message(F.text == "⚡️ Inline Mod")
async def inline_templates_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    text, kb = await get_inline_templates_content()
    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.callback_query(F.data == "inline_tpl_create")
async def start_template_create(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(InlineTemplateState.waiting_name)
    await callback.message.edit_text("<b>✏️ Введите название шаблона:</b>", parse_mode="HTML")
    await callback.answer()

@router.message(InlineTemplateState.waiting_name)
async def input_name(message: types.Message, state: FSMContext):
    await state.update_data(template_name=message.text.strip())
    await state.set_state(InlineTemplateState.waiting_nft)
    await message.answer(
        "<b>📥 Введите до 10 ссылок вида:\nhttps://t.me/nft/ValentineBox-20352</b>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.message(InlineTemplateState.waiting_nft)
async def input_nfts(message: types.Message, state: FSMContext):
    slugs = re.findall(r"https://t\.me/nft/([A-Za-z0-9\-]+)", message.text)
    if not slugs:
        await message.answer("❌ Ссылки не найдены. Отправь хотя бы одну.")
        return
    if len(slugs) > 10:
        await message.answer("❌ Максимум 10 ссылок.")
        return
    await state.update_data(nft_slugs=slugs)
    await state.set_state(InlineTemplateState.waiting_button_text)
    await message.answer("<b>✏️ Введите текст кнопки:</b>", parse_mode="HTML")

@router.message(InlineTemplateState.waiting_button_text)
async def input_button(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text.strip())
    await state.set_state(InlineTemplateState.waiting_message_text)
    await message.answer(
        "<b>📝 Введите текст сообщения:</b>\n\n<b>Вы можете использовать любое форматирование текста.</b>",
        parse_mode="HTML"
    )

@router.message(InlineTemplateState.waiting_message_text)
async def input_text(message: types.Message, state: FSMContext):
    await state.update_data(message_text=message.html_text)
    await state.set_state(InlineTemplateState.waiting_ref_message_text)
    await message.answer(
        "<b>📝 Введите текст сообщения для перехода по реферальной ссылке:</b>\n\n"
        "<b>Вы можете использовать любое форматирование текста.</b>",
        parse_mode="HTML"
    )

@router.message(InlineTemplateState.waiting_ref_message_text)
async def input_ref_message_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    tg_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("❌ Админ не найден.")
            await state.clear()
            return

        gift = CustomGift(
            admin_id=admin.id,
            template_name=data["template_name"],
            slugs=json.dumps(data["nft_slugs"]),
            message_text=data["message_text"],
            button_text=data["button_text"],
            ref_message_text=message.html_text,
            lang="RU"
        )
        session.add(gift)
        await session.commit()

    await state.clear()
    await message.answer(
        f"<b>✅ Шаблон '{data['template_name']}' создан.</b>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    text, kb = await get_inline_templates_content()
    await message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@router.callback_query(F.data.startswith("inline_tpl_list"))
async def show_my_templates(callback: types.CallbackQuery):
    tg_id = callback.from_user.id

    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.message.edit_text("❌ Админ не найден.")
            return

        result = await session.execute(
            select(CustomGift.template_name)
            .where(CustomGift.admin_id == admin.id)
            .distinct()
        )
        names = result.scalars().all()

    if not names:
        text = (
            "<b>📁 У тебя пока нет ни одного шаблона.</b>\n\n"
            "<i>Создай свой кастомный шаблон для инлайн-режима!</i>"
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Создать", callback_data="inline_tpl_create")],
                [InlineKeyboardButton(text="Назад", callback_data="inline_tpl_back")]
            ]
        )
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        return

    total = len(names)
    pages = (total + TEMPLATES_PER_PAGE - 1) // TEMPLATES_PER_PAGE
    page = max(1, min(page, pages))
    start = (page - 1) * TEMPLATES_PER_PAGE
    end = start + TEMPLATES_PER_PAGE
    page_names = names[start:end]

    buttons = []
    row = []
    for i, name in enumerate(page_names):
        row.append(InlineKeyboardButton(text=name, callback_data=f"inline_tpl_show_{name}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    nav = []
    nav.append(InlineKeyboardButton(text="<", callback_data=f"inline_tpl_list:{page-1}" if page > 1 else "ignore"))
    nav.append(InlineKeyboardButton(text=f"{page}/{pages}", callback_data="ignore"))
    nav.append(InlineKeyboardButton(text=">", callback_data=f"inline_tpl_list:{page+1}" if page < pages else "ignore"))
    buttons.append(nav)

    buttons.append([InlineKeyboardButton(text="Назад", callback_data="inline_tpl_back")])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text("<b>📁 Твои шаблоны:</b>", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()  

@router.callback_query(F.data == "inline_tpl_back")
async def inline_templates_back(callback: types.CallbackQuery):
    text, kb = await get_inline_templates_content()
    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()


@router.callback_query(F.data.startswith("inline_tpl_show_"))
async def show_template_actions(callback: types.CallbackQuery, state: FSMContext):  
    await state.clear()  
    template_name = callback.data.replace("inline_tpl_show_", "", 1)
    tg_id = callback.from_user.id

    text, kb = await get_template_info_menu(tg_id, template_name)
    await callback.message.edit_text(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

async def get_template_info_menu(tg_id: int, template_name: str) -> tuple[str, InlineKeyboardMarkup]:
    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            return "❌ Админ не найден.", InlineKeyboardMarkup(inline_keyboard=[])

        gift = await session.scalar(
            select(CustomGift).where(
                CustomGift.admin_id == admin.id,
                CustomGift.template_name == template_name
            )
        )

    if not gift:
        return "❌ Шаблон не найден.", InlineKeyboardMarkup(inline_keyboard=[])

    slugs = json.loads(gift.slugs)
    links = "\n".join([
        f'<b><a href="https://t.me/nft/{slug}">{slug.split("-")[0]}</a></b>'
        for slug in slugs
    ])
    button_text = gift.button_text
    message_text = gift.message_text
    ref_message_text = gift.ref_message_text or "<i>Не задан</i>"
    ref_enabled = getattr(gift, "ref_enabled", False)

    # Надпись для переключателя
    ref_toggle = "✅ Реф-режим включен" if ref_enabled else "❌ Реф-режим выключен"

    text = (
        f"<b>📦 Шаблон: {template_name}</b>\n\n"
        f"<b>🔗 Ссылки NFT:</b>\n<blockquote>{links}</blockquote>\n\n"
        f"<b>🔘 Текст кнопки:</b>\n{button_text}\n\n"
        f"<b>📝 Сообщение:</b>\n{message_text}\n\n"
        f"<b>🎁 Текст для реф:</b>\n{ref_message_text}\n\n"
        f"<b>{ref_toggle}</b>"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Переключить реф-режим", callback_data=f"inline_tpl_toggle_ref_{template_name}")],
            [InlineKeyboardButton(text="Изменить текст", callback_data=f"inline_tpl_edit_msg_{template_name}")],
            [InlineKeyboardButton(text="Изменить текст кнопки", callback_data=f"inline_tpl_edit_btn_{template_name}")],
            [InlineKeyboardButton(text="Изменить текст для реф", callback_data=f"inline_tpl_edit_refmsg_{template_name}")],
            [InlineKeyboardButton(text="Изменить ссылки NFT", callback_data=f"inline_tpl_edit_links_{template_name}")],
            [InlineKeyboardButton(text="Удалить шаблон", callback_data=f"inline_tpl_delete_{template_name}")],
            [InlineKeyboardButton(text="Назад", callback_data="inline_tpl_list")]
        ]
    )

    return text, kb

@router.callback_query(F.data.startswith("inline_tpl_toggle_ref_"))
async def toggle_ref_mode(callback: types.CallbackQuery):
    template_name = callback.data.replace("inline_tpl_toggle_ref_", "", 1)
    tg_id = callback.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.answer("❌ Админ не найден.")
            return

        gift = await session.scalar(
            select(CustomGift).where(
                CustomGift.admin_id == admin.id,
                CustomGift.template_name == template_name
            )
        )
        if not gift:
            await callback.answer("❌ Шаблон не найден.")
            return

        gift.ref_enabled = not bool(getattr(gift, "ref_enabled", False))
        await session.commit()

    text, kb = await get_template_info_menu(tg_id, template_name)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.bot.send_message(
        callback.from_user.id,
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

@router.callback_query(F.data.startswith("inline_tpl_edit_msg_"))
async def edit_template_message(callback: types.CallbackQuery, state: FSMContext):
    template_name = callback.data.replace("inline_tpl_edit_msg_", "", 1)
    await state.clear() 
    await state.update_data(template_name=template_name)
    await state.set_state(InlineTemplateState.editing_message_text)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"inline_tpl_show_{template_name}")]
        ]
    )

    await callback.message.edit_text(
        "<b>📝 Введите новый текст сообщения:</b>\n\n<b>Вы можете использовать любое форматирование текста.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(InlineTemplateState.editing_message_text)
async def save_new_message_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_name = data["template_name"]
    tg_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("❌ Админ не найден.")
            await state.clear()
            return

        await session.execute(
            update(CustomGift)
            .where(CustomGift.admin_id == admin.id, CustomGift.template_name == template_name)
            .values(message_text=message.html_text)
        )
        await session.commit()

    await state.clear()
    text, kb = await get_template_info_menu(tg_id, template_name)
    await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@router.callback_query(F.data.startswith("inline_tpl_edit_btn_"))
async def edit_template_button_text(callback: types.CallbackQuery, state: FSMContext):
    template_name = callback.data.replace("inline_tpl_edit_btn_", "", 1)
    await state.clear()
    await state.update_data(template_name=template_name)
    await state.set_state(InlineTemplateState.editing_button_text)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"inline_tpl_show_{template_name}")]
        ]
    )

    await callback.message.edit_text(
        "<b>🔘 Введите новый текст кнопки:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(InlineTemplateState.editing_button_text)
async def save_new_button_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_name = data["template_name"]
    tg_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("❌ Админ не найден.")
            await state.clear()
            return

        await session.execute(
            update(CustomGift)
            .where(CustomGift.admin_id == admin.id, CustomGift.template_name == template_name)
            .values(button_text=message.text.strip())
        )
        await session.commit()

    await state.clear()
    text, kb = await get_template_info_menu(tg_id, template_name)
    await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@router.callback_query(F.data.startswith("inline_tpl_edit_links_"))
async def edit_template_links(callback: types.CallbackQuery, state: FSMContext):
    template_name = callback.data.replace("inline_tpl_edit_links_", "", 1)
    await state.clear()
    await state.update_data(template_name=template_name)
    await state.set_state(InlineTemplateState.editing_links)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"inline_tpl_show_{template_name}")]
        ]
    )

    await callback.message.edit_text(
        "<b>📥 Введите новые ссылки (до 10 шт):\nhttps://t.me/nft/Slug</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(InlineTemplateState.editing_links)
async def save_new_links(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_name = data["template_name"]
    tg_id = message.from_user.id

    slugs = re.findall(r"https://t\.me/nft/([A-Za-z0-9\-]+)", message.text)
    if not slugs:
        await message.answer("❌ Ссылки не найдены. Отправь хотя бы одну.")
        return
    if len(slugs) > 10:
        await message.answer("❌ Максимум 10 ссылок.")
        return

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("❌ Админ не найден.")
            await state.clear()
            return

        await session.execute(
            update(CustomGift)
            .where(CustomGift.admin_id == admin.id, CustomGift.template_name == template_name)
            .values(slugs=json.dumps(slugs))
        )
        await session.commit()

    await state.clear()
    text, kb = await get_template_info_menu(tg_id, template_name)
    await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)

@router.callback_query(F.data.startswith("inline_tpl_delete_"))
async def delete_template(callback: types.CallbackQuery, state: FSMContext):
    template_name = callback.data.replace("inline_tpl_delete_", "", 1)
    tg_id = callback.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await callback.message.edit_text(
                "❌ Админ не найден.",
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            await state.clear()
            return

        await session.execute(
            delete(CustomGift).where(
                CustomGift.admin_id == admin.id,
                CustomGift.template_name == template_name
            )
        )
        await session.commit()

    await callback.message.edit_text(
        f"<b>🗑️ Шаблон <u>{template_name}</u> удалён.</b>",
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    text, kb = await get_inline_templates_content()
    await callback.message.answer(
        text,
        reply_markup=kb,
        parse_mode="HTML",
        disable_web_page_preview=True
    )
    await callback.answer()

@router.callback_query(F.data.startswith("inline_tpl_edit_refmsg_"))
async def edit_ref_message_text(callback: types.CallbackQuery, state: FSMContext):
    template_name = callback.data.replace("inline_tpl_edit_refmsg_", "", 1)
    await state.clear()
    await state.update_data(template_name=template_name)
    await state.set_state(InlineTemplateState.editing_ref_message_text)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"inline_tpl_show_{template_name}")]
        ]
    )

    await callback.message.edit_text(
        "<b>📝 Введите новый текст для перехода по реф. ссылке:</b>\n\n<b>Вы можете использовать любое форматирование текста.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(InlineTemplateState.editing_ref_message_text)
async def save_new_ref_message_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_name = data["template_name"]
    tg_id = message.from_user.id

    async with Session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await message.answer("❌ Админ не найден.")
            await state.clear()
            return

        await session.execute(
            update(CustomGift)
            .where(CustomGift.admin_id == admin.id, CustomGift.template_name == template_name)
            .values(ref_message_text=message.html_text)
        )
        await session.commit()

    await state.clear()
    text, kb = await get_template_info_menu(tg_id, template_name)
    await message.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)