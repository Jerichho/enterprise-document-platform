"""Versioned API v1 routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, conversations, documents, search

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(admin.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)


@api_router.get("/status")
def api_status() -> dict[str, str]:
    """Lightweight versioned API heartbeat for clients."""
    return {"status": "ok", "api": "v1"}
