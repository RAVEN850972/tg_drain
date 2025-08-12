import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PATH, LOG_WEBHOOK_PATH
from db import engine, Base
from log_bot import setup_log_bot
from chat_config import setup_panel_chat, router as chat_router
from add_worker_bot import router as add_bot_router
from start_menu import router as start_router
from profilee import router as profile_router
from templates import router as templates_router
from settings import router as settings_router
from about import router as about_router
from stat_handler import router as stat_router
from admin_panel import admin_router
from inline_templates_menu import router as inline_tpl_router
from referral import router as referral_router
from business_connections import router as business_router
from panel_poster import panel_poster_loop
from check_worker_bots import check_worker_bots_loop
from daily_report import daily_report_task

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher(storage=MemoryStorage())

dp.include_router(add_bot_router)
dp.include_router(start_router)
dp.include_router(profile_router)
dp.include_router(templates_router)
dp.include_router(settings_router)
dp.include_router(about_router)
dp.include_router(stat_router)
dp.include_router(chat_router)
dp.include_router(admin_router)
dp.include_router(inline_tpl_router)
dp.include_router(referral_router)
dp.include_router(business_router)

async def set_menu_button_and_commands(bot: Bot):
    commands = [
        BotCommand(command="/start", description="Перезапустить бота"),
        BotCommand(command="/stat", description="Статистика"),
        BotCommand(command="/top", description="Топ 10 по NFT"),
        BotCommand(command="/topday", description="Топ NFT за день"),
        BotCommand(command="/topstars", description="Топ 10 по звёздам"),
        BotCommand(command="/topstarsday", description="Топ звёзд за день"),
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_HOST + WEBHOOK_PATH)
    await set_menu_button_and_commands(bot)
    await setup_panel_chat(bot)
    print(f"[on_startup] Webhook основного бота установлен: {WEBHOOK_HOST + WEBHOOK_PATH}")

    app["check_worker_task"] = asyncio.create_task(check_worker_bots_loop())
    app["daily_report_task"] = asyncio.create_task(daily_report_task(bot))

    log_bot, log_dp = await setup_log_bot()
    app["log_bot"] = log_bot
    app["log_dp"] = log_dp

    SimpleRequestHandler(dispatcher=log_dp, bot=log_bot).register(app, path=LOG_WEBHOOK_PATH)
    await log_bot.set_webhook(WEBHOOK_HOST + LOG_WEBHOOK_PATH)
    print(f"[on_startup] LogBot webhook установлен: {WEBHOOK_HOST + LOG_WEBHOOK_PATH}")
    app["panel_poster_task"] = asyncio.create_task(panel_poster_loop())

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()
    if "log_bot" in app:
        await app["log_bot"].delete_webhook()

    for key in ["check_worker_task", "panel_poster_task", "daily_report_task"]:
        task = app.get(key)
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

async def build_app() -> web.Application:
    print("[build_app] Старт")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[build_app] Таблицы БД готовы")

    app = web.Application()
    app["webhook_host"] = WEBHOOK_HOST

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    return app

if __name__ == "__main__":
    web.run_app(build_app(), host="0.0.0.0", port=3000)