import asyncio
import os
import time
from aiohttp import web
from sqlalchemy import select
from worker_webhook import register_worker_routes
from worker_bots import _bots
from db import engine, Base, Session
from config import WEBHOOK_HOST
import uvloop

from cache import set_all_tokens_for_port

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
print("[init] uvloop включён")

async def health_check(request: web.Request):
    port = os.getenv("WORKER_PORT", "8001")
    return web.json_response({"status": "ok", "port": port})

async def close_bot_sessions(app):
    start_time = time.perf_counter()
    print("[shutdown] Закрываю сессии ботов...")
    for token, bot in list(_bots.items()):
        try:
            await bot.session.close()
            print(f"[shutdown] Сессия закрыта для бота {token}")
        except Exception as e:
            print(f"[shutdown] Ошибка закрытия сессии {token}: {e}")
        finally:
            _bots.pop(token, None)
    elapsed = (time.perf_counter() - start_time) * 1000
    print(f"[shutdown] Все сессии закрыты за {elapsed:.1f} мс")

async def on_startup(app):
    port = int(os.getenv("WORKER_PORT", "8001"))
    print(f"[startup] Приложение запущено на порту {port}")
    print(f"[startup] WEBHOOK_HOST = {WEBHOOK_HOST}")

    from models import WorkerBot
    async with Session() as session:
        result = await session.execute(
            select(WorkerBot.token).where(WorkerBot.server_port == port)
        )
        tokens = [row[0] for row in result.all()]
    await set_all_tokens_for_port(port, tokens)
    print(f"[startup] В Redis обновлены {len(tokens)} токенов для порта {port}")

async def build_worker_app() -> web.Application:
    port = os.getenv("WORKER_PORT", "8001")
    try:
        print(f"[build_worker_app] Старт приложения на порту {port}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print(f"[build_worker_app] Таблицы БД готовы на порту {port}")
    except Exception as e:
        print(f"[build_worker_app] Ошибка инициализации базы данных на порту {port}: {e}")
        raise

    app = web.Application()
    app["webhook_host"] = WEBHOOK_HOST

    await register_worker_routes(app)
    app.router.add_get("/health", health_check)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(close_bot_sessions)
    return app

if __name__ == "__main__":
    port = int(os.getenv("WORKER_PORT", "8001"))
    try:
        web.run_app(build_worker_app(), host="0.0.0.0", port=port)
    except KeyboardInterrupt:
        print(f"[exit] Остановка приложения на порту {port}")
    except Exception as e:
        print(f"[main] Ошибка запуска на порту {port}: {e}")