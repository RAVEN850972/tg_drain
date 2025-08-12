import aiohttp
import base64

IMGBB_API_KEY = "472c48e931ec66bef2ce569d9ce545a7"
IMGBB_API_URL = "https://api.imgbb.com/1/upload"

async def upload_image_from_file(file_path: str, name: str = None, expiration: int = None) -> str | None:
    with open(file_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()
    data = {"key": IMGBB_API_KEY, "image": image_data}
    if name:
        data["name"] = name
    if expiration:
        data["expiration"] = str(expiration)
    async with aiohttp.ClientSession() as session:
        async with session.post(IMGBB_API_URL, data=data) as resp:
            res = await resp.json()
            if res.get("success"):
                return res["data"]["url"]
            else:
                print("[IMGBB API ERROR]", res)
                return None

async def upload_image_from_url(img_url: str, name: str = None, expiration: int = None) -> str | None:
    data = {"key": IMGBB_API_KEY, "image": img_url}
    if name:
        data["name"] = name
    if expiration:
        data["expiration"] = str(expiration)
    async with aiohttp.ClientSession() as session:
        async with session.post(IMGBB_API_URL, data=data) as resp:
            res = await resp.json()
            if res.get("success"):
                return res["data"]["url"]
            else:
                print("[IMGBB API ERROR]", res)
                return None