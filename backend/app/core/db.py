from __future__ import annotations

from typing import AsyncGenerator
from urllib.parse import urlparse

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from .config import settings


def _resolve_db_name(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.path and parsed.path != "/":
        return parsed.path.lstrip("/")
    return "airr_poc"


_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongo_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    global _db
    if _db is None:
        client = get_client()
        name = _resolve_db_name(settings.mongo_uri)
        _db = client[name]
    return _db


async def db_dependency() -> AsyncGenerator[AsyncIOMotorDatabase, None]:
    yield get_db()

