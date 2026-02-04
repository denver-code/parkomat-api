import asyncio
from datetime import datetime, timedelta, timezone

from beanie import PydanticObjectId

from app.utils.telegram import send_telegram_msg
from models.models import Car, ParkingLocation, ParkingSession, ParkingSessionStatus


async def schedule_reminders(
    user_chat_id: str, end_time: datetime, session_id: PydanticObjectId
):
    """
    This function lives in the background and waits for the specific
    milestones (20m, 10m, 0m) to trigger Telegram alerts.
    """
    intervals = [20, 10, 0]

    for minutes_left in intervals:
        now = datetime.now(timezone.utc)
        trigger_time = end_time - timedelta(minutes=minutes_left)
        delay = (trigger_time - now).total_seconds()

        if delay > 0:
            await asyncio.sleep(delay)

            session = await ParkingSession.get(session_id)
            if not session or session.status != ParkingSessionStatus.ACTIVE:
                break
            car = Car.get(session.car_id)
            parking_location = ParkingLocation.get(session.parking_location_id)

            if not car or not parking_location:
                continue

            msg = (
                f"🚨Your parking of {car.license_plate} at {parking_location.name} has expired!"
                if minutes_left == 0
                else f"⚠️ <b>{minutes_left}m left!</b> at {parking_location.name} for your {car.license_plate} car!"
            )
            await send_telegram_msg(user_chat_id, msg)

            if minutes_left == 0:
                session.status = ParkingSessionStatus.COMPLETED
                await session.save()
