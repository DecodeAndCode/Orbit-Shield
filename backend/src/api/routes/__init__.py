"""API route registry."""

from fastapi import APIRouter

from src.api.routes.satellites import router as satellites_router
from src.api.routes.conjunctions import router as conjunctions_router

api_router = APIRouter(prefix="/api")
api_router.include_router(satellites_router)
api_router.include_router(conjunctions_router)
