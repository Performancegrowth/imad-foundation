"""Design file upload endpoint (Sprint 2)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.core.storage import save_upload

router = APIRouter()

ALLOWED = {".dxf", ".dwg", ".ifc", ".obj", ".png", ".jpg", ".jpeg", ".tiff", ".tif", ".webp", ".pdf"}


@router.post("/upload", summary="Upload a CAD or image design file")
async def upload_file(file: UploadFile):
    """Persist the upload and return its ``file_id`` for processing."""
    filename = (file.filename or "").strip()
    ext = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
    if not filename:
        raise HTTPException(status_code=400, detail="Missing file name.")
    if ext not in ALLOWED:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{ext or '?'}'. Allowed: {', '.join(sorted(ALLOWED))}",
        )
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    meta = save_upload(filename, content)
    return {
        "file_id": meta["file_id"],
        "original_name": meta["original_name"],
        "size_bytes": meta["size_bytes"],
        "extension": meta["file_ext"],
        "status": "uploaded",
    }