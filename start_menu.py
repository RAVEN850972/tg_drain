import random
from aiogram import types, F, Router
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from db import Session
from models import Admin, Application
from config import PANEL_OWNERS

router = Router()

class ApplicationState(StatesGroup):
    captcha = State()
    project_source = State()
    scam_experience = State()
    work_time = State()
    goals = State()

CAPTCHA_EMOJIS = [
    "🍭", "❤️", "🐸", "🐰", "⚡️", "🎁", "☔️", "☂️",
    "🌈", "💡", "🍀", "🔥", "🧊", "🌙", "🎯", "💎",
    "🦄", "🐳", "🧠", "🕹"
]

def generate_captcha():
    emojis = random.sample(CAPTCHA_EMOJIS, 8)
    correct = random.choice(emojis)
    buttons = [
        InlineKeyboardButton(
            text=e,
            callback_data="captcha_pass" if e == correct else "captcha_fail"
        ) for e in emojis
    ]
    random.shuffle(buttons)
    markup = InlineKeyboardMarkup(inline_keyboard=[
        buttons[:4],
        buttons[4:]
    ])
    return correct, markup

def parse_ref_id(text):
    if text.startswith("/start ref_"):
        try:
            return int(text.split("ref_")[1].split()[0])
        except:
            return None
    return None

@router.message(F.text.regexp(r"^/start(\s+ref_\d+)?$"))
async def start_handler(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        await message.answer(
            "⛔️ Используй этого бота только в личке.",
            reply_markup=ReplyKeyboardRemove()
        )
        return

    await state.clear()
    tg_user = message.from_user
    ref_id = parse_ref_id(message.text.strip())

    async with Session() as session:
        ids = [tg_user.id]
        if ref_id and ref_id != tg_user.id:
            ids.append(ref_id)
        result = await session.execute(select(Admin).where(Admin.telegram_id.in_(ids)))
        users = {adm.telegram_id: adm for adm in result.scalars().all()}
        admin = users.get(tg_user.id)
        ref_owner = users.get(ref_id) if ref_id and ref_id != tg_user.id else None
        is_new = False

        if not admin:
            admin = Admin(
                telegram_id=tg_user.id,
                first_name=tg_user.first_name,
                last_name=tg_user.last_name,
                username=tg_user.username,
                referred_by=ref_id if ref_id and ref_id != tg_user.id else None
            )
            session.add(admin)
            is_new = True
        else:
            updated = False
            if admin.first_name != tg_user.first_name:
                admin.first_name = tg_user.first_name
                updated = True
            if admin.last_name != tg_user.last_name:
                admin.last_name = tg_user.last_name
                updated = True
            if admin.username != tg_user.username:
                admin.username = tg_user.username
                updated = True
            if updated:
                session.add(admin)

        if is_new and ref_owner:
            ref_owner.referrals_count = (ref_owner.referrals_count or 0) + 1
            session.add(ref_owner)
            try:
                await message.bot.send_message(
                    ref_id,
                    f"🎉 <b>У тебя новый реферал!</b>\n"
                    f"<b>💁🏻‍♀️ Имя:</b> <b>{tg_user.first_name or '-'} {tg_user.last_name or ''}</b>\n"
                    f"<b>💁🏻‍♀️ Тэг: @{tg_user.username or '-'}</b>\n"
                    f"<b>💁🏻‍♀️ ID:</b> <code>{tg_user.id}</code>",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"[WARN] Не удалось отправить уведомление рефералу {ref_id}: {e}")

        await session.commit()

        # ОСНОВНОЕ МЕНЮ
        if tg_user.id in PANEL_OWNERS or (admin and admin.is_accepted):
            kb = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
                [KeyboardButton(text="💁🏻‍♀️ Мой профиль"), KeyboardButton(text="⚙️ Настройки")],
                [KeyboardButton(text="🤖 Боты"), KeyboardButton(text="🧩 Шаблоны")],
                [KeyboardButton(text="⚡️ Inline Mod"), KeyboardButton(text="👩🏼‍💻 О проекте")],
                [KeyboardButton(text="🏢 Бизнес Коннекты")]
            ])
            await message.answer(
                "<b>👋 Привет, рады тебя видеть!</b>\n\n"
                "<b>Вступай в наш</b> <a href='https://t.me/+PJVvLxYCft8xYTky'>чатик</a>",
                parse_mode="HTML",
                reply_markup=kb
            )
            return

        stmt = select(Application).where(Application.telegram_id == tg_user.id, Application.status == "pending")
        result = await session.execute(stmt)
        existing_app = result.scalar_one_or_none()

        if existing_app:
            await message.answer("<b>⌛️ Ваша заявка в ожидании рассмотрения, подождите.</b>", parse_mode="HTML")
            return

        emoji, markup = generate_captcha()
        msg = await message.answer(
            f"<b>👋 Привет, чтобы перейти к заполнению анкеты нажми на кнопку с эмодзи {emoji}</b>",
            reply_markup=markup,
            parse_mode="HTML"
        )
        await state.set_state(ApplicationState.captcha)
        await state.update_data(captcha_correct=emoji, captcha_msg_id=msg.message_id)

@router.callback_query(ApplicationState.captcha)
async def handle_captcha(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    correct = data.get("captcha_correct")
    if callback.data == "captcha_pass" and callback.message.reply_markup:
        await callback.message.delete()
        await callback.message.answer(
            "<b>1️⃣ Первым делом расскажи откуда ты узнал о нас?</b>",
            parse_mode="HTML"
        )
        await state.set_state(ApplicationState.project_source)
    else:
        new_emoji, new_markup = generate_captcha()
        await state.update_data(captcha_correct=new_emoji)
        try:
            await callback.message.edit_text(
                f"<b>👋 Привет, чтобы перейти к заполнению анкеты нажми на кнопку с эмодзи {new_emoji}</b>",
                reply_markup=new_markup,
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"[WARN] Не удалось отредактировать капчу: {e}")
        await callback.answer("❌ Неверно. Попробуйте снова!")

@router.message(ApplicationState.project_source)
async def process_project_source(message: types.Message, state: FSMContext):
    await state.update_data(project_source=message.text)
    await message.answer(
        "<b>2️⃣ Отлично, а был ли у тебя опыт? Если да то какой опыт?</b>",
        parse_mode="HTML"
    )
    await state.set_state(ApplicationState.scam_experience)

@router.message(ApplicationState.scam_experience)
async def process_scam_experience(message: types.Message, state: FSMContext):
    await state.update_data(scam_experience=message.text)
    await message.answer(
        "<b>3️⃣ А сколько времени ты готов уделять работе в нашем проекте?</b>",
        parse_mode="HTML"
    )
    await state.set_state(ApplicationState.work_time)

@router.message(ApplicationState.work_time)
async def process_work_time(message: types.Message, state: FSMContext):
    await state.update_data(work_time=message.text)
    await message.answer(
        "<b>4️⃣ И на последок, какие цели ты преследуешь?</b>",
        parse_mode="HTML"
    )
    await state.set_state(ApplicationState.goals)

@router.message(ApplicationState.goals)
async def process_goals(message: types.Message, state: FSMContext):
    from_user = message.from_user
    data = await state.get_data()

    async with Session() as session:
        app = Application(
            telegram_id=from_user.id,
            first_name=from_user.first_name,
            last_name=from_user.last_name,
            username=from_user.username,
            project_source=data.get("project_source"),
            scam_experience=data.get("scam_experience"),
            work_time=data.get("work_time"),
            goals=message.text,
            status="pending"
        )
        session.add(app)
        await session.commit()

        await message.answer("<b>✅ Заявка отправлена!</b>", parse_mode="HTML")
        await state.clear()
        
        for admin_id in PANEL_OWNERS:
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_app:{app.id}"),
                    InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_app:{app.id}")
                ]
            ])

            text = (
                f"<b>📥 Новая заявка #{app.id}</b>\n\n"
                f"<b>👤 ID: </b><code>{app.telegram_id}</code>\n"
                f"<b>👤 Тег: </b><b>@{app.username or 'нету'}</b>\n"
                f"<b>👤 Имя: </b><b>{app.first_name or 'нету'}</b>\n"
                f"<b>1️⃣ Откуда узнал:</b> <b>{app.project_source}</b>\n"
                f"<b>2️⃣ Опыт:</b> <b>{app.scam_experience}</b>\n"
                f"<b>3️⃣ Время на проект:</b> <b>{app.work_time}</b>\n"
                f"<b>4️⃣ Цели:</b> <b>{app.goals}</b>"
            )

            try:
                await message.bot.send_message(
                    admin_id,
                    text,
                    reply_markup=markup,
                    parse_mode="HTML",
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"[WARN] Не удалось отправить заявку админу {admin_id}: {e}")