import asyncio
from datetime import datetime, timedelta, timezone

from app.utils.redis import is_reminder_sent, mark_reminder_sent
from app.utils.telegram import send_telegram_msg
from models.models import Car, ParkingLocation, ParkingSession, ParkingSessionStatus


async def schedule_reminders(user_chat_id: str, end_time: datetime, session_id: str):
    if end_time.tzinfo is None:
        end_time = end_time.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    total_duration = (end_time - now).total_seconds() / 60

    if total_duration >= 30:
        intervals = [20, 10, 0]
    elif total_duration >= 15:
        intervals = [10, 5, 0]
    else:
        intervals = [int(total_duration * 0.5), int(total_duration * 0.2), 0]

    intervals.sort(reverse=True)

    for minutes_left in intervals:
        if await is_reminder_sent(session_id, minutes_left):
            continue

        trigger_time = end_time - timedelta(minutes=minutes_left)
        delay = (trigger_time - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        session = await ParkingSession.get(session_id)
        if not session or session.status != ParkingSessionStatus.ACTIVE:
            return

        car = await Car.get(session.car_id)
        parking_location = await ParkingLocation.get(session.parking_location_id)

        car_plate = car.license_plate if car else "your car"
        lat, lgn = session.car_location["coordinates"]
        loc_name = (
            parking_location.location_name if parking_location else f"{lat}, {lgn}"
        )

        msg = (
            f"🚨Your parking of {car_plate} at {loc_name} has expired!"
            if minutes_left == 0
            else f"⚠️ <b>{minutes_left}m left!</b> at {loc_name} for your {car_plate} car!"
        )

        await send_telegram_msg(user_chat_id, msg)
        await mark_reminder_sent(session_id, minutes_left)

        if minutes_left == 0:
            session.status = ParkingSessionStatus.COMPLETED
            await session.save()
