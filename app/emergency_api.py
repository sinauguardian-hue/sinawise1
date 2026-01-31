from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from .admin_auth import require_admin
from .storage import read_json, write_json

router = APIRouter(tags=["emergency"])
logger = logging.getLogger("sinabung.emergency")

# Ambil send_to_topic dari notifier (kalau tersedia)
try:
    from .notifier import send_to_topic
except Exception:
    send_to_topic = None

EMERGENCY_TOPIC = os.environ.get("FCM_EMERGENCY_TOPIC", "sinabung_emergency").strip() or "sinabung_emergency"
NOTIFY_CLEAR = os.environ.get("EMERGENCY_NOTIFY_CLEAR", "0").strip() == "1"
STATE_KEY = "emergency_state"


def _default_state() -> Dict[str, Any]:
    return {
        "active": False,
        "level": None,
        "message": "Situasi sudah aman.",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def _load_state() -> Dict[str, Any]:
    data = read_json(STATE_KEY, _default_state())
    if not isinstance(data, dict):
        data = _default_state()
    data.setdefault("active", False)
    data.setdefault("level", None)
    data.setdefault("message", "Situasi sudah aman.")
    data.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
    return data


def _save_state(state: Dict[str, Any]) -> None:
    write_json(STATE_KEY, state)

class EmergencyTriggerReq(BaseModel):
    level: Optional[str] = Field(None, description="Level bahaya (mis. AWAS/SIAGA)")
    message: Optional[str] = Field(None, description="Pesan peringatan")
    # kompatibilitas lama (jika ada client lama)
    title: Optional[str] = None
    body: Optional[str] = None


class EmergencyClearReq(BaseModel):
    message: Optional[str] = Field(None, description="Pesan situasi aman")
    # kompatibilitas lama
    body: Optional[str] = None

@router.get("/emergency/status")
def emergency_status() -> Dict[str, Any]:
    return _load_state()


@router.post("/admin/emergency/trigger", dependencies=[Depends(require_admin)])
def emergency_trigger(payload: EmergencyTriggerReq) -> Dict[str, Any]:
    level = (payload.level or "").strip() or None
    message = (payload.message or payload.body or "").strip() or "Segera evakuasi!"

    state = _load_state()
    state.update(
        {
            "active": True,
            "level": level,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_state(state)

    if send_to_topic is not None:
        try:
            data = {
                "type": "EMERGENCY_ALARM",
                "active": "1",
                "ts_utc": str(state["updated_at"]),
                "level": str(level or ""),
                "message": str(message),
                "title": str(payload.title or "PERINGATAN DARURAT"),
            }
            send_to_topic(
                topic=EMERGENCY_TOPIC,
                title=payload.title or "PERINGATAN DARURAT",
                body=message,
                data=data,
                notification=True,
                sound="default",
            )
        except Exception:
            logger.exception("Failed to send emergency alarm notification.")

    return {"ok": True, "status": state}


@router.post("/admin/emergency/clear", dependencies=[Depends(require_admin)])
def emergency_clear(payload: EmergencyClearReq) -> Dict[str, Any]:
    message = (payload.message or payload.body or "").strip() or "Situasi sudah aman."

    state = _load_state()
    state.update(
        {
            "active": False,
            "level": None,
            "message": message,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    _save_state(state)

    if send_to_topic is not None and NOTIFY_CLEAR:
        try:
            data = {
                "type": "EMERGENCY_STOP",
                "active": "0",
                "ts_utc": str(state["updated_at"]),
                "message": str(message),
                "title": "Situasi Aman",
            }
            send_to_topic(
                topic=EMERGENCY_TOPIC,
                title="Situasi Aman",
                body=message,
                data=data,
                notification=True,
                sound="default",
            )
        except Exception:
            logger.exception("Failed to send emergency clear notification.")

    return {"ok": True, "status": state}
