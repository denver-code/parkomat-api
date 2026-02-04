from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from beanie import Document, PydanticObjectId
from pydantic import BaseModel, Field


class User(Document):
    email: str
    password: str
    email_verified: bool = False
    notification_settings: "NotificationSettings" = Field(
        default_factory=lambda: NotificationSettings()
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    telegram_chat_id: Optional[str] = None
    connection_code: Optional[str] = None

    class Settings:
        name = "user"


class NotificationSettings(BaseModel):
    email_on_signin: bool = False
    email_on_password_reset: bool = False


class OTPActivationModel(Document):
    class Settings:
        name = "otp_activation"

    user_id: PydanticObjectId
    otp: str
    expires_at: datetime


class PasswordResetToken(Document):
    class Settings:
        name = "password_reset_token"
        indexes = [
            "token",
            "user_id",
            "expires_at",
        ]

    user_id: PydanticObjectId
    token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    used_at: Optional[datetime] = None


class Car(Document):
    user_id: PydanticObjectId
    license_plate: str

    class Settings:
        name = "car"


class FeeClassification(Enum):
    FREE = "free"
    PAID = "paid"


class ParkingLocation(Document):
    owner_user_id: PydanticObjectId
    location_name: str
    geo_point: dict = {"type": "Point", "coordinates": [0.0, 0.0]}
    latitude: float
    longitude: float
    fee_classification: Optional[FeeClassification] = FeeClassification.FREE
    # In minutes
    max_stay: Optional[int] = None
    no_return_time: Optional[int] = None

    is_public: bool = False
    is_active: bool = True

    class Settings:
        name = "parking_location"
        indexes = [[("geo_point", "2dsphere")]]


class UserParkingLocation(Document):
    user_id: PydanticObjectId
    parking_location_id: PydanticObjectId

    class Settings:
        name = "user_parking_location"


class ParkingSessionStatus(Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ParkingSession(Document):
    user_id: PydanticObjectId
    parking_location_id: Optional[PydanticObjectId] = None
    car_id: PydanticObjectId
    start_time: datetime = Field(default_factory=datetime.utcnow)
    car_location: Optional[dict] = {
        "type": "Point",
        "coordinates": [0.0, 0.0],  # [longitude, latitude]
    }
    # Calculated automatically based on the parking location's fee classification and max stay
    end_time: datetime
    status: ParkingSessionStatus = ParkingSessionStatus.ACTIVE

    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "parking_session"
        indexes = [[("car_location", "2dsphere")]]
