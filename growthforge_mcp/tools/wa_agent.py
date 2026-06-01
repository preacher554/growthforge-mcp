from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import audit, tail
from ..auth import require_permission
from ..paths import data_dir, safe_resolve_under

WA_AGENT_ROOTS = [
    Path("/root/repos/messaging-agent-architect"),
    Path("/root/repos/growthforge-wa-agent-runtime"),
    Path("/root/hermes-workspace/wa-agent"),
]

ROSTER = [
    {"codename": "Messaging Agent Operator", "worker_id": "messaging-agent-operator", "role": "client respawn lead / managed messaging agent operator"},
    {"codename": "Runtime Architect", "worker_id": "messaging-agent-architect", "role": "runtime architecture, tenant isolation, handoff correctness"},
    {"codename": "Tenant Operator", "worker_id": "messaging-agent-tenant-operator", "role": "client onboarding, package scope, tenant files"},
    {"codename": "QA Operator", "worker_id": "messaging-agent-qa", "role": "handoff, buffer, outbox, tenant isolation test plans"},
    {"codename": "Support Operator", "worker_id": "messaging-agent-support", "role": "runtime issue triage, audit review, client support notes"},
]

RESPAWN_CHECKLIST = {
    "intake": ["collect business profile", "confirm package", "collect approved FAQ", "collect handoff destination"],
    "tenant_setup": ["create tenant_id", "set WhatsApp channel_instance", "set buffer and resume policy", "verify all runtime data is tenant-scoped"],
    "knowledge_setup": ["business-profile.md", "faq.md", "package-scope.md", "handoff-rules.md", "brand-voice.md"],
    "adapter": ["verify WhatsApp bridge", "configure webhook", "normalize inbound payload", "preserve provider message id", "classify business outbound events"],
    "runtime": ["webhook idempotency", "message buffer", "planning context", "outbox safe send", "pacing worker", "runtime events"],
    "handoff": ["handoff summary", "admin notification", "owner lock", "outbox echo vs human admin classification", "1-hour human window", "contextual resume"],
    "chat_ux": ["one idea per bubble", "one question at a time", "no repeated greeting", "strip corporate AI phrases", "split long bubbles", "adaptive emoji density"],
    "qa": ["FAQ test", "fragmented chat test", "duplicate webhook test", "handoff test", "admin takeover test", "resume test", "tenant isolation test"],
    "go_live": ["activate after QA pass", "monitor first 20-50 chats", "collect FAQ gaps", "update handoff rules", "prepare weekly improvement notes"],
}


def _wa_data_dir() -> Path:
    base = data_dir() / "wa-agent"
    (base / "drafts").mkdir(parents=True, exist_ok=True)
    return base


def _safe_segment(value: str, fallback: str) -> str:
    cleaned = "".join(c for c in value.lower().replace(" ", "-") if c.isalnum() or c in "-_")
    return cleaned[:60] or fallback


def _refuse_private_file(path: Path) -> None:
    lower_name = path.name.lower()
    blocked = [".env", "auth.json", "secret", "token", "credential", "password"]
    if any(item in lower_name for item in blocked):
        raise ValueError("Refusing to read likely private file")


def register(mcp: Any) -> None:
    @mcp.tool()
    def wa_agent_roster() -> dict[str, Any]:
        """Return the Messaging Agent worker roster and operating gates."""
        require_permission("wa_agent.read")
        return {"system": "WA Agent / Messaging Agent", "roster": ROSTER, "gates": list(RESPAWN_CHECKLIST.keys())}

    @mcp.tool()
    def wa_agent_status() -> dict[str, Any]:
        """Return a read-only status snapshot of known Messaging Agent roots and MCP data paths."""
        require_permission("wa_agent.read")
        roots = [{"path": str(root), "exists": root.exists(), "is_dir": root.is_dir()} for root in WA_AGENT_ROOTS]
        dd = _wa_data_dir()
        return {"roots": roots, "data_dir": str(dd), "drafts_dir": str(dd / "drafts"), "audit_log": str(data_dir() / "audit" / "audit.jsonl")}

    @mcp.tool()
    def wa_agent_list_workspaces(max_depth: int = 2) -> dict[str, Any]:
        """List known Messaging Agent workspace directories."""
        require_permission("wa_agent.read")
        max_depth = max(0, min(int(max_depth), 4))
        results = []
        for root in WA_AGENT_ROOTS:
            if not root.exists() or not root.is_dir():
                continue
            for p in sorted(root.rglob("*")):
                try:
                    rel = p.relative_to(root)
                except ValueError:
                    continue
                if p.is_dir() and len(rel.parts) <= max_depth:
                    results.append(str(p))
                if len(results) >= 200:
                    break
        return {"count": len(results), "directories": results}

    @mcp.tool()
    def wa_agent_read_source_file(root_path: str, rel_path: str, max_chars: int = 12000) -> dict[str, Any]:
        """Read a non-private source/playbook file under an approved Messaging Agent root."""
        require_permission("wa_agent.read")
        root = Path(root_path).resolve()
        allowed = [r.resolve() for r in WA_AGENT_ROOTS if r.exists()]
        if root not in allowed:
            raise ValueError(f"root_path not allowed: {root_path}")
        path = safe_resolve_under(root, rel_path)
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
        _refuse_private_file(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        max_chars = max(100, min(int(max_chars), 50000))
        return {"path": str(path), "truncated": len(text) > max_chars, "content": text[:max_chars]}

    @mcp.tool()
    def wa_agent_create_draft(kind: str, title: str, body: str, metadata_json: str = "{}") -> dict[str, Any]:
        """Create a draft proposal for a Messaging Agent change. Does not apply production changes."""
        require_permission("wa_agent.draft")
        kind_safe = _safe_segment(kind, "draft")[:40]
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = _safe_segment(title, "untitled")
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except Exception as e:
            raise ValueError(f"metadata_json must be valid JSON: {e}")
        path = _wa_data_dir() / "drafts" / f"{ts}-{kind_safe}-{slug}.md"
        content = "\n".join(["---", f"kind: {kind_safe}", f"title: {json.dumps(title, ensure_ascii=False)}", f"created_at: {ts}", f"metadata: {json.dumps(metadata, ensure_ascii=False)}", "status: draft", "---", "", body, ""])
        path.write_text(content, encoding="utf-8")
        record = audit("wa_agent.draft.create", {"kind": kind_safe, "title": title, "path": str(path)})
        return {"draft_path": str(path), "audit": record}

    @mcp.tool()
    def wa_agent_list_drafts(limit: int = 50) -> dict[str, Any]:
        """List recent Messaging Agent draft proposals."""
        require_permission("wa_agent.read")
        limit = max(1, min(int(limit), 200))
        drafts = sorted((_wa_data_dir() / "drafts").glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return {"count": len(drafts), "drafts": [str(p) for p in drafts]}

    @mcp.tool()
    def wa_agent_audit_tail(limit: int = 20) -> dict[str, Any]:
        """Read recent MCP audit events for Messaging Agent/GrowthForge."""
        require_permission("wa_agent.audit.read")
        events = [event for event in tail(limit * 3) if str(event.get("action", "")).startswith("wa_agent.")]
        return {"events": events[-limit:]}

    @mcp.tool()
    def wa_agent_client_respawn_checklist(package: str = "basic") -> dict[str, Any]:
        """Return the safe client respawn checklist for a new Messaging Agent tenant."""
        require_permission("wa_agent.read")
        package_safe = package.lower().strip()
        if package_safe not in {"basic", "pro", "custom"}:
            raise ValueError("package must be one of: basic, pro, custom")
        return {"package": package_safe, "checklist": RESPAWN_CHECKLIST, "hard_rules": ["never mix tenant data", "never read private files", "never apply production changes from V1 MCP tools", "never send live WhatsApp messages from draft/read tools", "never allow AI generation while conversation owner is human"]}
