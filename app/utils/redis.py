import redis.asyncio as redis

from app.core.config import config


class RedisManager:
    def __init__(self):
        self.client: redis.Redis = None

    async def connect(self):
        self.client = redis.from_url(
            f"redis://{config.REDIS_HOST}:{config.REDIS_PORT}",
            decode_responses=True,
            max_connections=10,  # Cap connections
        )

    async def disconnect(self):
        if self.client:
            await self.client.close()


manager = RedisManager()


async def init_redis():
    await manager.connect()


async def close_redis():
    await manager.disconnect()


def get_redis():
    return manager.client


async def mark_reminder_sent(session_id: str, interval: int):
    key = f"session:reminders:{session_id}"
    await manager.client.sadd(key, interval)
    await manager.client.expire(key, 86400)


async def is_reminder_sent(session_id: str, interval: int) -> bool:
    key = f"session:reminders:{session_id}"
    return await manager.client.sismember(key, interval)
