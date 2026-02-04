import httpx

from app.core.config import config


async def send_telegram_msg(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json=payload)
        print("response ", r)
