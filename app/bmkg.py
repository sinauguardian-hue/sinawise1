from __future__ import annotations
import httpx

BMKG_AUTOGEMPA_URL = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"

async def fetch_latest_quake(url: str = BMKG_AUTOGEMPA_URL) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(url, headers={"User-Agent": "sinabung-alert-mvp/1.0"})
        r.raise_for_status()
        data = r.json()

    g = data.get("Infogempa", {}).get("gempa", {}) or {}
    return {
        "source": "BMKG",
        "date_time": g.get("DateTime"),
        "magnitude": g.get("Magnitude"),
        "kedalaman": g.get("Kedalaman"),
        "wilayah": g.get("Wilayah"),
        "potensi": g.get("Potensi"),
        "dirasakan": g.get("Dirasakan"),
        "shakemap": g.get("Shakemap"),
    }
