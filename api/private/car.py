import os
from io import BytesIO

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image

from app.core.config import config
from app.core.jwt import FastJWT
from models.models import Car

UPLOAD_DIR = "static/cars"

car_router = APIRouter(prefix="/car")


@car_router.post("")
async def create_car(
    license_plate: str = Form(...),
    photo: UploadFile = File(...),
    user=Depends(FastJWT().login_required),
):
    existing_car = await Car.find_one(
        Car.user_id == user.id,
        Car.license_plate == license_plate,
    )
    if existing_car:
        raise HTTPException(
            status_code=400, detail="This plate is already in your garage"
        )

    car = Car(user_id=user.id, license_plate=license_plate)
    await car.insert()

    # Filename format: user_id-car_id.jpg
    filename = f"{user.id}-{car.id}.jpg"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        content = await photo.read()
        with Image.open(BytesIO(content)) as img:
            # Convert to RGB (required for PNG to JPG conversion)
            rgb_img = img.convert("RGB")
            rgb_img.save(file_path, "JPEG", quality=20)
    except Exception:
        # If image processing fails, you might want to delete the DB record
        await car.delete()
        raise HTTPException(status_code=400, detail="Invalid image format")

    await car.save()

    return {
        "id": str(car.id),
        "license_plate": car.license_plate,
        "photo_url": f"{config.API_BASE_URL}/api/static/cars/{filename}",
    }


@car_router.get("")
async def get_cars(user=Depends(FastJWT().login_required)):
    cars = Car.find(Car.user_id == user.id)
    return {
        "cars": [
            {
                "id": str(car.id),
                "license_plate": car.license_plate,
                "photo_filename": f"{user.id}-{car.id}.jpg",
            }
            for car in await cars.to_list()
        ],
        "base_url": f"{config.API_BASE_URL}/api/static/cars/",
    }


@car_router.get("/{car_id}")
async def get_car(car_id: PydanticObjectId, user=Depends(FastJWT().login_required)):
    car = await Car.find_one(Car.id == car_id, Car.user_id == user.id)
    if not car:
        raise HTTPException(status_code=404, detail="Car not found")

    return {
        "id": str(car.id),
        "license_plate": car.license_plate,
        "photo_filename": f"{config.API_BASE_URL}/api/static/cars/{user.id}-{car.id}.jpg",
    }
