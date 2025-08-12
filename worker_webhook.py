import asyncio
import os
from datetime import datetime
from aiohttp import web
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from worker_bots import get_cached_bot, _bots
from bot_handlers import handle_update, handle_update_with_cache
from worker_bots import handle_webhook_business_connection, handle_webhook_inline_query
from aiogram.exceptions import TelegramUnauthorizedError
from cache import get_token_port, get_tokens_for_port
from db import Session
from models import WorkerBot

WEBHOOK_RATE_LIMIT = 25

# Очередь апдейтов и пул воркеров
update_queue = asyncio.Queue(maxsize=1000)
WORKER_POOL_SIZE = 5
MAX_UPDATE_AGE = 30  # секунд

# Кэш WorkerBot
worker_bot_cache = {}
WORKER_BOT_CACHE_TTL = 5  # секунд

async def webhook_handler(request: web.Request):
    token = request.match_info.get("token")
    port = int(os.getenv("WORKER_PORT", "8001"))

    token_port = await get_token_port(token)
    if not token_port:
        print(f"[WebhookHandler] Неизвестный токен: {token} на порту {port}")
        return web.json_response({"error": "Unknown token"}, status=403)
    if token_port != port:
        print(f"[WebhookHandler] Токен {token} принадлежит порту {token_port}, текущий порт {port}")
        return web.json_response({"error": "Invalid server port"}, status=403)

    try:
        data = await request.json()
    except Exception as e:
        print(f"[WebhookHandler] Ошибка разбора JSON для токена {token} на порту {port}: {e}")
        return web.json_response({"error": "Invalid JSON"}, status=400)

    bot = get_cached_bot(token)
    if not bot:
        print(f"[WebhookHandler] Бот для токена {token} не найден в кеше на порту {port}")
        return web.json_response({"error": "Unknown token"}, status=403)

    # Добавляем апдейт в очередь с меткой времени
    try:
        await update_queue.put({
            'data': data,
            'bot': bot,
            'token': token,
            'timestamp': datetime.now()
        })
    except asyncio.QueueFull:
        print(f"[WebhookHandler] Очередь переполнена для токена {token}")
        return web.json_response({"error": "Queue full"}, status=503)

    return web.Response(status=200)

async def get_cached_worker_bot(token: str):
    cache_key = token
    cached = worker_bot_cache.get(cache_key)
    
    if cached and (datetime.now() - cached['timestamp']).seconds < WORKER_BOT_CACHE_TTL:
        return cached['data']
    
    async with Session() as session:
        worker_bot = await session.scalar(
            select(WorkerBot)
            .where(WorkerBot.token == token)
            .options(selectinload(WorkerBot.template))
        )
        
        if worker_bot:
            worker_bot_cache[cache_key] = {
                'data': {
                    'id': worker_bot.id,
                    'owner_id': worker_bot.owner_id,
                    'template_id': worker_bot.template_id,
                    'base_template_id': worker_bot.base_template_id,
                    'username': worker_bot.username,
                    'template': worker_bot.template
                },
                'timestamp': datetime.now()
            }
            return worker_bot_cache[cache_key]['data']
    
    return None

async def update_worker(worker_id: int):
    while True:
        try:
            update_data = await update_queue.get()
            
            # Фильтрация старых апдейтов
            age = (datetime.now() - update_data['timestamp']).seconds
            if age > MAX_UPDATE_AGE:
                continue
            
            data = update_data['data']
            bot = update_data['bot']
            token = update_data['token']
            
            # Используем кэшированные данные WorkerBot
            worker_bot_data = await get_cached_worker_bot(token)
            if not worker_bot_data:
                continue
            
            try:
                if "inline_query" in data:
                    await handle_webhook_inline_query(data, bot, token, None)
                else:
                    await handle_webhook_business_connection(data, bot)
                    await handle_update_with_cache(data, bot, _bots, worker_bot_data)
                    
            except TelegramUnauthorizedError:
                print(f"[Worker-{worker_id}] Удалённый/невалидный бот {token}")
                _bots.pop(token, None)
                worker_bot_cache.pop(token, None)
            except Exception as e:
                print(f"[Worker-{worker_id}] Ошибка обработки: {e}")
                
        except Exception as e:
            print(f"[Worker-{worker_id}] Критическая ошибка: {e}")
            await asyncio.sleep(0.1)

async def setup_webhooks(webhook_host: str, port: str):
    tokens = await get_tokens_for_port(int(port))
    print(f"[setup_webhooks] Найдено {len(tokens)} воркеров для порта {port}")

    semaphore = asyncio.Semaphore(WEBHOOK_RATE_LIMIT)

    async def setup_for_worker(token: str):
        async with semaphore:
            bot = get_cached_bot(token)
            if not bot:
                return
            try:
                # Добавляем drop_pending_updates=True
                await bot.set_webhook(
                    f"{webhook_host}/webhook/{token}",
                    drop_pending_updates=True
                )
                print(f"[setup_webhooks] Webhook установлен для {token}")
            except Exception as e:
                print(f"[setup_webhooks] Ошибка для {token}: {e}")

    await asyncio.gather(*[setup_for_worker(token) for token in tokens])
    
    # Запускаем пул воркеров для обработки очереди
    for i in range(WORKER_POOL_SIZE):
        asyncio.create_task(update_worker(i))
    
    print(f"[setup_webhooks] Запущено {WORKER_POOL_SIZE} воркеров для обработки очереди")
