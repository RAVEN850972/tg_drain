from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

router = Router()

def get_about_text_and_kb():
    text = (
        "<b>👩🏻‍💻 О нашем проекте</b>\n\n"
        "<b>🎉 Мы открылись 1 июля 2025</b>\n"
        "<b>☕️ Наш проект берет комиссию — каждая 4-я NFT идет админу</b>\n\n"
        "<b>✅ Состояние панели: 🟢 WORK</b>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📖 Мануалы", url="https://teletype.in/@bebe3414/fV4zvOsPKOs")],
        [
            InlineKeyboardButton(text="👑 Правила", callback_data="show_rules"),
            InlineKeyboardButton(text="♣️ Админ (тс)", url="https://t.me/Persilf")
        ],
        [
            InlineKeyboardButton(text="💬 Чат воркеров", url="https://t.me/+Y-csslTe-mtjYzZi")
        ],
        [
            InlineKeyboardButton(text="💸 Профиты", url="https://t.me/+czlUaC-SHldkOGNi"),
            InlineKeyboardButton(text="🔎 Парсер NFT", url="https://t.me/chekalsbot")
        ],
        [InlineKeyboardButton(text="⚡️ Отстук", url="https://t.me/AlphaSsquadBot")]
    ])
    return text, kb

@router.message(F.text == "👩🏼‍💻 О проекте")
async def about_handler(message: types.Message):
    if message.chat.type != "private":
        await message.answer("⛔ Доступно только в личке с ботом.")
        return

    text, kb = get_about_text_and_kb()
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "show_rules")
async def show_rules_handler(callback: types.CallbackQuery):
    text = (
        "<b>📜 Правила проекта</b>\n\n"
        "<b>1.</b> Запрещена реклама, флуд, спам, коммерция, продажа услуг или любых товаров в чате воркеров.\n\n"
        "<b>2.</b> Запрещено оскорблять других участников: воркеров, админов, модеров, тсов. "
        "Не разводите срач и не ведите себя неадекватно.\n\n"
        "<b>3.</b> Попрошайничество в любом виде — <b>строго запрещено</b>.\n\n"
        "<b>4.</b> <b>Скам или попытки скама</b> воркеров в любом виде — <u>мгновенный бан</u>.\n\n"
        "<b>5.</b> <b>В чате запрещена отправка 18+ контента</b> — моментальный бан.\n\n"
        "<i>Соблюдение этих простых правил — залог спокойной и продуктивной работы 👌</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Назад", callback_data="back_to_about")]
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_about")
async def back_to_about(callback: types.CallbackQuery):
    text, kb = get_about_text_and_kb()
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()