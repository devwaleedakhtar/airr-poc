from __future__ import annotations

import os
import tempfile
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import cloudinary
import cloudinary.uploader
import cloudinary.utils
import requests

from .config import settings


def _configure_cloudinary() -> None:
    if settings.cloudinary_url:
        cloudinary.config(cloudinary_url=settings.cloudinary_url)
        return
    if settings.cloudinary_cloud_name and settings.cloudinary_api_key and settings.cloudinary_api_secret:
        cloudinary.config(
            cloud_name=settings.cloudinary_cloud_name,
            api_key=settings.cloudinary_api_key,
            api_secret=settings.cloudinary_api_secret,
            secure=True,
        )


_configure_cloudinary()


def upload_raw(
    file_path: str,
    public_id: str,
    folder: Optional[str] = None,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "resource_type": "raw",
        "public_id": public_id,
        "type": "private",
        "use_filename": False,
        "unique_filename": False,
        "overwrite": True,
    }
    if folder:
        options["folder"] = folder
    result = cloudinary.uploader.upload(file_path, **options)
    return {
        "public_id": result.get("public_id"),
        "secure_url": result.get("secure_url"),
        "url": result.get("url"),
        "bytes": result.get("bytes"),
        "format": result.get("format"),
        "resource_type": result.get("resource_type"),
    }


def download_to_temp(url: str, suffix: str = "") -> str:
    """Always download via a signed Cloudinary URL when possible.

    If the URL is a Cloudinary raw asset, generate a signed private download URL
    and stream it. If parsing fails (non-Cloudinary URL), fall back to direct GET.
    """

    def _stream_to_temp(download_url: str) -> str:
        resp = requests.get(download_url, stream=True)
        resp.raise_for_status()
        fd, path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return path

    public_id, fmt = _extract_public_id_and_format(url)
    if public_id:
        signed = cloudinary.utils.private_download_url(
            public_id,
            fmt or None,
            resource_type="raw",
            type="private",
        )
        return _stream_to_temp(signed)

    # Non-Cloudinary or failed parse; use direct fetch
    try:
        return _stream_to_temp(url)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else None
        # If this was an Admin signed URL that included a format and failed with 404,
        # retry by regenerating a signed URL without format.
        if status == 404:
            pid2, fmt2 = _extract_from_admin_download_url(url)
            if pid2:
                signed2 = cloudinary.utils.private_download_url(
                    pid2,
                    None,  # omit format
                    resource_type="raw",
                    type="private",
                )
                return _stream_to_temp(signed2)
        raise


def _extract_public_id_and_format(asset_url: str) -> tuple[str | None, str | None]:
    # Expected (typical): https://res.cloudinary.com/<cloud>/raw/upload/v<ver>/<folder>/<name>.<ext>
    try:
        # Strip protocol and domain
        parts = asset_url.split("/raw/upload/")
        if len(parts) != 2:
            return None, None
        tail = parts[1]
        # Remove version segment if present (starts with v123456789/)
        if tail.startswith("v"):
            tail = tail.split("/", 1)[1]
        # Split extension
        if "." in tail:
            base, ext = tail.rsplit(".", 1)
        else:
            base, ext = tail, None
        # public_id should not include extension
        public_id = base
        return public_id, ext
    except Exception:
        return None, None


def _extract_from_admin_download_url(asset_url: str) -> Tuple[Optional[str], Optional[str]]:
    try:
        parsed = urlparse(asset_url)
        # Expect path like /v1_1/<cloud>/raw/download
        if "/raw/download" not in parsed.path:
            return None, None
        qs = parse_qs(parsed.query)
        pid = qs.get("public_id", [None])[0]
        fmt = qs.get("format", [None])[0]
        return pid, fmt
    except Exception:
        return None, None
