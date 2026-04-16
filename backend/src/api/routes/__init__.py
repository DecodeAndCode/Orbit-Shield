"""API route registry."""

from fastapi import APIRouter

from src.api.routes.satellites import router as satellites_router
from src.api.routes.conjunctions import router as conjunctions_router
from src.api.routes.propagation import router as propagation_router
from src.api.routes.ml import router as ml_router
from src.api.routes.alerts import router as alerts_router

api_router = APIRouter(prefix="/api")
api_router.include_router(satellites_router)
api_router.include_router(conjunctions_router)
api_router.include_router(propagation_router)
api_router.include_router(ml_router)
api_router.include_router(alerts_router)
