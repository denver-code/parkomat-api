from re import A

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute

from api.public.auth import auth_router

public_router = APIRouter(prefix="/public")


public_router.include_router(auth_router)
