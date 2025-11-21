from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ..core.db import db_dependency
from ..repositories import sessions_repo
from ..schemas.mapping import MappingResult
from ..schemas.sessions import (
    ExportResponse,
    SessionListItem,
    UpdateSessionRequest,
    SessionModel,
)
from ..services import mapping_service, workbook_export_service


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


@router.post("/{session_id}/map", response_model=MappingResult)
async def generate_mapping(session_id: str, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    source = doc.get("final_json") or doc.get("extracted_json")
    if not source:
        raise HTTPException(status_code=400, detail="Session has no extracted data to map")
    try:
        result = mapping_service.map_to_canonical(source)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await sessions_repo.set_mapping(db, session_id, result)
    return result


@router.put("/{session_id}/mapping", response_model=MappingResult)
async def save_mapping(session_id: str, payload: MappingResult, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    normalized = mapping_service.normalize_mapping(payload)
    await sessions_repo.set_mapping(db, session_id, normalized)
    return normalized


@router.post("/{session_id}/export", response_model=ExportResponse)
async def export_session_workbook(session_id: str, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")

    mapping_payload = doc.get("mapping")
    if mapping_payload:
        try:
            mapping_obj = mapping_service.normalize_mapping(
                MappingResult.model_validate(mapping_payload)
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid mapping payload: {exc}")
    else:
        source = doc.get("final_json") or doc.get("extracted_json")
        if not source:
            raise HTTPException(status_code=400, detail="Session has no data to export")
        try:
            mapping_obj = mapping_service.map_to_canonical(source)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        await sessions_repo.set_mapping(db, session_id, mapping_obj)

    try:
        export_result = workbook_export_service.export_mapping(session_id, mapping_obj)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to export workbook: {exc}")

    return export_result
