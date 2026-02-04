import datetime
from uuid import uuid4

from beanie import PydanticObjectId
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
)
from pydantic import BaseModel, EmailStr, Field

from app.core.config import config
from app.core.email import send_email
from app.core.jwt import FastJWT
from app.core.password_utils import (
    generate_password,
    get_password_hash,
    verify_password,
)
from app.utils.flags import signup_enabled
from models.models import OTPActivationModel, PasswordResetToken, User


class AuthSchema(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    id: PydanticObjectId = Field(..., alias="id")
    email: str

    class Config:
        json_encoders = {PydanticObjectId: str}


auth_router = APIRouter(prefix="/auth")


async def send_verification_email(email: str, activation_token: str):
    # TODO: Use proper email template
    await send_email(
        email,
        "Activation of Parkomat account",
        f"""
Please verify your email address

Click the link below to verify your email address
{activation_token}


If you didn't sign up for Parkomat, you can ignore this email.

Kind Regards,
Ihor Savenko | Parkomat Security System
        """,
    )


async def send_password_reset_email(email: str, reset_link: str):
    await send_email(
        email,
        "Reset your Parkomat password",
        f"""
We received a request to reset your password.

Click the link below to set a new password:
{reset_link}

If you didn't request this, you can ignore this email.

Kind Regards,
Ihor Savenko | Parkomat Security System
        """,
    )


async def send_signin_alert_email(email: str):
    await send_email(
        email,
        "New sign-in to your Parkomat account",
        f"""
We detected a new sign-in to your Parkomat account.

If this was you, no action is needed.
If this wasn't you, please reset your password.

Kind Regards,
Ihor Savenko | Parkomat Security System
        """,
    )


async def send_password_reset_confirmation(email: str):
    await send_email(
        email,
        "Your Parkomat password was reset",
        f"""
Your Parkomat password has been reset successfully.

If you didn't do this, please reset your password again immediately.

Kind Regards,
Ihor Savenko | Parkomat Security System
        """,
    )


@auth_router.post("/signup", response_model=UserOut)
async def signup_event(
    payload: AuthSchema,
    background_tasks: BackgroundTasks,
    _=Depends(signup_enabled),
) -> UserOut:
    if await User.find_one({"email": payload.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(payload.password)

    user: User = User(
        email=payload.email,
        password=hashed_password,
    )
    user: User = await user.insert()

    otp_code = generate_password(9)

    otp_activation = OTPActivationModel(
        user_id=user.id,
        otp=otp_code,
        expires_at=datetime.datetime.now() + datetime.timedelta(hours=1),
    )

    await otp_activation.insert()

    activation_token = await FastJWT().encode_otp(
        data={
            "otp_id": str(otp_activation.id),
            "otp_code": otp_code,
        }
    )

    activation_link = (
        f"{config.API_BASE_URL}/api/public/auth/activate/{activation_token}"
    )

    background_tasks.add_task(send_verification_email, payload.email, activation_link)

    return UserOut(id=user.id, email=user.email)


@auth_router.get("/activate/{otp_activation_token}")
async def activate_otp(otp_activation_token: str):
    decoded = await FastJWT().decode_otp(otp_activation_token)
    if not decoded:
        raise HTTPException(status_code=400, detail="Invalid OTP token")

    if not decoded.get("otp_id") or not decoded.get("otp_code"):
        raise HTTPException(status_code=400, detail="Invalid OTP token")

    if not PydanticObjectId.is_valid(decoded.get("otp_id")):
        raise HTTPException(status_code=400, detail="Invalid OTP token")

    decoded["otp_id"] = PydanticObjectId(decoded.get("otp_id"))

    otp_record = await OTPActivationModel.find_one(
        {"_id": decoded.get("otp_id"), "otp": decoded.get("otp_code")}
    )
    if not otp_record:
        raise HTTPException(status_code=400, detail="Invalid OTP token")

    if otp_record.expires_at < datetime.datetime.now():
        await otp_record.delete()
        raise HTTPException(status_code=400, detail="OTP token expired")

    user = await User.find_one({"_id": otp_record.user_id})

    if not user:
        await otp_record.delete()
        raise HTTPException(status_code=400, detail="Invalid OTP token")

    user.email_verified = True

    await user.save()

    await otp_record.delete()

    return {"message": "Account activated successfully"}


@auth_router.post("/signin")
async def signin_event(
    payload: AuthSchema,
    response: Response,
    background_tasks: BackgroundTasks,
):
    user = await User.find_one({"email": payload.email})
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=401, detail="Bad email or password")

    if not user.email_verified:
        raise HTTPException(status_code=401, detail="Email not verified")

    jwt_token = await FastJWT().encode_access(
        data={
            "id": str(user.id),
            "email": payload.email,
        }
    )

    is_prod = config.ENV == "production"

    response.set_cookie(
        key="access_token",
        value=jwt_token,
        httponly=True,
        domain=".ihorsavenko.com" if is_prod else None,
        samesite="none" if is_prod else None,
        secure=True if is_prod else False,
        path="/",
    )

    if user.notification_settings and user.notification_settings.email_on_signin:
        background_tasks.add_task(send_signin_alert_email, user.email)

    return {"ok": True}


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    password: str = Field(min_length=8, max_length=72)


class PasswordChangePayload(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)


@auth_router.post("/password-reset/request")
async def request_password_reset(
    payload: PasswordResetRequest,
    background_tasks: BackgroundTasks,
):
    user = await User.find_one({"email": payload.email})
    if not user:
        return {"ok": True}

    token = str(uuid4())
    reset_entry = PasswordResetToken(
        user_id=user.id,
        token=token,
        expires_at=datetime.datetime.utcnow() + datetime.timedelta(hours=1),
    )
    await reset_entry.insert()

    base_url = (config.FRONTEND_URL or config.API_BASE_URL).rstrip("/")
    reset_link = f"{base_url}/reset-password/{token}"
    background_tasks.add_task(send_password_reset_email, user.email, reset_link)
    return {"ok": True}


@auth_router.post("/password-reset/{token}")
async def confirm_password_reset(
    token: str,
    payload: PasswordResetConfirm,
    background_tasks: BackgroundTasks,
):
    reset_entry = await PasswordResetToken.find_one({"token": token})
    if not reset_entry:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    if reset_entry.used_at:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")
    if reset_entry.expires_at < datetime.datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    user = await User.get(reset_entry.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Reset link is invalid or expired")

    user.password = get_password_hash(payload.password)
    await user.save()

    reset_entry.used_at = datetime.datetime.utcnow()
    await reset_entry.save()

    if (
        user.notification_settings
        and user.notification_settings.email_on_password_reset
    ):
        background_tasks.add_task(send_password_reset_confirmation, user.email)

    return {"ok": True}


@auth_router.post("/password/change")
async def change_password(
    payload: PasswordChangePayload,
    user: User = Depends(FastJWT().login_required),
):
    if not verify_password(payload.current_password, user.password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.password = get_password_hash(payload.new_password)
    await user.save()
    return {"ok": True}


@auth_router.get("/verify")
async def verify_event(request: Request):
    token: dict = await FastJWT().decode(request.headers["Authorization"])
    user = await User.get(token["id"])
    if not user:
        raise HTTPException(401, "Unauthorized")
    return {"status": "valid"}


@auth_router.post("/logout")
async def logout_event(response: Response):
    is_prod = config.ENV == "production"

    response.delete_cookie(
        key="access_token",
        path="/",
        domain=".ihorsavenko.com" if is_prod else None,
        samesite="none" if is_prod else None,
        secure=True if is_prod else False,
        httponly=True,
    )

    return {"ok": True}
