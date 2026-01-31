from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

STATE_FILE = Path("state.json")


@dataclass
class State:
    last_report_id: str | None = None
    last_level: str | None = None


def load_state() -> State:
    if not STATE_FILE.exists():
        return State()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        # kalau file rusak, mulai dari kosong
        return State()

    return State(
        last_report_id=data.get("last_report_id"),
        last_level=data.get("last_level"),
    )


def save_state(state: State) -> None:
    payload = {
        "last_report_id": state.last_report_id,
        "last_level": state.last_level,
    }
    STATE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
