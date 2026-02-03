import datetime

import jwt
from beanie import PydanticObjectId
from fastapi import Cookie, HTTPException, Request
from models.models import User

from app.core.config import config


class FastJWT:
    def __init__(self):
        self.access_secret = config.JWT_SECRET_KEY
        self.otp_secret = f"{config.JWT_SECRET_KEY}_otp"
        self.algorithm = "HS256"

    # --------------------
    # Encode
    # --------------------

    async def encode_access(
        self,
        *,
        data: dict,
        expires_in_days: int = 30,
    ) -> str:
        return self._encode(
            data=data,
            secret=self.access_secret,
            expires_in_seconds=expires_in_days * 86400,
        )

    async def encode_otp(
        self,
        *,
        data: dict,
        expires_in_minutes: int = 60,
    ) -> str:
        return self._encode(
            data=data,
            secret=self.otp_secret,
            expires_in_seconds=expires_in_minutes * 60,
        )

    def _encode(
        self,
        *,
        data: dict,
        secret: str,
        expires_in_seconds: int,
    ) -> str:
        now = datetime.datetime.utcnow()
        payload = {
            **data,
            "iat": now,
            "exp": now + datetime.timedelta(seconds=expires_in_seconds),
        }

        return jwt.encode(payload, secret, algorithm=self.algorithm)

    # --------------------
    # Decode
    # --------------------

    async def decode_access(self, token: str) -> dict:
        return self._decode(token, self.access_secret)

    async def decode_otp(self, token: str) -> dict:
        return self._decode(token, self.otp_secret)

    def _decode(self, token: str, secret: str) -> dict:
        try:
            return jwt.decode(token, secret, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=400, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=400, detail="Invalid token")

    # --------------------
    # Dependency
    # --------------------

    async def login_required(
        self,
        request: Request,
        access_token: str | None = Cookie(default=None),
    ) -> User:
        token = access_token

        if not token:
            auth = request.headers.get("Authorization")
            if auth and auth.startswith("Bearer "):
                token = auth.removeprefix("Bearer ").strip()

        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        payload = await self.decode_access(token)

        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")

        user = await User.get(PydanticObjectId(user_id))
        if not user:
            raise HTTPException(status_code=401, detail="User not found")

        if not user.email_verified:
            raise HTTPException(status_code=403, detail="Email not verified")

        return user
