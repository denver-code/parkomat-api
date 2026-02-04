import asyncio
import os
from asyncio import run
from contextlib import asynccontextmanager
from datetime import time, timedelta

import sentry_sdk
from beanie import PydanticObjectId, init_beanie
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from api.router import router as api_router
from app.core.config import config
from app.core.database import db
from app.core.email import send_email
from app.core.jwt import FastJWT
from models.models import (
    Car,
    OTPActivationModel,
    ParkingLocation,
    ParkingSession,
    ParkingSessionStatus,
    PasswordResetToken,
    User,
    UserParkingLocation,
)

if not os.path.exists("static/cars"):
    os.makedirs("static/cars")

if not os.path.exists("static/sessions"):
    os.makedirs("static/sessions")


def init_sentry() -> None:
    if not config.SENTRY_DSN:
        return

    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        environment=config.SENTRY_ENVIRONMENT or config.ENV,
        traces_sample_rate=config.SENTRY_TRACES_SAMPLE_RATE,
        integrations=[FastApiIntegration(), StarletteIntegration()],
        send_default_pii=False,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_beanie(
        database=db,
        document_models=[
            User,
            OTPActivationModel,
            PasswordResetToken,
            Car,
            ParkingLocation,
            UserParkingLocation,
            ParkingSession,
        ],
    )

    yield


def get_application():
    init_sentry()
    _app = FastAPI(title=config.PROJECT_NAME, lifespan=lifespan)

    @_app.middleware("http")
    async def metrics_auth_middleware(request: Request, call_next):
        if request.url.path == "/metrics" and config.METRICS_TOKEN:
            auth_header = request.headers.get("authorization", "")
            token_header = request.headers.get("x-metrics-token", "")
            is_bearer = auth_header.lower().startswith("bearer ")
            bearer_token = auth_header[7:] if is_bearer else ""
            if config.METRICS_TOKEN not in {bearer_token, token_header}:
                return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        return await call_next(request)

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=config.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return _app


app = get_application()


# health check
@app.get("/health")
async def health():
    return {"status": "ok"}


app.include_router(api_router)

from datetime import datetime, timezone

import httpx

from app.core.config import config


async def send_telegram_msg(chat_id: str, text: str):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient() as client:
        await client.post(url, json=payload)


async def schedule_reminders(
    user_chat_id: str, end_time: datetime, session_id: PydanticObjectId
):
    """
    This function lives in the background and waits for the specific
    milestones (20m, 10m, 0m) to trigger Telegram alerts.
    """
    intervals = [20, 10, 0]  # Minutes remaining

    for minutes_left in intervals:
        now = datetime.now(timezone.utc)
        # Calculate how long to sleep until this specific reminder
        trigger_time = end_time - timedelta(minutes=minutes_left)
        delay = (trigger_time - now).total_seconds()

        if delay > 0:
            await asyncio.sleep(delay)

            # Verify the session is still ACTIVE (user didn't finish early)
            session = await ParkingSession.get(session_id)
            if not session or session.status != ParkingSessionStatus.ACTIVE:
                break  # Stop reminders if they left the spot

            # Send the message
            msg = (
                "🚨 <b>Expired!</b>"
                if minutes_left == 0
                else f"⚠️ <b>{minutes_left}m left!</b>"
            )
            await send_telegram_msg(user_chat_id, msg)

            # If expired, update status in DB
            if minutes_left == 0:
                session.status = ParkingSessionStatus.COMPLETED
                await session.save()


@app.post("/telegram-webhook")
async def telegram_webhook(update: dict):
    # Standard safety checks for Telegram payload
    if "message" not in update or "text" not in update["message"]:
        return {"ok": True}

    text = update["message"]["text"].strip().upper()
    chat_id = update["message"]["chat"]["id"]

    if text.startswith("CONNECT_"):
        # Find the user with this specific code
        user = await User.find_one(User.connection_code == text)

        if user:
            # Success! Link the account
            user.telegram_chat_id = str(chat_id)
            user.connection_code = None  # Burn the code immediately
            await user.save()

            await send_telegram_msg(
                chat_id,
                "<b>Success!</b> 🚗 Your account is now linked. "
                "I will send your parking reminders here.",
            )
        else:
            await send_telegram_msg(
                chat_id, "❌ <b>Invalid Code.</b> Please check the app for a new code."
            )

    return {"ok": True}
