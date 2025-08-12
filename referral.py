from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from db import Session
from models import Admin

router = Router()

BOT_USERNAME = "Alphasqquad_bot"
REFERRALS_PER_PAGE = 7

@router.callback_query(F.data.startswith("referral"))
async def referral_handler(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    page = int(parts[1]) if len(parts) > 1 else 1

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{callback.from_user.id}"

    async with Session() as session:
        admin = (await session.execute(
            select(Admin).where(Admin.telegram_id == callback.from_user.id)
        )).scalar_one_or_none()
        if not admin:
            await callback.message.edit_text("Профиль не найден.")
            return

        referrals = (await session.execute(
            select(Admin).where(Admin.referred_by == admin.telegram_id)
        )).scalars().all()
        referrals_count = len(referrals)

        total_nft = sum(getattr(ref, "gifts_unique_sent", 0) or 0 for ref in referrals)
        total_stars = sum(getattr(ref, "stars_sent", 0) or 0 for ref in referrals)
        
        total = referrals_count
        pages = (total + REFERRALS_PER_PAGE - 1) // REFERRALS_PER_PAGE or 1
        page = max(1, min(page, pages))
        start = (page - 1) * REFERRALS_PER_PAGE
        end = start + REFERRALS_PER_PAGE
        page_refs = referrals[start:end]

        if referrals:
            referrals_text = "<b>Твои рефералы:</b>\n\n"
            for ref in page_refs:
                line = f"• <b>ID:</b> <code>{ref.telegram_id}</code>"
                if ref.username:
                    line += f" | <b>@{ref.username}</b>"
                line += (
                    f" | 🎆 <b>{getattr(ref, 'gifts_unique_sent', 0)}</b>"
                    f" | ⭐️ <b>{getattr(ref, 'stars_sent', 0)}</b>"
                )
                referrals_text += line + "\n"
        else:
            referrals_text = "У тебя пока нет рефералов.\n\n"

    text = (
        f"<b>🚀 Твоя реферальная ссылка:</b>\n"
        f"<code>{ref_link}</code>\n\n"
        f"<b>💁🏻‍♀️ Рефералов: {referrals_count}</b>\n\n"
        f"{referrals_text}\n"
        f"📊 <b>Общая статистика рефералов:</b>\n"
        f"• 🎆 NFT: <b>{total_nft}</b>\n"
        f"• ⭐️ Звёзд: <b>{total_stars}</b>\n\n"
        "<blockquote>"
        f"<b>Как работает рефералка и зачем она нужна?</b>\n"
        f"Каждый твой реферал помогает тебе снижать комиссию.\n"
        f"Когда твои рефералы суммарно сделают 15 успешных переводов NFT, твоя комиссия отключится на 20 часов.\n"
        f"Отправь свою ссылку другу — если он перейдет и запустит бота по ней, ты увидишь его тут!\n"
        "</blockquote>"
    )

    nav = [
        InlineKeyboardButton(text="<", callback_data=f"referral:{page-1}" if page > 1 else "ignore"),
        InlineKeyboardButton(text=f"{page}/{pages}", callback_data="ignore"),
        InlineKeyboardButton(text=">", callback_data=f"referral:{page+1}" if page < pages else "ignore")
    ]
    buttons = [nav, [InlineKeyboardButton(text="Назад", callback_data="back_to_profile")]]

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery, state: FSMContext):
    from profilee import build_profile_text_and_kb
    text, kb = await build_profile_text_and_kb(callback.from_user.id)
    if text:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()