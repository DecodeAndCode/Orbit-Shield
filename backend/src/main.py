"""FastAPI application entry point for Collider."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings  # noqa: F401
from src.api.routes import api_router
from src.api.websocket import conjunction_websocket


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield


app = FastAPI(
    title="Collider",
    description="ML-enhanced satellite collision avoidance system",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.websocket("/ws/conjunctions")(conjunction_websocket)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "collider"}


@app.get("/")
async def root() -> dict[str, str]:
    """Root — landing info. Humans should go to /docs or the frontend."""
    return {
        "service": "collider",
        "status": "ok",
        "docs": "/docs",
        "frontend": "http://localhost:5173",
        "health": "/health",
    }
