from re import A

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute

from api.private.car import car_router
from api.private.parking_location import parking_router
from api.private.parking_session import session_router

private_router = APIRouter(prefix="/private")


@private_router.get("/")
async def root():
    return {"message": "Hello World"}


private_router.include_router(car_router)
private_router.include_router(parking_router)
private_router.include_router(session_router)
