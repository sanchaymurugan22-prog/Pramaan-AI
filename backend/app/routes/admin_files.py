"""Admin pages about files (Stage 9B, designs 35, 38, 39). Admins only.

GET    /api/admin/letterhead          the office name and whether a logo is set
PUT    /api/admin/letterhead          {"office_name": "..."} printed on every exported file and as "Issued by"
POST   /api/admin/letterhead/logo     upload a PNG or JPEG logo (form field "file")
DELETE /api/admin/letterhead/logo
GET    /api/letterhead/logo.png       (anyone signed in) the logo, for previews

GET    /api/admin/public-page         what the public verify page holds, its address, last export, check counts
GET    /api/admin/backups             version, and the backups made so far
POST   /api/admin/backups             make a backup now (data/backups/)
GET    /api/admin/backups/{name}      download one backup
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import app_settings, audit, backup, branding
from app.auth.deps import allow, signed_in
from app.config import settings
from app.db import Record, User, get_session

router = APIRouter(prefix="/api", tags=["admin"])
admin_only = allow("admin")
VERSION = "0.9.0"


def letterhead_state() -> dict:
    saved = app_settings.get("letterhead")
    return {"office_name": saved.get("office_name") or "", "effective_name": branding.office_name(),
            "default_name": settings.issuing_office, "has_logo": branding.logo_png() is not None}


@router.get("/admin/letterhead")
def get_letterhead(admin: User = Depends(admin_only)):
    return letterhead_state()


class LetterheadChange(BaseModel):
    office_name: str


@router.put("/admin/letterhead")
def change_letterhead(change: LetterheadChange, admin: User = Depends(admin_only)):
    name = " ".join(change.office_name.split())
    if len(name) > 120:
        raise HTTPException(400, "Keep the office name under 120 characters.")
    saved = app_settings.get("letterhead")
    saved["office_name"] = name
    app_settings.put("letterhead", saved, by=admin)
    audit.log("system", "letterhead_changed", f"Office name on exported files: “{name or settings.issuing_office}”",
              actor=admin)
    return letterhead_state()


@router.post("/admin/letterhead/logo")
async def upload_logo(file: Annotated[UploadFile, File()], admin: User = Depends(admin_only)):
    data = await file.read(branding.MAX_LOGO_BYTES + 1)
    try:
        branding.save_logo(data)
    except branding.LogoError as exc:
        raise HTTPException(400, str(exc))
    saved = app_settings.get("letterhead")
    saved["has_logo"] = True
    app_settings.put("letterhead", saved, by=admin)
    audit.log("system", "logo_uploaded", f"Uploaded a new logo for exported files ({file.filename})", actor=admin)
    return letterhead_state()


@router.delete("/admin/letterhead/logo")
def delete_logo(admin: User = Depends(admin_only)):
    branding.remove_logo()
    saved = app_settings.get("letterhead")
    saved["has_logo"] = False
    app_settings.put("letterhead", saved, by=admin)
    audit.log("system", "logo_removed", "Removed the logo from exported files", actor=admin)
    return letterhead_state()


@router.get("/letterhead/logo.png")
def logo(user: User = Depends(signed_in)):
    data = branding.logo_png()
    if data is None:
        raise HTTPException(404, "No logo has been uploaded.")
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.get("/admin/public-page")
def public_page(db: Session = Depends(get_session), admin: User = Depends(admin_only)):
    issued = db.scalar(select(func.count()).select_from(Record).where(Record.kind == "issue")) or 0
    withdrawn = db.scalar(select(func.count()).select_from(Record).where(Record.kind == "withdraw")) or 0
    return {
        "address": settings.verify_base_url,
        "issuer": branding.office_name(),
        "records": {"issued": issued, "withdrawn": withdrawn},
        "last_export": app_settings.get("public_page").get("last_export"),
        "checker": app_settings.get("counters"),
    }


@router.get("/admin/backups")
def list_backups(admin: User = Depends(admin_only)):
    return {"version": VERSION, "ai_mode": settings.ai_mode, "backups": backup.list_backups(),
            "folder": str(backup.BACKUP_DIR)}


@router.post("/admin/backups", status_code=201)
def make_backup(admin: User = Depends(admin_only)):
    path = backup.make_backup()
    audit.log("system", "backup_made", f"Made a backup: {path.name} ({path.stat().st_size:,} bytes, encrypted)",
              actor=admin)
    return {"version": VERSION, "made": path.name, "backups": backup.list_backups(), "folder": str(backup.BACKUP_DIR)}


@router.get("/admin/backups/{name}")
def download_backup(name: str, admin: User = Depends(admin_only)):
    path = backup.backup_path(name)
    if path is None:
        raise HTTPException(404, "Backup not found.")
    audit.log("system", "backup_downloaded", f"Downloaded the backup {name}", actor=admin)
    return FileResponse(path, media_type="application/zip", filename=name)
