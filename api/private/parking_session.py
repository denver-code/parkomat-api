import asyncio
import os
from datetime import datetime, time, timedelta, timezone
from io import BytesIO
from typing import Optional

from beanie import PydanticObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from PIL import Image

from app.core.config import config
from app.core.jwt import FastJWT
from app.utils.telegram import send_telegram_msg
from models.models import Car, ParkingLocation, ParkingSession, ParkingSessionStatus

session_router = APIRouter(prefix="/session", tags=["Parking Sessions"])

SESSION_UPLOAD_DIR = "static/sessions"


@session_router.post("")
async def create_parking_session(
    background_tasks: BackgroundTasks,
    car_id: str = Form(...),
    parking_location_id: Optional[str] = Form(None),
    manual_max_stay_mins: Optional[int] = Form(None),
    lat: float = Form(...),
    lng: float = Form(...),
    photo: UploadFile = File(...),
    user=Depends(FastJWT().login_required),
):
    car = await Car.find_one(Car.id == PydanticObjectId(car_id), Car.user_id == user.id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found in your garage")

    start_time = datetime.now(timezone.utc)
    calculated_end_time = None

    if parking_location_id:
        location = await ParkingLocation.get(PydanticObjectId(parking_location_id))
        if not location:
            raise HTTPException(status_code=404, detail="Parking location not found")

        stay_duration = location.max_stay if location.max_stay else 1440
        calculated_end_time = start_time + timedelta(minutes=stay_duration)
    else:
        if not manual_max_stay_mins:
            raise HTTPException(
                status_code=400,
                detail="Manual stay time required if location is not selected",
            )
        calculated_end_time = start_time + timedelta(minutes=manual_max_stay_mins)

    session = ParkingSession(
        user_id=user.id,
        car_id=car.id,
        car_location={"type": "Point", "coordinates": [lng, lat]},
        parking_location_id=PydanticObjectId(parking_location_id)
        if parking_location_id
        else None,
        start_time=start_time,
        end_time=calculated_end_time,
        status=ParkingSessionStatus.ACTIVE,
    )
    await session.insert()

    if user.telegram_chat_id:
        from app.utils.reminders import schedule_reminders

        asyncio.create_task(
            schedule_reminders(user.telegram_chat_id, session.end_time, str(session.id))
        )
        parking_location = None
        if parking_location_id:
            parking_location = await ParkingLocation.get(parking_location_id)

        await send_telegram_msg(
            user.telegram_chat_id,
            f"Your parking session {f'at {parking_location.name} ' if parking_location else ''}for {car.license_plate} that lasts {manual_max_stay_mins} minutes has started.",
        )

    filename = f"{user.id}-{session.id}.jpg"
    file_path = os.path.join(SESSION_UPLOAD_DIR, filename)

    try:
        content = await photo.read()
        with Image.open(BytesIO(content)) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(file_path, "JPEG", quality=45)
    except Exception:
        await session.delete()
        raise HTTPException(status_code=400, detail="Failed to process proof photo")

    return {
        "session_id": str(session.id),
        "car_plate": car.license_plate,
        "ends_at": session.end_time,
        "photo_url": f"{config.API_BASE_URL}/api/static/sessions/{filename}",
        "end_time": session.end_time,
    }


@session_router.get("")
async def get_sessions(
    status: Optional[str] = None,
    car_reg: Optional[str] = None,
    date: Optional[datetime] = None,
    user=Depends(FastJWT().login_required),
):
    query_filter = {"user_id": user.id}

    if car_reg:
        car = await Car.find_one(
            Car.user_id == user.id, Car.license_plate == car_reg.upper()
        )
        if not car:
            return []
        query_filter["car_id"] = car.id

    query = ParkingSession.find(query_filter)

    if status:
        query = query.find(ParkingSession.status == status)
    if date:
        start_of_day = datetime.combine(date, time.min)
        end_of_day = datetime.combine(date, time.max)
        query = query.find(
            ParkingSession.start_time >= start_of_day,
            ParkingSession.start_time <= end_of_day,
        )

    return await query.to_list()


@session_router.post("/{session_id}/complete")
async def complete_session(session_id: str, user=Depends(FastJWT().login_required)):
    session = await ParkingSession.get(PydanticObjectId(session_id))
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = ParkingSessionStatus.COMPLETED
    await session.save()
    return {"status": "completed"}
