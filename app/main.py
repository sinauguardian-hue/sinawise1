from __future__ import annotations

import os
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx
from fastapi import FastAPI, HTTPException

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logger = logging.getLogger("sinabung")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

# -----------------------------------------------------------------------------
# FastAPI app (INI YANG DICARI UVICORN: app.main:app)
# -----------------------------------------------------------------------------
app = FastAPI(title="Sinabung Early Warning MVP")

# -----------------------------------------------------------------------------
# Include routers (posko + education + emergency + admin auth)
# Pastikan file-file ini ada di folder app/
# -----------------------------------------------------------------------------
try:
    from .posko_api import router as posko_router
    app.include_router(posko_router)
    logger.info("Posko routes enabled.")
except Exception as e:
    logger.warning("Posko routes not enabled: %s: %s", type(e).__name__, e)

try:
    from .education_api import router as edu_router
    app.include_router(edu_router)
    logger.info("Education routes enabled.")
except Exception as e:
    logger.warning("Education routes not enabled: %s: %s", type(e).__name__, e)

try:
    from .emergency_api import router as emergency_router
    app.include_router(emergency_router)
    logger.info("Emergency routes enabled.")
except Exception as e:
    logger.warning("Emergency routes not enabled: %s: %s", type(e).__name__, e)

# INI PENTING: file-nya HARUS bernama "admin_auth_api.py"
# (bukan admin_auth.py)
try:
    from .admin_auth_api import router as admin_auth_router
    app.include_router(admin_auth_router)
    logger.info("Admin auth routes enabled.")
except Exception as e:
    logger.warning("Admin auth routes not enabled: %s: %s", type(e).__name__, e)

# -----------------------------------------------------------------------------
# Optional components (scheduler + MAGMA fetch + notifier + state)
# -----------------------------------------------------------------------------
FEATURES_ERROR: Optional[str] = None

scheduler = None
get_latest_sinabung_report_url = None
fetch_report_detail = None
send_to_topic = None
load_state = None
save_state = None

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from .magma import get_latest_sinabung_report_url, fetch_report_detail
    from .notifier import send_to_topic
    from .state import load_state, save_state

    scheduler = AsyncIOScheduler()
except Exception as e:
    FEATURES_ERROR = f"{type(e).__name__}: {e}"
    logger.warning("Optional components not ready: %s", FEATURES_ERROR)

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _extract_radius_km(rekomendasi: list[str]) -> list[str]:
    results: list[str] = []

    for line in rekomendasi or []:
        for m in re.finditer(
            r"radius(?:\s+(radial|sektoral))?\s+(\d+(?:[.,]\d+)?)\s*km",
            line,
            flags=re.I,
        ):
            tipe = (m.group(1) or "").lower()
            km = m.group(2).replace(",", ".")
            if tipe:
                results.append(f"Radius {km} km ({tipe})")
            else:
                results.append(f"Radius {km} km")

        for m in re.finditer(r"dalam\s+radius\s+(\d+(?:[.,]\d+)?)\s*km", line, flags=re.I):
            km = m.group(1).replace(",", ".")
            results.append(f"Radius {km} km")

        area = re.search(r"sektoral\s+([a-z\-–]+(?:\s*[a-z\-–]+)*)", line, flags=re.I)
        if area and results:
            last = results[-1]
            if "sektoral" in last and "area:" not in last:
                results[-1] = f"{last} (area: {area.group(1).strip()})"

    uniq: list[str] = []
    seen: set[str] = set()
    for r in results:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def _ensure_magma_ready() -> None:
    if FEATURES_ERROR or get_latest_sinabung_report_url is None or fetch_report_detail is None:
        raise HTTPException(status_code=503, detail=f"MAGMA feature not ready: {FEATURES_ERROR}")

# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------
@app.get("/")
def root() -> Dict[str, Any]:
    return {
        "message": "Sinabung backend is running",
        "health": "/health",
        "docs": "/docs",
        "dashboard": "/sinabung/dashboard",
        # public:
        "posko_public": "/evacuation/posts",
        "education_public": "/education/videos",
        # admin auth:
        "admin_login": "/admin/login",
        "admin_me": "/admin/me",
        # admin CRUD:
        "posko_admin": "/admin/posts (GET/POST)",
        "posko_admin_by_id": "/admin/posts/{posko_id} (PUT/DELETE)",
        "education_admin": "/admin/videos (GET/POST)",
        "education_admin_by_id": "/admin/videos/{video_id} (PUT/DELETE)",
        # scheduler manual:
        "admin_check_now": "/admin/check-now (POST)",
    }


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "ok": True,
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "features_ready": FEATURES_ERROR is None,
        "features_error": FEATURES_ERROR,
    }


@app.get("/sinabung/last")
def sinabung_last() -> Dict[str, Any]:
    if FEATURES_ERROR or load_state is None:
        raise HTTPException(status_code=503, detail=f"Backend not fully configured: {FEATURES_ERROR}")
    st = load_state()
    return {
        "last_report_id": getattr(st, "last_report_id", None),
        "last_level": getattr(st, "last_level", None),
    }


@app.get("/sinabung/dashboard")
async def dashboard() -> Dict[str, Any]:
    """
    Dashboard gabungan:
    - MAGMA/PVMBG: level + laporan + rekomendasi + radius_info
    - BMKG: gempa terbaru (autogempa)

    IMPORTANT:
    - Jika MAGMA gagal (DNS/timeout), endpoint tetap balikin BMKG + info error MAGMA.
    """
    # BMKG dulu (biar tetap ada output walau MAGMA error)
    try:
        from .bmkg import fetch_latest_quake
        bmkg = await fetch_latest_quake()
    except Exception as e:
        bmkg = {"source": "BMKG", "error": f"{type(e).__name__}: {e}"}

    # MAGMA
    volcano_payload: Dict[str, Any] = {"name": "Sinabung", "source": "MAGMA/PVMBG"}

    try:
        _ensure_magma_ready()

        tingkat_url = os.environ.get("MAGMA_TINGKAT_URL", "").strip()
        if not tingkat_url:
            raise HTTPException(status_code=500, detail="MAGMA_TINGKAT_URL belum diset")

        report_url = await get_latest_sinabung_report_url(tingkat_url)
        logger.info("Report URL: %s", report_url)

        detail = await fetch_report_detail(report_url)

        rekom = detail.get("rekomendasi") or []
        radius = _extract_radius_km(rekom)

        volcano_payload.update(
            {
                "level": detail.get("level"),
                "report_id": detail.get("report_id"),
                "report_url": detail.get("report_url"),
                "title": detail.get("title"),
                "rekomendasi": rekom,
                "radius_info": radius,
            }
        )

    except HTTPException as e:
        volcano_payload["error"] = e.detail
    except httpx.HTTPError as e:
        volcano_payload["error"] = f"Gagal akses MAGMA: {type(e).__name__}"
    except Exception as e:
        volcano_payload["error"] = f"Gagal proses MAGMA: {type(e).__name__}: {e}"

    return {"volcano": volcano_payload, "earthquake": bmkg}

# -----------------------------------------------------------------------------
# Core job: check MAGMA -> compare state -> send notification -> save state
# -----------------------------------------------------------------------------
async def check_update() -> None:
    if (
        FEATURES_ERROR
        or get_latest_sinabung_report_url is None
        or fetch_report_detail is None
        or load_state is None
        or save_state is None
    ):
        logger.debug("check_update skipped; features not ready: %s", FEATURES_ERROR)
        return

    tingkat_url = os.environ.get("MAGMA_TINGKAT_URL", "").strip()
    if not tingkat_url:
        logger.warning("MAGMA_TINGKAT_URL is empty; skipping check_update.")
        return

    topic = os.environ.get("FCM_TOPIC", "sinabung").strip() or "sinabung"
    st = load_state()

    try:
        report_url = await get_latest_sinabung_report_url(tingkat_url)
        detail = await fetch_report_detail(report_url)
    except Exception:
        logger.exception("Failed to fetch/parse MAGMA data.")
        return

    new_id = detail.get("report_id")
    new_level = detail.get("level")

    changed = False
    if new_id and new_id != getattr(st, "last_report_id", None):
        changed = True
    if new_level and new_level != getattr(st, "last_level", None):
        changed = True

    if not changed:
        logger.info(
            "No change. last_report_id=%s last_level=%s",
            getattr(st, "last_report_id", None),
            getattr(st, "last_level", None),
        )
        return

    title = "Update Gunung Sinabung"
    body_parts = []
    if new_level:
        body_parts.append(str(new_level))
    if detail.get("title"):
        body_parts.append(str(detail["title"]))

    body = " | ".join(body_parts).strip() or "Ada pembaruan informasi Sinabung."
    if len(body) > 180:
        body = body[:177] + "..."

    if send_to_topic is not None:
        try:
            msg_id = send_to_topic(
                topic=topic,
                title=title,
                body=body,
                data={
                    "report_url": str(detail.get("report_url", "")),
                    "level": str(new_level or ""),
                    "report_id": str(new_id or ""),
                },
            )
            logger.info("FCM sent msg_id=%s", msg_id)
        except Exception:
            logger.exception("Failed to send FCM (cek GOOGLE_APPLICATION_CREDENTIALS).")

    if new_id:
        st.last_report_id = new_id
    if new_level:
        st.last_level = new_level
    save_state(st)


@app.post("/admin/check-now")
async def admin_check_now() -> Dict[str, Any]:
    await check_update()
    return {"ok": True}

# -----------------------------------------------------------------------------
# Startup/shutdown: scheduler
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def on_startup() -> None:
    if FEATURES_ERROR or scheduler is None:
        logger.warning("Scheduler not started: %s", FEATURES_ERROR)
        return

    interval_minutes = int(os.environ.get("CHECK_INTERVAL_MINUTES", "5"))
    interval_minutes = max(1, interval_minutes)

    scheduler.add_job(
        check_update,
        trigger="interval",
        minutes=interval_minutes,
        id="sinabung_check",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Scheduler started (interval=%s minutes).", interval_minutes)


@app.on_event("shutdown")
async def on_shutdown() -> None:
    if scheduler is not None and getattr(scheduler, "running", False):
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")
