from re import A

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute

from api.private import private_router
from api.public import public_router
from api.static import static_router
from app.core.jwt import FastJWT

router = APIRouter(prefix="/api")


router.include_router(private_router, dependencies=[Depends(FastJWT().login_required)])
router.include_router(public_router)
router.include_router(static_router)
