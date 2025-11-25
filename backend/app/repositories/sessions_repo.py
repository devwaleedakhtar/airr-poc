from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from ..schemas.mapping import MappingResult


COLLECTION = "sessions"


def _to_str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc["_id"] = str(doc["_id"]) if isinstance(doc.get("_id"), ObjectId) else doc.get("_id")
    return doc


async def create(db: AsyncIOMotorDatabase, data: Dict[str, Any]) -> str:
    now = datetime.utcnow()
    data.setdefault("created_at", now)
    data.setdefault("updated_at", now)
    result = await db[COLLECTION].insert_one(data)
    return str(result.inserted_id)


async def update_final_json(db: AsyncIOMotorDatabase, session_id: str, final_json: Dict[str, Any]) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"final_json": final_json, "updated_at": datetime.utcnow()}},
    )


async def get(db: AsyncIOMotorDatabase, session_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION].find_one({"_id": ObjectId(session_id)})
    return _to_str_id(doc) if doc else None


async def list_all(db: AsyncIOMotorDatabase, limit: int = 100) -> List[Dict[str, Any]]:
    cursor = db[COLLECTION].find().sort("created_at", -1).limit(limit)
    return [_to_str_id(doc) async for doc in cursor]


async def set_mapping(
    db: AsyncIOMotorDatabase,
    session_id: str,
    mapping: MappingResult,
) -> None:
    payload = mapping.model_dump()
    payload["metadata"]["generated_at"] = mapping.metadata.generated_at
    await db[COLLECTION].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"mapping": payload, "updated_at": datetime.utcnow()}},
    )


async def set_mapping_job(
    db: AsyncIOMotorDatabase,
    session_id: str,
    job: Dict[str, Any],
) -> None:
    await db[COLLECTION].update_one(
        {"_id": ObjectId(session_id)},
        {"$set": {"mapping_job": job, "updated_at": datetime.utcnow()}},
    )
