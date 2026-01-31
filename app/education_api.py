from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, HttpUrl

from .admin_auth import require_admin
from .storage import read_json, write_json

router = APIRouter(tags=["education"])

DB_NAME = "education"  # -> backend/data/education.json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class VideoCreate(BaseModel):
    judul: str = Field(..., min_length=2)
    url: HttpUrl
    keterangan: Optional[str] = None


class VideoUpdate(BaseModel):
    judul: Optional[str] = None
    url: Optional[HttpUrl] = None
    keterangan: Optional[str] = None


class VideoOut(VideoCreate):
    id: str
    created_at: str
    updated_at: str


def _load_all() -> List[dict]:
    return read_json(DB_NAME, default=[])


def _save_all(items: List[dict]) -> None:
    write_json(DB_NAME, items)


# ---------------- PUBLIC ----------------
@router.get("/education/videos", response_model=list[VideoOut])
def public_list_videos():
    return _load_all()


# ---------------- ADMIN ----------------
@router.get("/admin/videos", response_model=list[VideoOut])
def admin_list_videos(user: str = require_admin):
    return _load_all()


@router.post("/admin/videos", response_model=VideoOut)
def admin_create_video(body: VideoCreate, user: str = require_admin):
    items = _load_all()
    item = body.model_dump()
    item["id"] = uuid4().hex[:10]
    item["created_at"] = _now()
    item["updated_at"] = item["created_at"]
    items.append(item)
    _save_all(items)
    return item


@router.put("/admin/videos/{video_id}", response_model=VideoOut)
def admin_update_video(video_id: str, body: VideoUpdate, user: str = require_admin):
    items = _load_all()
    for i, it in enumerate(items):
        if it.get("id") == video_id:
            upd = body.model_dump(exclude_none=True)
            it.update(upd)
            it["updated_at"] = _now()
            items[i] = it
            _save_all(items)
            return it
    raise HTTPException(status_code=404, detail="Video tidak ditemukan")


@router.delete("/admin/videos/{video_id}")
def admin_delete_video(video_id: str, user: str = require_admin):
    items = _load_all()
    new_items = [it for it in items if it.get("id") != video_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="Video tidak ditemukan")
    _save_all(new_items)
    return {"ok": True, "deleted_id": video_id}
