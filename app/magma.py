from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup


def _extract_report_id(report_url: str) -> str | None:
    m = re.search(r"/laporan/(\d+)", report_url)
    return m.group(1) if m else None


async def get_latest_sinabung_report_url(tingkat_url: str) -> str:
    """
    Ambil URL laporan terbaru Sinabung dari halaman 'Tingkat Aktivitas' MAGMA.
    tingkat_url contoh:
      https://magma.esdm.go.id/v1/gunung-api/tingkat-aktivitas
    """
    if not tingkat_url:
        raise ValueError("tingkat_url kosong")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            tingkat_url,
            headers={"User-Agent": "sinabung-alert-mvp/1.0"},
        )
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Cari node teks yang mengandung "Sinabung", lalu cari link laporan di container terdekat.
    candidates = soup.find_all(string=re.compile(r"\bSinabung\b", re.IGNORECASE))
    for text_node in candidates:
        parent = getattr(text_node, "parent", None)
        if parent is None:
            continue

        container = parent.find_parent(["li", "tr", "div", "p"]) or parent
        a = container.find("a", href=re.compile(r"/v1/gunung-api/laporan/"))
        if a and a.get("href"):
            return urljoin(tingkat_url, a["href"])

    raise RuntimeError("Tidak menemukan link laporan Sinabung di halaman Tingkat Aktivitas.")


async def fetch_report_detail(report_url: str) -> dict:
    """
    Fetch halaman laporan MAGMA dan ambil ringkasan:
    - report_id
    - level (contoh: 'Level II (Waspada)')
    - title (baris ringkas)
    - rekomendasi (list beberapa baris)
    """
    if not report_url:
        raise ValueError("report_url kosong")

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(
            report_url,
            headers={"User-Agent": "sinabung-alert-mvp/1.0"},
        )
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n", strip=True)

    # Heuristik level
    m_level = re.search(r"(Level\s+[IV]+\s*\([^)]+\))", text)
    level = m_level.group(1) if m_level else None

    # Judul ringkas (sering memuat periode)
    title_line = None
    for line in text.split("\n"):
        if "Sinabung" in line and "periode" in line:
            title_line = line
            break

    # Rekomendasi: ambil beberapa baris setelah kata 'Rekomendasi'
    rekomendasi: list[str] = []
    if "Rekomendasi" in text:
        after = text.split("Rekomendasi", 1)[1]
        for line in after.split("\n"):
            line = line.strip()
            if not line:
                continue
            if "Copyright" in line:
                break
            rekomendasi.append(line)
            if len(rekomendasi) >= 10:
                break

    return {
        "report_url": report_url,
        "report_id": _extract_report_id(report_url),
        "level": level,
        "title": title_line,
        "rekomendasi": rekomendasi,
    }
