# app/posko_api.py
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from .posko_store import list_posko, create_posko, delete_posko
from .admin_auth import require_admin  # sesuaikan nama dependencymu

router = APIRouter(tags=["posko"])

class PoskoCreate(BaseModel):
    nama: str = Field(min_length=2)
    alamat: str = Field(min_length=3)
    lat: float
    lng: float
    kapasitas: Optional[int] = None
    telepon: Optional[str] = None
    keterangan: Optional[str] = None

@router.get("/evacuation/posts")
def public_list_posko():
    return [p.__dict__ for p in list_posko()]

@router.get("/admin/posts")
def admin_list_posko(_=Depends(require_admin)):
    return [p.__dict__ for p in list_posko()]

@router.post("/admin/posts")
def admin_create_posko(body: PoskoCreate, _=Depends(require_admin)):
    p = create_posko(**body.dict())
    return p.__dict__

@router.delete("/admin/posts/{posko_id}")
def admin_delete_posko(posko_id: str, _=Depends(require_admin)):
    ok = delete_posko(posko_id)
    if not ok:
        raise HTTPException(404, "posko not found")
    return {"ok": True}
