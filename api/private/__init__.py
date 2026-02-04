from re import A

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute

from api.private.car import car_router
from api.private.parking_location import parking_router
from api.private.parking_session import session_router
from app.core.jwt import FastJWT

private_router = APIRouter(prefix="/private")


@private_router.get("/")
async def root():
    return {"message": "Hello World"}


private_router.include_router(car_router)
private_router.include_router(parking_router)
private_router.include_router(session_router)


import base64
import os


@private_router.post("/telegram/request-code")
async def get_connection_code(user=Depends(FastJWT().login_required)):
    # Generate 6 random bytes and encode to Base32 (approx 10 chars)
    random_bytes = os.urandom(6)
    code = base64.b32encode(random_bytes).decode("utf-8").replace("=", "")

    full_code = f"CONNECT_{code}"

    user.connection_code = full_code
    await user.save()

    return {"code": full_code}
***REMOVED***