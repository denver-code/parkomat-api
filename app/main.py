import os
from contextlib import asynccontextmanager

import sentry_sdk
from beanie import init_beanie
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from api.router import router as api_router
from app.core.config import config
from app.core.database import db
from app.utils.telegram import send_telegram_msg
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

    _app.add_middleware(
        CORSMiddleware,
        allow_origins=config.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return _app


app = get_application()


@app.get("/")
async def health():
    return {"status": "ok"}


app.include_router(api_router)


@app.post("/telegram-webhook")
async def telegram_webhook(update: dict):
    if "message" not in update or "text" not in update["message"]:
        return {"ok": True}

    text = update["message"]["text"].strip().upper()
    chat_id = update["message"]["chat"]["id"]

    if text.startswith("CONNECT_"):
        user = await User.find_one(User.connection_code == text)

        if user:
            user.telegram_chat_id = str(chat_id)
            user.connection_code = None
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
