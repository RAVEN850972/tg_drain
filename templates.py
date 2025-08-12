# templates.py
import os
import re
import shutil
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from sqlalchemy import func, select
from models import Template, Admin, WorkerBot
from db import Session
from loader import bot
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.orm import selectinload
from aiogram.types import CallbackQuery
from imgbb_api import upload_image_from_file
import uuid

ITEMS_PER_PAGE = 8

router = Router()

class TemplateCreate(StatesGroup):
    waiting_name = State()
    waiting_after_start = State()
    waiting_non_premium_text = State()
    waiting_no_rights_text = State()
    waiting_disconnect_text = State()
    waiting_button_text = State()  
    waiting_button_url = State() 
    waiting_photo_url = State()
    waiting_video_file = State()
    waiting_second_button_text = State()        
    waiting_second_button_reply = State()

class TemplateEdit(StatesGroup):
    waiting_after_start_text = State()
    waiting_non_premium_text = State()
    waiting_no_rights_text = State()
    waiting_disconnect_text = State()
    waiting_new_photo = State()
    waiting_new_video = State()
    waiting_button_text = State()
    waiting_button_url = State()
    waiting_second_button_text = State()      
    waiting_second_button_reply = State()     
 
class TemplateImport(StatesGroup):
    waiting_code = State()

kb_skip_no_rights = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_no_rights_text")]
    ]
)
kb_skip_disconnect = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Пропустить", callback_data="skip_disconnect_text")]
    ]
)

kb_skip_button_text = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_button_text")]]
)
kb_skip_button_url = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_button_url")]]
)

kb_skip_second_button_text = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_second_button_text")]]
)
kb_skip_second_button_reply = InlineKeyboardMarkup(
    inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="skip_second_button_reply")]]
)


async def get_admin(tg_id: int) -> Admin | None:
    async with Session() as session:
        result = await session.execute(select(Admin).where(Admin.telegram_id == tg_id))
        return result.scalar_one_or_none()

@router.message(F.text == "🧩 Шаблоны")
async def templates_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    await get_templates_main_menu(message)

@router.callback_query(F.data == "back_to_templates")
async def back_to_templates(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  
    await get_templates_main_menu(callback)

async def save_template(state: FSMContext, admin: Admin, media: dict):
    data = await state.get_data()
    async with Session() as session:
        template = Template(
            name=data["name"],
            after_start=data["after_start"],
            non_premium_text=data["non_premium_text"],
            no_rights_text=data.get("no_rights_text"),
            disconnect_text=data.get("disconnect_text"),
            button_text=data.get("button_text"),
            button_url=data.get("button_url"),
            second_button_text=data.get("second_button_text"),          
            second_button_reply=data.get("second_button_reply"),         
            video_path=media.get("video_path"),
            photo_url=media.get("photo_url"),
            owner_id=admin.id,
            share_code=str(uuid.uuid4())
        )
        session.add(template)
        await session.commit()

# 🧩 Главное меню шаблонов
async def get_templates_main_menu(target: types.Message | types.CallbackQuery):
    text = (
        "<b>📑 Шаблоны</b>\n\n"
        "<b>📍 Создайте собственный шаблон.</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Создать шаблон", callback_data="create_template")],
        [InlineKeyboardButton(text="Мои шаблоны", callback_data="my_templates")],
        [InlineKeyboardButton(text="Ввести код шаблона", callback_data="enter_template_code")],
        #[InlineKeyboardButton(text="Базовые шаблоны", callback_data="ready_templates")]
    ])

    if isinstance(target, types.CallbackQuery):
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()
    else:
        await target.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "create_template")
async def start_template_creation(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TemplateCreate.waiting_name)
    await callback.message.edit_text("<b>Введите название шаблона:</b>", parse_mode="HTML")
    await callback.answer()

@router.message(TemplateCreate.waiting_name)
async def get_template_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await state.set_state(TemplateCreate.waiting_after_start)
    await message.answer(
        "<b>Введите текст после /start:\n\nВы можете использовать любое форматирование текста</b>",
        parse_mode="HTML"
    )

@router.message(TemplateCreate.waiting_after_start)
async def get_after_start_text(message: types.Message, state: FSMContext):
    await state.update_data(after_start=message.html_text)
    await state.set_state(TemplateCreate.waiting_non_premium_text)
    await message.answer(
        "<b>Введите текст для не-премиум пользователей:\n\nВы можете использовать любое форматирование текста</b>",
        parse_mode="HTML"
    )

@router.message(TemplateCreate.waiting_non_premium_text)
async def get_non_premium_text(message: types.Message, state: FSMContext):
    await state.update_data(non_premium_text=message.html_text)
    await state.set_state(TemplateCreate.waiting_no_rights_text)
    await message.answer(
        "<b>Введите текст который увидит мамонт если не выдал права для передачи нфт\n\n"
        "Вы можете использовать любое форматирование текста</b>",
        reply_markup=kb_skip_no_rights,
        parse_mode="HTML"
    )

@router.message(TemplateCreate.waiting_no_rights_text)
async def get_no_rights_text(message: types.Message, state: FSMContext):
    await state.update_data(no_rights_text=message.html_text)
    await state.set_state(TemplateCreate.waiting_disconnect_text)
    await message.answer(
        "<b>Введите текст при отключении бота от бизнес аккаунта\n\n"
        "Вы можете использовать любое форматирование текста</b>",
        reply_markup=kb_skip_disconnect,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_no_rights_text")
async def skip_no_rights_text_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(no_rights_text=None)
    await state.set_state(TemplateCreate.waiting_disconnect_text)
    await callback.message.edit_text(
        "<b>Введите текст при отключении бота от бизнес аккаунта\n\n"
        "Вы можете использовать любое форматирование текста</b>",
        reply_markup=kb_skip_disconnect,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateCreate.waiting_disconnect_text)
async def get_disconnect_text(message: types.Message, state: FSMContext):
    await state.update_data(disconnect_text=message.html_text)
    await state.set_state(TemplateCreate.waiting_button_text)
    await message.answer(
        "<b>Введите текст для инлайн-кнопки:</b>",
        reply_markup=kb_skip_button_text,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_disconnect_text")
async def skip_disconnect_text_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(disconnect_text=None)
    await state.set_state(TemplateCreate.waiting_button_text)
    await callback.message.edit_text(
        "<b>Введите текст для инлайн-кнопки:</b>",
        reply_markup=kb_skip_button_text,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateCreate.waiting_button_text)
async def get_button_text(message: types.Message, state: FSMContext):
    await state.update_data(button_text=message.text)
    await state.set_state(TemplateCreate.waiting_button_url)
    await message.answer(
        "<b>Введите ссылку для кнопки:</b>",
        reply_markup=kb_skip_button_url,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_button_text")
async def skip_button_text_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(button_text=None)
    await state.set_state(TemplateCreate.waiting_button_url)
    await callback.message.edit_text(
        "<b>Введите ссылку для кнопки:</b>",
        reply_markup=kb_skip_button_url,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateCreate.waiting_button_url)
async def get_button_url(message: types.Message, state: FSMContext):
    url = message.text.strip()
    if not re.match(r"^https?://[^\s]+$", url, re.IGNORECASE):
        await message.answer(
            "<b>❗️ Введите корректную ссылку (http://... или https://...)</b>",
            parse_mode="HTML"
        )
        return 

    await state.update_data(button_url=url)
    await state.set_state(TemplateCreate.waiting_second_button_text)
    await message.answer(
        "<b>Введите текст для второй инлайн-кнопки:</b>",
        reply_markup=kb_skip_second_button_text,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_button_url")
async def skip_button_url_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(button_url=None)
    await state.set_state(TemplateCreate.waiting_second_button_text)
    await callback.message.edit_text(
        "<b>Введите текст для второй инлайн-кнопки:</b>",
        reply_markup=kb_skip_second_button_text,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateCreate.waiting_second_button_text)
async def get_second_button_text(message: types.Message, state: FSMContext):
    await state.update_data(second_button_text=message.text)  
    await state.set_state(TemplateCreate.waiting_second_button_reply)
    await message.answer(
        "<b>Введите текст, который будет отправляться при нажатии на эту кнопку:</b>",
        reply_markup=kb_skip_second_button_reply,
        parse_mode="HTML"
    )

@router.callback_query(F.data == "skip_second_button_text")
async def skip_second_button_text_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(second_button_text=None)
    await state.set_state(TemplateCreate.waiting_second_button_reply)
    await callback.message.edit_text(
        "<b>Введите текст, который будет отправляться при нажатии на эту кнопку:</b>",
        reply_markup=kb_skip_second_button_reply,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateCreate.waiting_second_button_reply)
async def get_second_button_reply(message: types.Message, state: FSMContext):
    await state.update_data(second_button_reply=message.html_text)  
    await send_choose_media(message)

@router.callback_query(F.data == "skip_second_button_reply")
async def skip_second_button_reply_handler(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(second_button_reply=None)
    await send_choose_media(callback)

async def send_choose_media(target):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Видео", callback_data="template_media_video")],
            [InlineKeyboardButton(text="Фото", callback_data="template_media_photo")],
            [InlineKeyboardButton(text="Без медиа", callback_data="template_media_none")]
        ]
    )
    text = "<b>🎉 Шаблон почти готов — выберите медиа-тип:</b>"
    if isinstance(target, types.Message):
        await target.answer(text, reply_markup=kb, parse_mode="HTML")
    else:
        await target.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        await target.answer()

@router.callback_query(F.data == "template_media_photo")
async def ask_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TemplateCreate.waiting_photo_url)
    await callback.message.edit_text("<b>Отправьте фото для шаблона</b>", parse_mode="HTML")
    await callback.answer()

@router.message(TemplateCreate.waiting_photo_url, F.photo)
async def save_photo_and_template(message: types.Message, state: FSMContext):
    admin = await get_admin(message.from_user.id)
    if not admin:
        await message.answer("<b>❌ Вы не зарегистрированы как воркер.</b>", parse_mode="HTML")
        return

    file_id = message.photo[-1].file_id  
    file = await bot.get_file(file_id)
    file_path = f"temp_photo_{file_id}.jpg"
    await bot.download_file(file.file_path, destination=file_path)

    url = await upload_image_from_file(file_path)
    os.remove(file_path)

    if not url:
        await message.answer("❌ Не удалось загрузить фото на imgbb.")
        return

    await state.update_data(photo_url=url)
    await save_template(state, admin, {"photo_url": url})
    await state.clear()
    await message.answer("✅ Шаблон с фото успешно сохранён!")
    await get_templates_main_menu(message)

@router.message(TemplateCreate.waiting_photo_url)
async def wrong_photo_input(message: types.Message):
    await message.answer("<b>⚠️ Пожалуйста, отправьте именно фото.</b>", parse_mode="HTML")

@router.callback_query(F.data == "template_media_video")
async def ask_video_file(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TemplateCreate.waiting_video_file)
    await callback.message.edit_text("<b>Отправьте видеофайл для шаблона</b>", parse_mode="HTML")
    await callback.answer()

@router.message(TemplateCreate.waiting_video_file, F.video)
async def save_video_template(message: types.Message, state: FSMContext):
    admin = await get_admin(message.from_user.id)
    if not admin:
        await message.answer("<b>❌ Вы не зарегистрированы как воркер.</b>", parse_mode="HTML")
        return

    folder_path = os.path.join("Видео", str(admin.telegram_id))
    os.makedirs(folder_path, exist_ok=True)
    file_path = os.path.join(folder_path, f"{message.video.file_unique_id}.mp4")

    file = await bot.get_file(message.video.file_id)
    await bot.download_file(file.file_path, destination=file_path)

    await save_template(state, admin, {"video_path": file_path})
    await state.clear()
    await message.answer("✅ Шаблон с видео успешно сохранён!", show_alert=True)
    await get_templates_main_menu(message)

@router.message(TemplateCreate.waiting_video_file)
async def wrong_video_input(message: types.Message):
    await message.answer("<b>⚠️ Отправьте именно видеофайл.</b>", parse_mode="HTML")

@router.callback_query(F.data == "template_media_none")
async def save_template_without_media(callback: types.CallbackQuery, state: FSMContext):
    admin = await get_admin(callback.from_user.id)
    if not admin:
        await callback.message.edit_text("<b>❌ Вы не зарегистрированы как воркер.</b>", parse_mode="HTML")
        await callback.answer()
        return
    await save_template(state, admin, {})
    await state.clear()
    await callback.answer("✅ Шаблон без медиа успешно сохранён!", show_alert=True)
    await get_templates_main_menu(callback)

@router.callback_query(F.data.startswith("my_templates"))
async def show_my_templates(callback: types.CallbackQuery):
    try:
        parts = callback.data.split(":")
        page = int(parts[1]) if len(parts) > 1 else 1
    except Exception:
        page = 1

    admin = await get_admin(callback.from_user.id)
    if not admin:
        await callback.message.edit_text("<b>❌ Вы не зарегистрированы как воркер.</b>", parse_mode="HTML")
        await callback.answer()
        return

    async with Session() as session:
        total = await session.scalar(
            select(func.count()).select_from(Template).where(Template.owner_id == admin.id)
        )
        total = total or 0
        if total == 0:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Назад", callback_data="back_to_templates")]
            ])
            await callback.message.edit_text("<b>У вас пока нет созданных шаблонов.</b>", reply_markup=kb, parse_mode="HTML")
            await callback.answer()
            return

        total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        page = max(1, min(page, total_pages))
        start_idx = (page - 1) * ITEMS_PER_PAGE

        stmt = (
            select(Template)
            .where(Template.owner_id == admin.id)
            .order_by(Template.id.desc())
            .offset(start_idx)
            .limit(ITEMS_PER_PAGE)
        )
        result = await session.execute(stmt)
        page_templates = result.scalars().all()

    kb = [
        [InlineKeyboardButton(text=t.name, callback_data=f"template_{t.id}")]
        for t in page_templates
    ]

    nav = [
        InlineKeyboardButton(
            text="<",
            callback_data=f"my_templates:{page-1}" if page > 1 else "noop"
        ),
        InlineKeyboardButton(
            text=f"{page}/{total_pages}",
            callback_data="noop"
        ),
        InlineKeyboardButton(
            text=">",
            callback_data=f"my_templates:{page+1}" if page < total_pages else "noop"
        )
    ]
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="Назад", callback_data="back_to_templates")])

    await callback.message.edit_text(
        "<b>📌 Ваши созданные шаблоны:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )
    await callback.answer()
    
@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()

async def send_template_details(callback_or_message: types.CallbackQuery | types.Message, template: Template):
    if template.photo_url and template.video_path:
        media_info = "Привязаны фото и видео"
    elif template.photo_url:
        media_info = "Привязано фото"
    elif template.video_path:
        media_info = "Привязано видео"
    else:
        media_info = "Без медиа и фото"

    text = (
        f"<b>📄 Шаблон:</b> <code>{template.name}</code>\n\n"
        f"<b>📦 Медиа:</b> {media_info}"
    )

    kb_buttons = [
        [InlineKeyboardButton(text="Изменить текст /start", callback_data=f"edit_after_start_{template.id}")],
        [InlineKeyboardButton(text="Изменить текст не премиум", callback_data=f"edit_non_premium_{template.id}")],
        [InlineKeyboardButton(text="Изменить текст без прав", callback_data=f"edit_no_rights_{template.id}")],
        [InlineKeyboardButton(text="Изменить текст при отключении", callback_data=f"edit_disconnect_{template.id}")],
        [InlineKeyboardButton(text="Изменить текст кнопки", callback_data=f"edit_button_text_{template.id}")],         
        [InlineKeyboardButton(text="Изменить ссылку кнопки", callback_data=f"edit_button_url_{template.id}")],
        [InlineKeyboardButton(text="Изменить название второй кнопки", callback_data=f"edit_second_button_text_{template.id}")],    
        [InlineKeyboardButton(text="Изменить текст второй кнопки", callback_data=f"edit_second_button_reply_{template.id}")],   
    ]

    if template.photo_url or template.video_path:
        kb_buttons.append([InlineKeyboardButton(text="Изменить медиа", callback_data=f"edit_media_{template.id}")])

    kb_buttons.append([InlineKeyboardButton(text="Удалить шаблон", callback_data=f"delete_template_{template.id}")])
    kb_buttons.append([InlineKeyboardButton(text="Копировать шаблон", callback_data=f"copy_template_{template.id}")])
    kb_buttons.append([InlineKeyboardButton(text="Код шаблона", callback_data=f"template_share_code_{template.id}")])
    kb_buttons.append([InlineKeyboardButton(text="Назад", callback_data="my_templates")])

    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)

    if isinstance(callback_or_message, types.CallbackQuery) and callback_or_message.message:
        try:
            await callback_or_message.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        except Exception:
            await callback_or_message.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback_or_message.answer()
    else:
        await callback_or_message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.regexp(r"^template_\d+$"))
async def show_template_details(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await send_template_details(callback, template)

@router.callback_query(F.data.startswith("edit_after_start_"))
async def edit_after_start_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_after_start_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст после /start:</b>\n\n{template.after_start}\n\n"
        f"<b>Отправьте новый текст для замены или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_after_start_text)
async def save_new_after_start_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.html_text  

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.after_start = new_text
        await session.commit()

    await message.answer("<b>✅ Текст шаблона успешно обновлён!</b>", parse_mode="HTML") 

    await state.clear()

    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_non_premium_"))
async def edit_non_premium_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_non_premium_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст для не премиум пользователей:</b>\n\n{template.non_premium_text or '(пусто)'}\n\n"
        f"<b>Отправьте новый текст для замены или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_non_premium_text)
async def save_new_non_premium_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.html_text  

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.non_premium_text = new_text
        await session.commit()

    await message.answer("<b>✅ Текст не премиум успешно обновлён!</b>", parse_mode="HTML")

    await state.clear()

    await send_template_details(message, template)

@router.callback_query(F.data.regexp(r"^delete_template_\d+$"))
async def confirm_delete_template(callback: types.CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    user_id = callback.from_user.id

    async with Session() as session:
        template = await session.get(Template, template_id)

        if not template:
            await callback.answer("❌ Шаблон не найден.", show_alert=True)
            return
        
        query = (
            select(WorkerBot)
            .where(
                WorkerBot.template_id == template_id,
                WorkerBot.owner.has(telegram_id=user_id)
            )
        )
        result = await session.execute(query)
        bot_using_template = result.scalar_one_or_none()

        if bot_using_template:
            await callback.answer(
                f"⚠️ Этот шаблон привязан к боту @{bot_using_template.username} и не может быть удалён.",
                show_alert=True
            )
            return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Да", callback_data=f"delete_template_confirm_{template_id}"),
            InlineKeyboardButton(text="Нет", callback_data=f"template_{template_id}")
        ]
    ])

    text = f"Вы точно хотите удалить шаблон <b>{template.name}</b>?"
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.regexp(r"^delete_template_confirm_\d+$"))
async def delete_template(callback: types.CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            await callback.answer("❌ Шаблон уже удалён или не найден.", show_alert=True)
            return

        await session.delete(template)
        await session.commit()

    await callback.answer("✅ Шаблон успешно удалён.", show_alert=True)

    await show_my_templates(callback)

@router.callback_query(F.data.startswith("edit_media_"))
async def edit_media_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    if template.photo_url:
        await state.set_state(TemplateEdit.waiting_new_photo)
        await callback.message.edit_text(
            "<b>Отправьте новое фото для шаблона:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    elif template.video_path:
        await state.set_state(TemplateEdit.waiting_new_video)
        await callback.message.edit_text(
            "<b>Отправьте новый видеофайл:</b>",
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ У шаблона нет медиа для редактирования.", show_alert=True)
        return

    await callback.answer()

@router.message(TemplateEdit.waiting_new_photo, F.photo)
async def save_new_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")

    file_id = message.photo[-1].file_id
    file = await bot.get_file(file_id)
    file_path = f"temp_photo_{file_id}.jpg"
    await bot.download_file(file.file_path, destination=file_path)

    url = await upload_image_from_file(file_path)
    os.remove(file_path)

    if not url:
        await message.answer("❌ Не удалось загрузить фото на imgbb.")
        await state.clear()
        return

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден.")
            await state.clear()
            return
        template.photo_url = url
        await session.commit()

    await message.answer("<b>✅ Фото успешно обновлено!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.message(TemplateEdit.waiting_new_photo)
async def wrong_photo_input_edit(message: types.Message):
    await message.answer("<b>⚠️ Пожалуйста, отправьте именно фото.</b>", parse_mode="HTML")

@router.message(TemplateEdit.waiting_new_video, F.video)
async def save_new_video(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")

    async with Session() as session:
        stmt = select(Template).where(Template.id == template_id).options(selectinload(Template.owner))
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()
        if not template:
            await message.answer("❌ Шаблон не найден.")
            await state.clear()
            return

        admin = template.owner
        folder_path = os.path.join("Видео", str(admin.telegram_id))
        os.makedirs(folder_path, exist_ok=True)
        file_path = os.path.join(folder_path, f"{message.video.file_unique_id}.mp4")

        file = await bot.get_file(message.video.file_id)
        await bot.download_file(file.file_path, destination=file_path)

        template.video_path = file_path
        await session.commit()

    await message.answer("<b>✅ Видео успешно обновлено!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.message(TemplateEdit.waiting_new_video)
async def wrong_video_input_edit(message: types.Message):
    await message.answer("⚠️ Пожалуйста, отправьте видеофайл.", parse_mode="HTML")

@router.callback_query(F.data.startswith("edit_no_rights_"))
async def edit_no_rights_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_no_rights_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст если не выдал права:</b>\n\n{template.no_rights_text or '(пусто)'}\n\n"
        f"<b>Отправьте новый текст для замены или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_no_rights_text)
async def save_new_no_rights_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.html_text

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.no_rights_text = new_text
        await session.commit()

    await message.answer("<b>✅ Текст успешно обновлён!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_disconnect_"))
async def edit_disconnect_text_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_disconnect_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст при отключении:</b>\n\n{template.disconnect_text or '(пусто)'}\n\n"
        f"<b>Отправьте новый текст для замены или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_disconnect_text)
async def save_new_disconnect_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.html_text

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.disconnect_text = new_text
        await session.commit()

    await message.answer("<b>✅ Текст для отключения успешно обновлён!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_button_text_"))
async def edit_button_text_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_button_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст кнопки:</b>\n\n{template.button_text or '(пусто)'}\n\n"
        f"<b>Отправьте новый текст для кнопки или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_button_text)
async def save_new_button_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.text

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.button_text = new_text
        await session.commit()

    await message.answer("<b>✅ Текст кнопки успешно обновлён!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_button_url_"))
async def edit_button_url_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_button_url)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущая ссылка кнопки:</b>\n\n{template.button_url or '(пусто)'}\n\n"
        f"<b>Отправьте новую ссылку для кнопки или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_button_url)
async def save_new_button_url(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_url = message.text

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.button_url = new_url
        await session.commit()

    await message.answer("<b>✅ Ссылка кнопки успешно обновлена!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_second_button_reply_"))
async def edit_second_button_reply_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_second_button_reply)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущий текст второй кнопки:</b>\n\n{template.second_button_reply or '(пусто)'}\n\n"
        f"<b>Отправьте новый текст или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_second_button_text)
async def save_new_second_button_text(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.text

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.second_button_text = new_text
        await session.commit()

    await message.answer("<b>✅ Название второй кнопки успешно обновлено!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.startswith("edit_second_button_text_"))
async def edit_second_button_text_handler(callback: types.CallbackQuery, state: FSMContext):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

    if not template:
        await callback.answer("❌ Шаблон не найден.", show_alert=True)
        return

    await state.update_data(edit_template_id=template_id)
    await state.set_state(TemplateEdit.waiting_second_button_text)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
    ])

    await callback.message.edit_text(
        f"<b>Текущее название второй кнопки:</b>\n\n{template.second_button_text or '(пусто)'}\n\n"
        f"<b>Отправьте новое название или нажмите 'Назад' для отмены.</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateEdit.waiting_second_button_reply)
async def save_new_second_button_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    template_id = data.get("edit_template_id")
    if not template_id:
        await message.answer("❌ Ошибка: шаблон не найден в состоянии.")
        await state.clear()
        return

    new_text = message.html_text 

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await message.answer("❌ Шаблон не найден в базе.")
            await state.clear()
            return
        template.second_button_reply = new_text
        await session.commit()

    await message.answer("<b>✅ Текст второй кнопки успешно обновлён!</b>", parse_mode="HTML")
    await state.clear()
    await send_template_details(message, template)

@router.callback_query(F.data.regexp(r"^template_share_code_\d+$"))
async def show_template_share_code(callback: types.CallbackQuery):
    template_id = int(callback.data.split("_")[-1])

    async with Session() as session:
        template = await session.get(Template, template_id)
        if not template:
            await callback.answer("❌ Шаблон не найден.", show_alert=True)
            return
        if not template.share_code:
            template.share_code = str(uuid.uuid4())
            await session.commit()
    
    text = (
        f"<b>🔗 Код шаблона:</b>\n\n"
        f"<code>{template.share_code}</code>\n\n"
        "Отправь этот код другому пользователю, чтобы он мог импортировать твой шаблон."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data=f"template_{template_id}")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "enter_template_code")
async def ask_template_code(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TemplateImport.waiting_code)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Назад", callback_data="back_to_templates")]
        ]
    )
    await callback.message.edit_text(
        "<b>Введите код шаблона для импорта:</b>",
        reply_markup=kb,
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TemplateImport.waiting_code)
async def import_template_by_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    admin = await get_admin(message.from_user.id)
    if not admin:
        await message.answer("❌ Вы не зарегистрированы как воркер.", parse_mode="HTML")
        await state.clear()
        return

    async with Session() as session:
        stmt = select(Template).where(Template.share_code == code)
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            await message.answer("❌ Шаблон с таким кодом не найден.", parse_mode="HTML")
            await state.clear()
            return

        new_video_path = None
        if template.video_path and os.path.exists(template.video_path):
            folder = os.path.join("Видео", str(admin.telegram_id))
            os.makedirs(folder, exist_ok=True)
            ext = os.path.splitext(template.video_path)[-1]
            new_video_path = os.path.join(folder, f"{uuid.uuid4()}{ext}")
            shutil.copyfile(template.video_path, new_video_path)

        new_template = Template(
            name=template.name,
            after_start=template.after_start,
            non_premium_text=template.non_premium_text,
            no_rights_text=template.no_rights_text,
            disconnect_text=template.disconnect_text,
            button_text=template.button_text,
            button_url=template.button_url,
            second_button_text=template.second_button_text,
            second_button_reply=template.second_button_reply,
            video_path=new_video_path,   
            photo_url=template.photo_url,
            owner_id=admin.id,
            share_code=str(uuid.uuid4())
        )
        session.add(new_template)
        await session.commit()

    await message.answer("✅ Шаблон успешно добавлен!", parse_mode="HTML")
    await state.clear()
    await get_templates_main_menu(message)

@router.callback_query(F.data.startswith("copy_template_"))
async def copy_template_handler(callback: types.CallbackQuery):
    template_id = int(callback.data.split("_")[-1])
    tg_id = callback.from_user.id

    async with Session() as session:
        stmt = select(Template).where(
            Template.id == template_id,
            Template.owner.has(telegram_id=tg_id)
        )
        result = await session.execute(stmt)
        template = result.scalar_one_or_none()

        if not template:
            await callback.answer("❌ Шаблон не найден.", show_alert=True)
            return

        new_template = Template(
            name=f"{template.name} 📂",
            after_start=template.after_start,
            non_premium_text=template.non_premium_text,
            no_rights_text=template.no_rights_text,
            disconnect_text=template.disconnect_text,
            button_text=template.button_text,
            button_url=template.button_url,
            second_button_text=template.second_button_text,
            second_button_reply=template.second_button_reply,
            video_path=template.video_path,
            photo_url=template.photo_url,
            owner_id=template.owner_id,
            share_code=str(uuid.uuid4())
        )
        session.add(new_template)
        await session.commit()

    await callback.answer("📂 Копия шаблона создана!", show_alert=True)
    await send_template_details(callback, new_template)