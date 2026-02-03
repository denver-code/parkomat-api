import os
from datetime import datetime
from io import BytesIO
from typing import List, Optional

from beanie import PydanticObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import config
from app.core.jwt import FastJWT
from models.models import (
    FeeClassification,
    ParkingLocation,
    User,
    UserParkingLocation,
)

parking_router = APIRouter(prefix="/parking")


class ParkingLocationCreateRequest(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    fee_classification: Optional[str] = "free"
    max_stay: Optional[int] = None
    no_return_time: Optional[int] = None
    is_public: bool = False


async def get_proximity_pipeline(
    user_id: PydanticObjectId, lat: float, lng: float, search_type: str
):
    """
    search_type: "saved" (user's memberships) or "public" (other public records)
    """
    pipeline = []

    # 1. GeoNear must be FIRST. Note: lng, lat order for GeoJSON.
    pipeline.append(
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lng, lat]},
                "distanceField": "distance_meters",
                "spherical": True,
                "query": {"is_active": True},
            }
        }
    )

    if search_type == "saved":
        pipeline.append(
            {
                "$lookup": {
                    "from": "user_parking_location",
                    "localField": "_id",
                    "foreignField": "parking_location_id",
                    "as": "membership",
                }
            }
        )
        pipeline.append({"$match": {"membership.user_id": user_id}})
    else:
        pipeline.append(
            {"$match": {"is_public": True, "owner_user_id": {"$ne": user_id}}}
        )

    # 3. Project results - converting ObjectIds to strings here saves us from loop-fixing later
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "id": {"$toString": "$_id"},
                "name": "$location_name",
                "lat": "$latitude",
                "lng": "$longitude",
                "distance": {"$round": ["$distance_meters", 0]},
                "max_stay": "$max_stay",
                "is_public": "$is_public",
                "is_owner": {"$eq": ["$owner_user_id", user_id]},
            }
        }
    )

    return pipeline


@parking_router.post("")
async def create_parking_location(
    payload: ParkingLocationCreateRequest,
    user=Depends(FastJWT().login_required),
):
    parking_location = ParkingLocation(
        owner_user_id=user.id,
        location_name=payload.location_name,
        # GeoJSON Point for $geoNear compatibility
        geo_point={
            "type": "Point",
            "coordinates": [payload.longitude, payload.latitude],
        },
        latitude=payload.latitude,
        longitude=payload.longitude,
        fee_classification=FeeClassification(payload.fee_classification),
        max_stay=payload.max_stay,
        no_return_time=payload.no_return_time,
        is_public=payload.is_public,
    )

    await parking_location.insert()

    await UserParkingLocation(
        user_id=user.id,
        parking_location_id=parking_location.id,
    ).insert()

    return parking_location


@parking_router.get("/proximity")
async def get_nearby_parking(
    lat: float, lng: float, user=Depends(FastJWT().login_required)
):

    collection = ParkingLocation.get_pymongo_collection()

    saved_pipeline = await get_proximity_pipeline(user.id, lat, lng, "saved")
    saved_results = await collection.aggregate(saved_pipeline).to_list(length=10)

    public_pipeline = await get_proximity_pipeline(user.id, lat, lng, "public")
    public_results = await collection.aggregate(public_pipeline).to_list(length=10)

    return {"saved": saved_results, "public": public_results}


@parking_router.get("")
async def get_parking_locations(user=Depends(FastJWT().login_required)):
    collection = UserParkingLocation.get_pymongo_collection()

    pipeline = [
        {"$match": {"user_id": user.id}},
        {
            "$lookup": {
                "from": "parking_location",
                "localField": "parking_location_id",
                "foreignField": "_id",
                "as": "details",
            }
        },
        {"$unwind": "$details"},
        {"$match": {"details.is_active": True}},
        {
            "$project": {
                "_id": 0,
                "id": {"$toString": "$details._id"},
                "name": "$details.location_name",
                "lat": "$details.latitude",
                "lng": "$details.longitude",
                "max_stay": "$details.max_stay",
                "owner_id": {"$toString": "$details.owner_user_id"},
                "is_owner": {"$eq": ["$details.owner_user_id", user.id]},
                "is_public": "$details.is_public",
            }
        },
    ]

    results = await collection.aggregate(pipeline).to_list(length=None)
    return results
