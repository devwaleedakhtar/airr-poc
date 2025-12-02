from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Dict

from cloudinary.utils import private_download_url
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, RedirectResponse

from ..core.cloudinary import download_to_temp
from ..core.db import db_dependency
from ..core.db import get_db
from ..repositories import sessions_repo, workbooks_repo
from ..schemas.mapping import MappingJobStatus, MappingResult
from ..schemas.sessions import (
    ExportResponse,
    SessionListItem,
    UpdateSessionRequest,
    SessionModel,
)
from ..services import mapping_service, workbook_export_service
from ..services.pdf_image_service import pdf_to_image


async def _run_mapping_job(session_id: str, source: Dict[str, Any]) -> None:
    db = get_db()
    started_at = datetime.utcnow()
    job: Dict[str, Any] = {"status": "running", "started_at": started_at, "completed_at": None, "error": None}
    await sessions_repo.set_mapping_job(db, session_id, job)
    try:
        mapping_obj = await asyncio.to_thread(mapping_service.map_to_canonical, source)
        await sessions_repo.set_mapping(db, session_id, mapping_obj)
        job["status"] = "succeeded"
        job["completed_at"] = datetime.utcnow()
    except Exception as exc:  # noqa: BLE001 - surface raw error string
        job["status"] = "failed"
        job["completed_at"] = datetime.utcnow()
        job["error"] = str(exc)
    await sessions_repo.set_mapping_job(db, session_id, job)


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


@router.get("/{session_id}/pdf")
async def get_session_pdf(session_id: str, db=Depends(db_dependency)):
    """Return a signed, browser-friendly download URL for the session's source PDF.

    We resolve the workbook + sheet from the session, look up the stored Cloudinary
    public_id/format, and generate a fresh private_download_url. If the workbook
    has no stored public_id for this sheet, we fall back to the persisted pdf_url.
    """
    session = await sessions_repo.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    workbook_id = session.get("workbook_id")
    sheet_name = session.get("sheet_name")
    if not workbook_id or not sheet_name:
        raise HTTPException(status_code=400, detail="Session is missing workbook_id or sheet_name")

    workbook = await workbooks_repo.get(db, workbook_id)
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found")

    pdf_public_ids = workbook.get("pdf_public_ids", {}) or {}
    pdf_formats = workbook.get("pdf_formats", {}) or {}
    public_id = pdf_public_ids.get(sheet_name)
    fmt = pdf_formats.get(sheet_name) or "pdf"

    if public_id:
        signed_url = private_download_url(
            public_id,
            fmt,
            resource_type="raw",
            type="private",
        )
        return RedirectResponse(url=signed_url, status_code=302)

    # Fallback: use the persisted URL if we don't have a stored public_id.
    pdf_url = session.get("pdf_url")
    if not pdf_url:
        raise HTTPException(status_code=400, detail="No PDF stored for this session")

    return RedirectResponse(url=pdf_url, status_code=302)


@router.get("/{session_id}/image")
async def get_session_image(
    session_id: str,
    background_tasks: BackgroundTasks,
    db=Depends(db_dependency),
):
    session = await sessions_repo.get(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    workbook_id = session.get("workbook_id")
    sheet_name = session.get("sheet_name")
    if not workbook_id or not sheet_name:
        raise HTTPException(status_code=400, detail="Session is missing workbook_id or sheet_name")

    workbook = await workbooks_repo.get(db, workbook_id)
    if not workbook:
        raise HTTPException(status_code=404, detail="Workbook not found")

    pdfs = workbook.get("pdfs", {}) or {}
    pdf_public_ids = workbook.get("pdf_public_ids", {}) or {}
    pdf_formats = workbook.get("pdf_formats", {}) or {}

    pdf_url = pdfs.get(sheet_name) or session.get("pdf_url")
    if not pdf_url and not pdf_public_ids.get(sheet_name):
        raise HTTPException(status_code=400, detail="No PDF stored for this session")

    tmp_pdf: str | None = None
    image_path: str | None = None

    try:
        # Download PDF using signed private URL when possible.
        if pdf_public_ids.get(sheet_name):
            signed = private_download_url(
                pdf_public_ids[sheet_name],
                pdf_formats.get(sheet_name) or "pdf",
                resource_type="raw",
                type="private",
            )
            tmp_pdf = download_to_temp(signed, suffix=".pdf")
        elif pdf_url:
            tmp_pdf = download_to_temp(pdf_url, suffix=".pdf")
        else:
            raise HTTPException(status_code=400, detail="No PDF stored for this session")

        image_path = pdf_to_image(tmp_pdf)

        def _cleanup(pdf_path: str | None, img_path: str | None) -> None:
            for path in (pdf_path, img_path):
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except FileNotFoundError:
                        pass

        background_tasks.add_task(_cleanup, tmp_pdf, image_path)

        filename = f"{sheet_name}.png"
        return FileResponse(
            image_path,
            media_type="image/png",
            filename=filename,
            background=background_tasks,
        )
    except HTTPException:
        if tmp_pdf and os.path.exists(tmp_pdf):
            try:
                os.remove(tmp_pdf)
            except FileNotFoundError:
                pass
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except FileNotFoundError:
                pass
        raise
    except Exception as exc:
        if tmp_pdf and os.path.exists(tmp_pdf):
            try:
                os.remove(tmp_pdf)
            except FileNotFoundError:
                pass
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
            except FileNotFoundError:
                pass
        raise HTTPException(status_code=500, detail=f"Failed to generate image: {exc}")


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


@router.post("/{session_id}/map/async", response_model=MappingJobStatus)
async def generate_mapping_async(session_id: str, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")
    source = doc.get("final_json") or doc.get("extracted_json")
    if not source:
        raise HTTPException(status_code=400, detail="Session has no extracted data to map")

    started_at = datetime.utcnow()
    job = MappingJobStatus(status="running", started_at=started_at)
    await sessions_repo.set_mapping_job(db, session_id, job.model_dump())
    asyncio.create_task(_run_mapping_job(session_id, source))
    return job


@router.get("/{session_id}/mapping/status", response_model=MappingJobStatus)
async def get_mapping_status(session_id: str, db=Depends(db_dependency)):
    doc = await sessions_repo.get(db, session_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Session not found")

    mapping = doc.get("mapping")
    job_data = doc.get("mapping_job") or {}
    if mapping and not job_data:
        job_data = {"status": "succeeded"}
    status = job_data.get("status") or "pending"

    if status == "succeeded":
        job_data["mapping"] = mapping

    try:
        return MappingJobStatus.model_validate(job_data)
    except Exception:
        # If stored payload is malformed, surface a minimal pending job.
        return MappingJobStatus(status="pending")


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


@router.get("/{session_id}/export/download")
async def download_exported_workbook(session_id: str, db=Depends(db_dependency)):
    """Stream an exported workbook directly, without relying on Cloudinary.

    This mirrors the mapping logic used in export_session_workbook but always
    generates the workbook locally and returns it as a file response.
    """
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

    workbook_path, _ = workbook_export_service.generate_workbook_file(session_id, mapping_obj)

    return FileResponse(
        path=str(workbook_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"{session_id}-model.xlsx",
    )
