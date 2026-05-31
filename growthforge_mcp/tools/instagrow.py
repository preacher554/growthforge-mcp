from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import audit, tail
from ..auth import require_permission
from ..paths import INSTAGROW_ROOTS, data_dir, safe_resolve_under

ROSTER = [
    {"codename": "Maestro", "worker_id": "instagrow-conductor", "role": "mission control / orchestration"},
    {"codename": "Scout", "worker_id": "instagrow-research", "role": "cross-platform research"},
    {"codename": "Quill", "worker_id": "instagrow-content", "role": "content pillars, copy, calendars"},
    {"codename": "Pixel", "worker_id": "instagrow-creative", "role": "asset-aware creative production"},
    {"codename": "Dispatch", "worker_id": "instagrow-publishing", "role": "publishing packages, analytics, adapter status"},
]


def register(mcp: Any) -> None:
    @mcp.tool()
    def instagrow_roster() -> dict[str, Any]:
        """Return the InstaGrow worker roster and gate model."""
        require_permission("instagrow.read")
        return {
            "system": "InstaGrow",
            "roster": ROSTER,
            "gates": ["intake", "research", "content", "creative", "publishing", "analytics"],
        }

    @mcp.tool()
    def instagrow_status() -> dict[str, Any]:
        """Return a read-only status snapshot of known InstaGrow roots and MCP data paths."""
        require_permission("instagrow.read")
        roots = []
        for root in INSTAGROW_ROOTS:
            roots.append({
                "path": str(root),
                "exists": root.exists(),
                "is_dir": root.is_dir(),
            })
        dd = data_dir()
        return {
            "roots": roots,
            "data_dir": str(dd),
            "drafts_dir": str(dd / "drafts"),
            "audit_log": str(dd / "audit" / "audit.jsonl"),
        }

    @mcp.tool()
    def instagrow_list_workspaces(max_depth: int = 2) -> dict[str, Any]:
        """List known InstaGrow workspace directories without reading secrets."""
        require_permission("instagrow.read")
        max_depth = max(0, min(int(max_depth), 4))
        results = []
        for root in INSTAGROW_ROOTS:
            if not root.exists() or not root.is_dir():
                continue
            for p in sorted(root.rglob("*")):
                try:
                    rel = p.relative_to(root)
                except ValueError:
                    continue
                if len(rel.parts) > max_depth:
                    continue
                if p.is_dir():
                    results.append(str(p))
                if len(results) >= 200:
                    break
        return {"count": len(results), "directories": results}

    @mcp.tool()
    def instagrow_read_source_file(root_path: str, rel_path: str, max_chars: int = 12000) -> dict[str, Any]:
        """Read a non-secret source/playbook file under an approved InstaGrow root."""
        require_permission("instagrow.read")
        root = Path(root_path).resolve()
        allowed = [r.resolve() for r in INSTAGROW_ROOTS if r.exists()]
        if root not in allowed:
            raise ValueError(f"root_path not allowed: {root_path}")
        path = safe_resolve_under(root, rel_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        lower = path.name.lower()
        if lower in {".env", "auth.json"} or any(x in lower for x in ["secret", "token", "key"]):
            raise ValueError("Refusing to read likely secret file")
        text = path.read_text(encoding="utf-8", errors="replace")
        max_chars = max(100, min(int(max_chars), 50000))
        return {"path": str(path), "truncated": len(text) > max_chars, "content": text[:max_chars]}

    @mcp.tool()
    def instagrow_create_draft(kind: str, title: str, body: str, metadata_json: str = "{}") -> dict[str, Any]:
        """Create a draft proposal for an InstaGrow change. Does not apply production changes."""
        require_permission("instagrow.draft")
        kind_safe = "".join(c for c in kind.lower() if c.isalnum() or c in "-_")[:40] or "draft"
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = "".join(c for c in title.lower().replace(" ", "-") if c.isalnum() or c == "-")[:60] or "untitled"
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except Exception as e:
            raise ValueError(f"metadata_json must be valid JSON: {e}")
        path = data_dir() / "drafts" / f"{ts}-{kind_safe}-{slug}.md"
        content = "
".join([
            "---",
            f"kind: {kind_safe}",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"created_at: {ts}",
            f"metadata: {json.dumps(metadata, ensure_ascii=False)}",
            "status: draft",
            "---",
            "",
            body,
            "",
        ])
        path.write_text(content, encoding="utf-8")
        record = audit("instagrow.draft.create", {"kind": kind_safe, "title": title, "path": str(path)})
        return {"draft_path": str(path), "audit": record}

    @mcp.tool()
    def instagrow_list_drafts(limit: int = 50) -> dict[str, Any]:
        """List recent InstaGrow draft proposals."""
        require_permission("instagrow.read")
        limit = max(1, min(int(limit), 200))
        drafts = sorted((data_dir() / "drafts").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return {"count": len(drafts), "drafts": [str(p) for p in drafts]}

    @mcp.tool()
    def instagrow_audit_tail(limit: int = 20) -> dict[str, Any]:
        """Read recent MCP audit events for InstaGrow/GrowthForge."""
        require_permission("instagrow.audit.read")
        return {"events": tail(limit)}
