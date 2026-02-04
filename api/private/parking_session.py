import os
from datetime import datetime, timedelta, timezone
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
    # 1. Validate the Car belongs to the user
    car = await Car.find_one(Car.id == PydanticObjectId(car_id), Car.user_id == user.id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found in your garage")

    # 2. Determine End Time
    start_time = datetime.now(timezone.utc)
    calculated_end_time = None

    if parking_location_id:
        location = await ParkingLocation.get(PydanticObjectId(parking_location_id))
        if not location:
            raise HTTPException(status_code=404, detail="Parking location not found")

        # If location has a max_stay (in minutes), use it. Default to 24h if none.
        stay_duration = location.max_stay if location.max_stay else 1440
        calculated_end_time = start_time + timedelta(minutes=stay_duration)
    else:
        # "Rush Mode" Logic
        if not manual_max_stay_mins:
            raise HTTPException(
                status_code=400,
                detail="Manual stay time required if location is not selected",
            )
        calculated_end_time = start_time + timedelta(minutes=manual_max_stay_mins)

    # 3. Create Session Record (to get ID for filename)
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

        background_tasks.add_task(
            schedule_reminders, user.telegram_chat_id, session.end_time, session.id
        )
        parking_location = None
        if parking_location_id:
            parking_location = await ParkingLocation.get(parking_location_id)

        await send_telegram_msg(
            user.telegram_chat_id,
            f"Your parking session {f'at {parking_location.name} ' if parking_location else ''}for {car.license_plate} that lasts {manual_max_stay_mins} minutes has started.",
        )

    # 4. Process Photo: user_id-session_id.jpg
    filename = f"{user.id}-{session.id}.jpg"
    file_path = os.path.join(SESSION_UPLOAD_DIR, filename)

    try:
        content = await photo.read()
        with Image.open(BytesIO(content)) as img:
            rgb_img = img.convert("RGB")
            rgb_img.save(file_path, "JPEG", quality=80)
    except Exception:
        await session.delete()
        raise HTTPException(status_code=400, detail="Failed to process proof photo")

    # 5. Return clean response
    return {
        "session_id": str(session.id),
        "car_plate": car.license_plate,
        "ends_at": session.end_time,
        "photo_url": f"/static/sessions/{filename}",
    }


@session_router.get("/active")
async def get_active_session(user=Depends(FastJWT().login_required)):
    """Returns the current active session for the user if it exists"""
    session = await ParkingSession.find_one(
        ParkingSession.user_id == user.id,
        ParkingSession.status == ParkingSessionStatus.ACTIVE,
    )
    if not session:
        return {"active": False}

    return {"active": True, "session": session}


@session_router.post("/{session_id}/complete")
async def complete_session(session_id: str, user=Depends(FastJWT().login_required)):
    session = await ParkingSession.get(PydanticObjectId(session_id))
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    session.status = ParkingSessionStatus.COMPLETED
    await session.save()
    return {"status": "completed"}
