from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .auth import current_role
from .paths import data_dir


def audit(event: str, payload: dict[str, Any]) -> dict[str, Any]:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "role": current_role(),
        "event": event,
        "payload": payload,
    }
    path = data_dir() / "audit" / "audit.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "
")
    return record


def tail(limit: int = 20) -> list[dict[str, Any]]:
    path = data_dir() / "audit" / "audit.jsonl"
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-max(1, min(limit, 200)):]
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except Exception:
            out.append({"raw": line})
    return out
