from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.db import db_dependency
from ..repositories import sessions_repo
from ..schemas.sessions import SessionListItem, UpdateSessionRequest, SessionModel


router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=list[SessionListItem])
async def list_sessions(db=Depends(db_dependency)):
    docs = await sessions_repo.list_all(db)
    # project fields for list
    items = [
        {
            "_id": d.get("_id"),
            "workbook_id": d.get("workbook_id"),
            "sheet_name": d.get("sheet_name"),
            "created_at": d.get("created_at"),
            "updated_at": d.get("updated_at"),
        }
        for d in docs
    ]
    return items


@router.get("/{session_id}", response_model=SessionModel)
async def get_session(session_id: str, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    return doc


@router.put("/{session_id}", response_model=SessionModel)
async def update_session(session_id: str, payload: UpdateSessionRequest, db=Depends(db_dependency)):
    await sessions_repo.update_final_json(db, session_id, payload.final_json)
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found after update")
    return doc
