from fastapi import APIRouter

from api.public.auth import auth_router

public_router = APIRouter(prefix="/public")


public_router.include_router(auth_router)
