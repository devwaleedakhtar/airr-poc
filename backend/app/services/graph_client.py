from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from ..core.config import settings


_token_cache: Optional[Dict[str, Any]] = None
_token_expiry_ts: float = 0.0


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
    resp.raise_for_status()
    payload = resp.json()

    access_token = payload.get("access_token")
    if not access_token:
        raise RuntimeError("Graph token response missing access_token")

    expires_in = float(payload.get("expires_in", 3600))
    _token_cache = payload
    _token_expiry_ts = now + expires_in
    return str(access_token)


def _headers(session_id: Optional[str] = None) -> Dict[str, str]:
    token = _get_access_token()
    headers: Dict[str, str] = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
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
    resp.raise_for_status()
    item = resp.json()
    item_id = item.get("id")
    if not item_id:
        raise RuntimeError("Graph upload response missing item id")
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
    resp.raise_for_status()
    payload = resp.json()
    session_id = payload.get("id")
    if not session_id:
        raise RuntimeError("Graph createSession response missing id")
    return str(session_id)


def activate_sheet(item_id: str, session_id: str, sheet_name: str) -> None:
    """Set the active worksheet for subsequent operations."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets('{sheet_name}')/activate"
    )
    resp = requests.post(url, headers=_headers(session_id), timeout=30)
    resp.raise_for_status()


def hide_other_sheets(item_id: str, session_id: str, active_sheet: str) -> None:
    """Hide all worksheets except the active one to mimic single-sheet export."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/workbook/worksheets"
    )
    resp = requests.get(url, headers=_headers(session_id), timeout=30)
    resp.raise_for_status()
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
        patch_resp.raise_for_status()


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
        # Intentionally do not raise; rendering will still proceed with original widths.
        return


def download_pdf(item_id: str, session_id: str) -> bytes:
    """Export the workbook (respecting the session state) to PDF bytes."""
    url = (
        f"{settings.graph_base_url}/drives/{settings.graph_drive_id}"
        f"/items/{item_id}/content?format=pdf"
    )
    resp = requests.get(url, headers=_headers(session_id), timeout=180)
    resp.raise_for_status()
    return resp.content

