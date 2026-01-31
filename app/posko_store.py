# app/posko_store.py
from __future__ import annotations
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
import json
import uuid
from typing import List, Optional, Dict, Any

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

POSKO_FILE = DATA_DIR / "posko.json"

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Posko:
    id: str
    nama: str
    alamat: str
    lat: float
    lng: float
    kapasitas: Optional[int] = None
    telepon: Optional[str] = None
    keterangan: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

def _load_all() -> List[Dict[str, Any]]:
    if not POSKO_FILE.exists():
        return []
    return json.loads(POSKO_FILE.read_text(encoding="utf-8"))

def _save_all(items: List[Dict[str, Any]]) -> None:
    POSKO_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

def list_posko() -> List[Posko]:
    return [Posko(**x) for x in _load_all()]

def create_posko(nama: str, alamat: str, lat: float, lng: float,
                 kapasitas: Optional[int] = None,
                 telepon: Optional[str] = None,
                 keterangan: Optional[str] = None) -> Posko:
    items = _load_all()
    p = Posko(
        id=str(uuid.uuid4()),
        nama=nama,
        alamat=alamat,
        lat=lat,
        lng=lng,
        kapasitas=kapasitas,
        telepon=telepon,
        keterangan=keterangan,
        created_at=_now(),
        updated_at=_now(),
    )
    items.append(asdict(p))
    _save_all(items)
    return p

def delete_posko(posko_id: str) -> bool:
    items = _load_all()
    before = len(items)
    items = [x for x in items if x.get("id") != posko_id]
    _save_all(items)
    return len(items) != before
