from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import requests

from ..core.config import settings


_token_cache: Optional[Dict[str, Any]] = None
_token_expiry_ts: float = 0.0

logger = logging.getLogger(__name__)


def _raise_for_graph_error(resp: requests.Response, context: str) -> None:
    """Raise a RuntimeError with the Graph error payload included for debugging."""
    if resp.ok:
        return
    try:
        body: Any = resp.json()
    except ValueError:
        body = resp.text
    logger.error("Microsoft Graph error [%s]: %s %s", context, resp.status_code, body)
    raise RuntimeError(f"{context} failed with {resp.status_code}: {body}")


def _get_access_token() -> str:
    """Acquire (and cache) an app-only access token for Microsoft Graph."""
    global _token_cache, _token_expiry_ts

    now = time.time()
    if _token_cache and now < _token_expiry_ts - 60:
        return str(_token_cache.get("access_token"))

    token_url = (
        f"https://login.microsoftonline.com/{settings.graph_tenant_id}/oauth2/v2.0/token"
    )
    data = {
        "client_id": settings.graph_client_id,
        "client_secret": settings.graph_client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }
    resp = requests.post(token_url, data=data, timeout=30)
    _raise_for_graph_error(resp, "Graph token request")
    payload = resp.json()

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Graph token response missing access_token")

    expires_in = float(payload.get("expires_in", 3600))
    _token_cache = payload
    _token_expiry_ts = now + expires_in
    return str(access_token)


def _headers(session_id: Optional[str] = None, *, accept: str = "application/json") -> Dict[str, str]:
    """Base headers for Graph requests.

    By default we ask for JSON, but some endpoints (like PDF export) return
    binary content and should override the Accept header.
    """
    token = _get_access_token()
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": accept,
    }
    if session_id:
        headers["workbook-session-id"] = session_id
    return headers


def upload_workbook(workbook_id: str, filename: str, content: bytes) -> str:
    """Upload a workbook binary into the configured drive and return the item id."""
    safe_name = filename or "workbook.xlsx"
    path = f"/airr-poc/workbooks/{workbook_id}/{safe_name}"
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/root:{path}:/content"
    )
    resp = requests.put(url, headers=_headers(), data=content, timeout=120)

    # If the workbook is locked (e.g., open in Excel or held by a prior Graph
    # session), a blind overwrite will fail with 423. In that case, prefer to
    # reuse the existing drive item at this path so conversions remain
    # idempotent for a given workbook_id.
    if resp.status_code == 423:
        meta_url = (
            f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
            f"/root:{path}"
        )
        meta_resp = requests.get(meta_url, headers=_headers(), timeout=30)
        if meta_resp.ok:
            try:
                existing = meta_resp.json()
            except ValueError:
                existing = {}
            item_id = existing.get("id")
            if item_id:
                logger.warning(
                    "Microsoft Graph upload hit 423 resourceLocked for path '%s'; "
                    "reusing existing drive item '%s'",
                    path,
                    item_id,
                )
                return str(item_id)
        # Fallback: treat the original 423 as a hard error so callers still see
        # the underlying Graph message.
        _raise_for_graph_error(resp, "Graph upload workbook (resourceLocked)")

    _raise_for_graph_error(resp, "Graph upload workbook")
    item = resp.json()
    item_id = item.get("id")
    if not item_id:
        raise RuntimeError("Graph upload response missing item id")
    return str(item_id)


def upload_export_workbook(session_id: str, filename: str, content: bytes) -> str:
    """Upload an exported workbook into the configured drive and return the item id.

    Files are stored under /airr-poc/exports/{session_id}/{filename}.
    """
    safe_name = filename or "model.xlsx"
    path = f"/airr-poc/exports/{session_id}/{safe_name}"
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/root:{path}:/content"
    )
    resp = requests.put(url, headers=_headers(), data=content, timeout=120)
    _raise_for_graph_error(resp, "Graph upload export workbook")
    item = resp.json()
    item_id = item.get("id")
    if not item_id:
        raise RuntimeError("Graph upload export workbook response missing item id")
    return str(item_id)


def create_workbook_session(item_id: str) -> str:
    """Create a persistent workbook session for a given drive item."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/createSession"
    )
    resp = requests.post(
        url,
        headers=_headers(),
        json={"persistChanges": True},
        timeout=30,
    )
    _raise_for_graph_error(resp, "Graph createSession")
    payload = resp.json()
    session_id = payload.get("id")
    if not session_id:
        raise RuntimeError("Graph createSession response missing id")
    return str(session_id)


def activate_sheet(item_id: str, session_id: str, sheet_name: str) -> None:
    """Best-effort: set the active worksheet for subsequent operations.

    Some tenants or Graph API surfaces may not expose the `activate` action on
    worksheets (or only expose it on beta). In those cases we log a warning but
    do not fail the overall conversion pipeline, since hiding other sheets and
    exporting the workbook still yields a useful PDF.
    """
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets('{sheet_name}')/activate"
    )
    resp = requests.post(url, headers=_headers(session_id), timeout=30)
    if not resp.ok:
        logger.warning(
            "Microsoft Graph activate worksheet '%s' failed for item '%s' with "
            "status %s: %s",
            sheet_name,
            item_id,
            resp.status_code,
            resp.text,
        )


def hide_other_sheets(item_id: str, session_id: str, active_sheet: str) -> None:
    """Hide all worksheets except the active one to mimic single-sheet export."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets"
    )
    resp = requests.get(url, headers=_headers(session_id), timeout=30)
    _raise_for_graph_error(resp, "Graph list worksheets")
    payload = resp.json()
    for ws in payload.get("value", []):
        name = ws.get("name")
        if not name or name == active_sheet:
            continue
        patch_url = (
            f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
            f"/items/{item_id}/workbook/worksheets('{name}')"
        )
        patch_resp = requests.patch(
            patch_url,
            headers={**_headers(session_id), "Content-Type": "application/json"},
            json={"visibility": "veryHidden"},
            timeout=30,
        )
        _raise_for_graph_error(patch_resp, f"Graph hide worksheet '{name}'")


def auto_fit_columns(item_id: str, session_id: str, sheet_name: str) -> None:
    """Best-effort auto-fit of used columns on the target sheet."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets('{sheet_name}')"
        f"/usedRange()/format/autoFitColumns"
    )
    resp = requests.post(url, headers=_headers(session_id), timeout=60)
    # Some tenants or workbook types may not support this fully; tolerate failures.
    if not resp.ok:
        logger.warning(
            "Microsoft Graph autoFitColumns failed for sheet '%s' on item '%s' "
            "with status %s: %s",
            sheet_name,
            item_id,
            resp.status_code,
            resp.text,
        )
        # Intentionally do not raise; rendering will still proceed with original widths.
        return


def set_single_page_layout(item_id: str, session_id: str, sheet_name: str) -> None:
    """Best-effort: nudge page layout toward a single-page, landscape export.

    Excel Online's PDF export respects the worksheet's page layout settings.
    Here we use a larger paper size and centered, landscape layout with a
    modest zoom scale to encourage a one-page render for typical model sheets.
    """
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets('{sheet_name}')/pageLayout"
    )
    payload: Dict[str, Any] = {
        "orientation": "landscape",
        "paperSize": "tabloid",  # 11x17, similar to the LibreOffice path
        "centerHorizontally": True,
        "centerVertically": True,
        "zoom": {"scale": 80},
    }
    try:
        resp = requests.patch(
            url,
            headers={**_headers(session_id), "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
    except Exception as exc:
        logger.warning(
            "Microsoft Graph pageLayout request failed for item '%s' sheet '%s': %s",
            item_id,
            sheet_name,
            exc,
        )
        return

    if not resp.ok:
        logger.warning(
            "Microsoft Graph pageLayout update failed for item '%s' sheet '%s' "
            "with status %s: %s",
            item_id,
            sheet_name,
            resp.status_code,
            resp.text,
        )
        # Do not raise; layout tweaks are best-effort only.


def get_used_range_text(item_id: str, session_id: str, sheet_name: str) -> List[List[str]]:
    """Return the worksheet used range as display text.

    Prefers the `text` matrix (display values) and falls back to `values`.
    All cells are converted to strings, with None mapped to "".
    """
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets('{sheet_name}')/usedRange()"
    )
    resp = requests.get(url, headers=_headers(session_id), timeout=60)
    _raise_for_graph_error(resp, "Graph get usedRange text")
    payload = resp.json()

    def _to_string_matrix(raw: Any) -> List[List[str]]:
        if not isinstance(raw, list):
            raise RuntimeError("Graph usedRange payload is not a list matrix")
        result: List[List[str]] = []
        for row in raw:
            if not isinstance(row, list):
                raise RuntimeError("Graph usedRange row is not a list")
            result.append([("" if cell is None else str(cell)) for cell in row])
        return result

    text_matrix = payload.get("text")
    if isinstance(text_matrix, list):
        return _to_string_matrix(text_matrix)

    values_matrix = payload.get("values")
    if isinstance(values_matrix, list):
        return _to_string_matrix(values_matrix)

    raise RuntimeError("Graph usedRange response missing 'text' or 'values' matrix")


def download_pdf(item_id: str, session_id: str) -> bytes:
    """Export the workbook (respecting the session state) to PDF bytes."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/content?format=pdf"
    )
    # Request binary PDF content explicitly; the default JSON Accept header
    # is not appropriate for this endpoint and can trigger 406 errors.
    resp = requests.get(
        url,
        headers=_headers(session_id, accept="application/pdf"),
        timeout=180,
    )
    _raise_for_graph_error(resp, "Graph download workbook as PDF")
    return resp.content


def create_view_link(item_id: str, scope: str = "anonymous") -> str:
    """Create a view-only sharing link for the given drive item.

    By default uses anonymous scope so the link can be opened by Office Online
    without authentication, subject to tenant sharing policies.
    """
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/createLink"
    )
    resp = requests.post(
        url,
        headers=_headers(),
        json={"type": "view", "scope": scope},
        timeout=30,
    )
    _raise_for_graph_error(resp, f"Graph createLink ({scope})")
    payload = resp.json()
    link = payload.get("link") or {}
    web_url = link.get("webUrl")
    if not web_url:
        raise RuntimeError("Graph createLink response missing webUrl")
    return str(web_url)

