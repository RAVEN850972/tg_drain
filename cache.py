import redis.asyncio as aioredis
import json
from models import Template

#REDIS_URL = "redis://localhost:6379/0"
REDIS_URL = "rediss://default:Act4AAIjcDFkNTNjOWMxZjliNGI0OTAyYTQ2ZTEyYzc0NTViODk5OHAxMA@adapted-trout-52088.upstash.io:6379"


redis = aioredis.from_url(REDIS_URL, decode_responses=True)
TEMPLATE_CACHE_TTL = 3600  
VIDEO_FILEID_TTL = 7 * 24 * 3600  
TOKEN_CACHE_TTL = 864000

def serialize_template(template: Template):
    return {
        "id": template.id,
        "name": template.name,
        "after_start": template.after_start,
        "non_premium_text": template.non_premium_text,
        "no_rights_text": template.no_rights_text,
        "disconnect_text": template.disconnect_text,
        "video_path": template.video_path,
        "photo_url": template.photo_url,
        "button_text": template.button_text,
        "button_url": template.button_url,
        "second_button_text": template.second_button_text,
        "second_button_reply": template.second_button_reply,
        "owner_id": template.owner_id,
        "share_code": template.share_code,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "reply_markup": template.reply_markup if hasattr(template, "reply_markup") else None
    }

def unserialize_template(data: str):
    return json.loads(data)

def get_cache_key(template_id: int, owner_id: int | None):
    return f"template:{template_id}:admin:{owner_id}"

async def get_template_cached(session, template_id: int, owner_id: int | None):
    if not template_id:
        return None

    key = get_cache_key(template_id, owner_id)
    data = await redis.get(key)
    if data:
        return unserialize_template(data)

    template = await session.get(Template, template_id)
    if template and template.owner_id == owner_id:
        ser = serialize_template(template)
        await redis.set(key, json.dumps(ser), ex=TEMPLATE_CACHE_TTL)
        return ser

    return None

async def invalidate_template_cache(template_id: int, owner_id: int | None):
    await redis.delete(get_cache_key(template_id, owner_id))

def video_fileid_cache_key(worker_bot_id, video_path):
    return f"video_fileid:{worker_bot_id}:{video_path}"

async def get_cached_video_fileid(worker_bot_id, video_path):
    key = video_fileid_cache_key(worker_bot_id, video_path)
    return await redis.get(key)

async def set_cached_video_fileid(worker_bot_id, video_path, file_id):
    key = video_fileid_cache_key(worker_bot_id, video_path)
    await redis.set(key, file_id, ex=VIDEO_FILEID_TTL)

async def invalidate_video_fileid(worker_bot_id, video_path):
    key = video_fileid_cache_key(worker_bot_id, video_path)
    await redis.delete(key)

async def get_token_port(token: str) -> int | None:
    port = await redis.get(f"bot:{token}")
    return int(port) if port else None

async def set_token_port(token: str, port: int):
    await redis.set(f"bot:{token}", port, ex=TOKEN_CACHE_TTL)

async def del_token_port(token: str):
    await redis.delete(f"bot:{token}")

async def get_tokens_for_port(port: int) -> list[str]:
    return await redis.smembers(f"port:{port}:tokens")

async def add_token_for_port(port: int, token: str):
    await set_token_port(token, port)
    await redis.sadd(f"port:{port}:tokens", token)
    await redis.expire(f"port:{port}:tokens", TOKEN_CACHE_TTL)

async def remove_token_from_port(port: int, token: str):
    await del_token_port(token)
    await redis.srem(f"port:{port}:tokens", token)

async def clear_all_tokens_for_port(port: int):
    tokens = await get_tokens_for_port(port)
    pipe = redis.pipeline()
    for token in tokens:
        pipe.delete(f"bot:{token}")
        pipe.srem(f"port:{port}:tokens", token)
    await pipe.execute()

async def set_all_tokens_for_port(port: int, tokens: list[str]):
    await clear_all_tokens_for_port(port)
    if tokens:
        pipe = redis.pipeline()
        for token in tokens:
            pipe.set(f"bot:{token}", port, ex=TOKEN_CACHE_TTL)
            pipe.sadd(f"port:{port}:tokens", token)
            pipe.expire(f"port:{port}:tokens", TOKEN_CACHE_TTL)
        await pipe.execute()