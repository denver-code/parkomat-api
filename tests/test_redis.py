import asyncio

import redis.asyncio as redis

REDIS_URL = "redis://localhost:6379/0"


async def test_redis_reminders():
    print(f"--- Connecting to Redis at {REDIS_URL} ---")
    client = redis.from_url(REDIS_URL, decode_responses=True)

    try:
        await client.ping()
        print("✅ Connection: Success!")

        test_session_id = "test_session_123"
        interval = 20
        key = f"session:reminders:{test_session_id}"

        print(f"--- Testing Interval Tracking for {test_session_id} ---")

        await client.sadd(key, interval)
        await client.expire(key, 10)

        is_sent = await client.sismember(key, interval)
        print(f"✅ Interval {interval} recorded: {is_sent}")

        await client.sadd(key, 10)
        all_intervals = await client.smembers(key)
        print(f"✅ All intervals recorded: {all_intervals}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        await client.aclose()


asyncio.run(test_redis_reminders())
