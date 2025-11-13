from __future__ import annotations

from typing import Any, Dict, List, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase


COLLECTION = "workbooks"


def _to_str_id(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    doc["_id"] = str(doc["_id"]) if isinstance(doc.get("_id"), ObjectId) else doc.get("_id")
    return doc


async def create(db: AsyncIOMotorDatabase, data: Dict[str, Any]) -> str:
    # allow caller to set _id to use in Cloudinary folder naming
    if "_id" not in data:
        data["_id"] = ObjectId()
    result = await db[COLLECTION].insert_one(data)
    return str(result.inserted_id)


async def generate_id() -> str:
    return str(ObjectId())


async def get(db: AsyncIOMotorDatabase, workbook_id: str) -> Optional[Dict[str, Any]]:
    doc = await db[COLLECTION].find_one({"_id": ObjectId(workbook_id)})
    return _to_str_id(doc) if doc else None


async def set_pdf_for_sheet(
    db: AsyncIOMotorDatabase,
    workbook_id: str,
    sheet_name: str,
    pdf_url: str,
    public_id: str | None = None,
    fmt: str | None = None,
) -> None:
    update = {f"pdfs.{sheet_name}": pdf_url}
    if public_id:
        update[f"pdf_public_ids.{sheet_name}"] = public_id
    if fmt:
        update[f"pdf_formats.{sheet_name}"] = fmt
    await db[COLLECTION].update_one(
        {"_id": ObjectId(workbook_id)},
        {"$set": update},
    )


async def list_sheets(db: AsyncIOMotorDatabase, workbook_id: str) -> List[str]:
    doc = await get(db, workbook_id)
    return doc.get("sheets", []) if doc else []
