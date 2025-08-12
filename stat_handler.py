from config import PANEL_OWNERS  
from aiogram import types, F, Router 
from sqlalchemy import select
from db import Session
from models import Admin
from stat_utils import (
    send_admin_and_global_stats,
    send_top_admins_by_nft,
    send_top_admins_by_daily_nft,
    send_top_admins_by_total_stars,
    send_top_admins_by_daily_stars,
    send_top_admins_by_users_count,
    send_top_admins_by_users_today,
)

router = Router()

async def is_accepted(user_id):
    if user_id in PANEL_OWNERS:
        return True
    async with Session() as session:
        admin = (await session.execute(
            select(Admin).where(Admin.telegram_id == user_id)
        )).scalar_one_or_none()
        return admin and admin.is_accepted

@router.message(F.text == "/stat")
async def stat_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_admin_and_global_stats(message)

@router.message(F.text == "/top")
async def top_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_nft(message)

@router.message(F.text == "/topday")
async def top_day_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_daily_nft(message)

@router.message(F.text == "/topstars")
async def top_stars_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_total_stars(message)

@router.message(F.text == "/topstarsday")
async def top_stars_day_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_daily_stars(message)

@router.message(F.text == "/topmamonts")
async def top_users_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_users_count(message)

@router.message(F.text == "/topmamontsday")
async def top_users_day_handler(message: types.Message):
    if not await is_accepted(message.from_user.id):
        await message.answer("<b>⛔️ Доступ только после принятия в команду!</b>", parse_mode="HTML")
        return
    await send_top_admins_by_users_today(message)