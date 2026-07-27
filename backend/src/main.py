"""FastAPI application entry point for Orbit-Shield."""

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
    title="Orbit-Shield",
    description="ML-enhanced satellite collision avoidance system",
    version="0.1.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://orbit-shield.vercel.app",
        "https://orbit-shield-seven.vercel.app",
    ],
    allow_origin_regex=r"https://orbit-shield(-[a-z0-9-]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.websocket("/ws/conjunctions")(conjunction_websocket)


@app.get("/health")
async def health_check() -> dict:
    """Liveness plus the state of the offline fallback.

    The snapshot only matters when the database is unreachable, which is
    exactly when it is hardest to inspect — so report it here rather than
    discovering it is missing during an outage.
    """
    from src.db import snapshot

    return {
        "status": "ok",
        "service": "orbit-shield",
        "snapshot": {
            "available": snapshot.available(),
            "generated_at": snapshot.generated_at(),
            "satellites": len(snapshot.satellites()),
            "conjunctions": len(snapshot.conjunctions()),
            "path": str(snapshot.SNAPSHOT_PATH),
            "path_exists": snapshot.SNAPSHOT_PATH.exists(),
        },
    }


@app.get("/")
async def root() -> dict[str, str]:
    """Root — landing info. Humans should go to /docs or the frontend."""
    return {
        "service": "orbit-shield",
        "status": "ok",
        "docs": "/docs",
        "frontend": "https://orbit-shield-seven.vercel.app",
        "health": "/health",
    }
