from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..audit import audit, tail
from ..auth import require_permission
from ..paths import data_dir

# ---------------------------------------------------------------------------
# WA Agent MCP Tools
# ---------------------------------------------------------------------------
# Safe read-only + draft tools for Nara WA Agent operations.
# Never touches: SSH keys, firewall, systemd destructive, raw shell.
# ---------------------------------------------------------------------------

RUNTIME_REPO = Path("/root/repos/growthforge-wa-agent-runtime")
EVOLUTION_URL = os.environ.get("EVOLUTION_BASE_URL", "http://127.0.0.1:8080")
EVOLUTION_KEY = os.environ.get("EVOLUTION_API_KEY", "")


def _run_git(args: list[str], cwd: str | Path) -> str:
    """Run a git command and return stdout."""
    try:
        out = subprocess.check_output(
            ["git"] + args,
            cwd=str(cwd),
            text=True,
            timeout=30,
            stderr=subprocess.DEVNULL,
        )
        return out.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"git {' '.join(args)} failed: {e.returncode}") from e


def register(mcp: Any) -> None:
    # ------------------------------------------------------------------
    # READ-ONLY TOOLS (safe, no side effects)
    # ------------------------------------------------------------------

    @mcp.tool()
    def wa_health() -> dict[str, Any]:
        """Return overall WA Agent system health snapshot."""
        require_permission("wa.read")

        # Check runtime repo
        repo_exists = RUNTIME_REPO.is_dir()
        repo_branch = ""
        repo_last_commit = ""
        if repo_exists:
            repo_branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], RUNTIME_REPO)
            repo_last_commit = _run_git(
                ["log", "-1", "--pretty=%h · %ad · %s", "--date=short"], RUNTIME_REPO
            )

        # Check PM2 for *-runtime processes
        pm2_online: list[str] = []
        pm2_stopped: list[str] = []
        try:
            raw = subprocess.check_output(
                ["pm2", "jlist"], text=True, timeout=10, stderr=subprocess.DEVNULL
            )
            for proc in json.loads(raw):
                name = proc.get("name", "")
                if name.endswith("-runtime") and proc.get("pm2_env", {}).get("status") == "online":
                    pm2_online.append(name)
                elif name.endswith("-runtime"):
                    pm2_stopped.append(name)
        except Exception:
            pass

        # Check Evolution instances
        evo_instances: list[dict[str, str]] = []
        if EVOLUTION_KEY:
            import urllib.request
            for inst_name in _tenant_instances():
                try:
                    req = urllib.request.Request(
                        f"{EVOLUTION_URL}/instance/connectionState/{inst_name}",
                        headers={"apikey": EVOLUTION_KEY},
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = json.loads(resp.read())
                        state = data.get("instance", {}).get("state", "unknown")
                        evo_instances.append({"instance": inst_name, "state": state})
                except Exception as e:
                    evo_instances.append({"instance": inst_name, "state": "error", "error": str(e)[:100]})

        return {
            "ok": True,
            "runtime_repo": str(RUNTIME_REPO),
            "repo_exists": repo_exists,
            "repo_branch": repo_branch,
            "repo_last_commit": repo_last_commit,
            "pm2_online": pm2_online,
            "pm2_stopped": pm2_stopped,
            "evolution_instances": evo_instances,
        }

    @mcp.tool()
    def wa_list_clients() -> dict[str, Any]:
        """List all registered WA agent clients (tenants) from Supabase."""
        require_permission("wa.read")

        supabase_url = os.environ.get("SUPABASE_URL", os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""))
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

        if not supabase_url or not supabase_key:
            return {"error": "Supabase not configured", "clients": []}

        import urllib.request
        url = f"{supabase_url}/rest/v1/tenants?select=id,tenant_key,business_name,package,whatsapp_instance,ai_enabled,created_at&order=created_at.asc"
        req = urllib.request.Request(
            url,
            headers={
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            tenants = json.loads(resp.read())

        clients = []
        for t in tenants:
            # Count conversations for this tenant
            conv_count = _supabase_count(
                supabase_url, supabase_key,
                f"conversations?tenant_id=eq.{t['id']}&select=id",
            )
            active_count = _supabase_count(
                supabase_url, supabase_key,
                f"conversations?tenant_id=eq.{t['id']}&state=eq.ai_active&select=id",
            )
            waiting_count = _supabase_count(
                supabase_url, supabase_key,
                f"conversations?tenant_id=eq.{t['id']}&state=eq.waiting_human&select=id",
            )
            human_count = _supabase_count(
                supabase_url, supabase_key,
                f"conversations?tenant_id=eq.{t['id']}&state=eq.human_active&select=id",
            )
            clients.append({
                "id": t["id"],
                "tenant_key": t["tenant_key"],
                "business_name": t["business_name"],
                "package": t["package"],
                "whatsapp_instance": t["whatsapp_instance"],
                "ai_enabled": t["ai_enabled"],
                "conversations": conv_count,
                "ai_active": active_count,
                "waiting_human": waiting_count,
                "human_active": human_count,
                "created_at": t["created_at"],
            })

        return {"clients": clients, "count": len(clients)}

    @mcp.tool()
    def wa_get_client_config(tenant_key: str) -> dict[str, Any]:
        """Get runtime configuration for a specific WA agent client (from brain.py system context)."""
        require_permission("wa.read")

        brain_file = RUNTIME_REPO / "app" / "brain.py"
        config_file = RUNTIME_REPO / "app" / "config.py"

        result: dict[str, Any] = {"tenant_key": tenant_key, "found": False}

        if brain_file.exists():
            content = brain_file.read_text(encoding="utf-8", errors="replace")
            # Extract SYSTEM_CONTEXT
            start = content.find('SYSTEM_CONTEXT = """')
            if start != -1:
                end = content.find('"""', start + 20)
                if end != -1:
                    result["system_context"] = content[start + 20:end].strip()
                    result["found"] = True
            # Extract opening_reply
            or_start = content.find("def opening_reply")
            if or_start != -1:
                or_end = content.find("\n\n", or_start + 200)
                result["opening_reply_preview"] = content[or_start:or_end][:500] if or_end != -1 else content[or_start:or_start + 500]

        if config_file.exists():
            config_content = config_file.read_text(encoding="utf-8")
            for field in ["hermes_model_provider", "hermes_model", "evolution_instance", "runtime_port"]:
                for line in config_content.splitlines():
                    if line.strip().startswith(field):
                        result[field] = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

        return result

    @mcp.tool()
    def wa_list_conversations(tenant_key: str, state_filter: str = "", limit: int = 50) -> dict[str, Any]:
        """List conversations for a specific tenant. Optional state filter (ai_active, waiting_human, human_active, resolved)."""
        require_permission("wa.read")

        supabase_url = os.environ.get("SUPABASE_URL", os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""))
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

        if not supabase_url or not supabase_key:
            return {"error": "Supabase not configured", "conversations": []}

        import urllib.request
        # First get tenant id
        url = f"{supabase_url}/rest/v1/tenants?tenant_key=eq.{tenant_key}&select=id"
        req = urllib.request.Request(url, headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tenants = json.loads(resp.read())

        if not tenants:
            return {"error": f"tenant_key '{tenant_key}' not found", "conversations": []}

        tenant_id = tenants[0]["id"]
        conv_url = f"{supabase_url}/rest/v1/conversations?tenant_id=eq.{tenant_id}&select=id,remote_jid,customer_name,state,last_message_at,created_at&order=last_message_at.desc.nullsfirst&limit={max(1, min(limit, 200))}"
        if state_filter:
            conv_url += f"&state=eq.{state_filter}"

        req = urllib.request.Request(conv_url, headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            conversations = json.loads(resp.read())

        for c in conversations:
            c["phone"] = (c.get("remote_jid") or "").replace("@s.whatsapp.net", "")

        return {"tenant_key": tenant_key, "conversations": conversations, "count": len(conversations)}

    @mcp.tool()
    def wa_get_messages(conversation_id: str, limit: int = 100) -> dict[str, Any]:
        """Get messages for a specific conversation."""
        require_permission("wa.read")

        supabase_url = os.environ.get("SUPABASE_URL", os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""))
        supabase_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))

        if not supabase_url or not supabase_key:
            return {"error": "Supabase not configured"}

        import urllib.request
        url = f"{supabase_url}/rest/v1/messages?conversation_id=eq.{conversation_id}&select=id,direction,sender_jid,text,created_at&order=created_at.asc&limit={max(1, min(limit, 500))}"
        req = urllib.request.Request(url, headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            messages = json.loads(resp.read())

        return {"conversation_id": conversation_id, "messages": messages, "count": len(messages)}

    @mcp.tool()
    def wa_read_runtime_file(rel_path: str, max_chars: int = 8000) -> dict[str, Any]:
        """Read a file under the WA runtime repo (brain.py, main.py, policy.py, etc). Safe: no secrets, no .env."""
        require_permission("wa.read")
        path = RUNTIME_REPO / rel_path
        resolved = path.resolve()
        if not str(resolved).startswith(str(RUNTIME_REPO.resolve())):
            raise ValueError("Path traversal not allowed")
        if not resolved.is_file():
            raise FileNotFoundError(str(resolved))
        lower = resolved.name.lower()
        if lower in (".env", ".env.local", "auth.json", "supabase.env") or any(x in lower for x in ["secret", "token", "key", "password"]):
            raise ValueError("Refusing to read likely secret file")
        text = resolved.read_text(encoding="utf-8", errors="replace")
        max_chars = max(100, min(int(max_chars), 50000))
        return {"path": str(resolved), "truncated": len(text) > max_chars, "content": text[:max_chars]}

    @mcp.tool()
    def wa_list_tenant_instances() -> dict[str, Any]:
        """List all WhatsApp instance names registered in Supabase tenants."""
        require_permission("wa.read")
        return {"instances": _tenant_instances()}

    @mcp.tool()
    def wa_get_evolution_status(instance_name: str) -> dict[str, Any]:
        """Check Evolution API connection status for a specific instance."""
        require_permission("wa.read")

        if not EVOLUTION_KEY:
            return {"error": "EVOLUTION_API_KEY not set in MCP env", "instance": instance_name}

        import urllib.request
        try:
            req = urllib.request.Request(
                f"{EVOLUTION_URL}/instance/connectionState/{instance_name}",
                headers={"apikey": EVOLUTION_KEY},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            return {"instance": instance_name, "state": data.get("instance", {}).get("state", "unknown"), "raw": data}
        except Exception as e:
            return {"instance": instance_name, "state": "error", "error": str(e)[:200]}

    # ------------------------------------------------------------------
    # DRAFT TOOLS (write side-effects into drafts/, not production)
    # ------------------------------------------------------------------

    @mcp.tool()
    def wa_create_draft_change(kind: str, title: str, body: str, metadata_json: str = "{}") -> dict[str, Any]:
        """Create a draft proposal for a WA config or system change. Does NOT apply."""
        require_permission("wa.draft")
        kind_safe = "".join(c for c in kind.lower() if c.isalnum() or c in "-_")[:40] or "draft"
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        slug = "".join(c for c in title.lower().replace(" ", "-") if c.isalnum() or c == "-")[:60] or "untitled"
        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except Exception as e:
            raise ValueError(f"metadata_json must be valid JSON: {e}") from e
        path = data_dir() / "drafts" / "wa" / f"{ts}-{kind_safe}-{slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join([
            "---",
            f"kind: {kind_safe}",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            f"created_at: {ts}",
            "domain: wa-agent",
            f"metadata: {json.dumps(metadata, ensure_ascii=False)}",
            "status: draft",
            "---",
            "",
            body,
            "",
        ])
        path.write_text(content, encoding="utf-8")
        record = audit("wa.draft.create", {"kind": kind_safe, "title": title, "path": str(path)})
        return {"draft_path": str(path), "audit": record}

    @mcp.tool()
    def wa_list_drafts(limit: int = 50) -> dict[str, Any]:
        """List recent WA agent draft proposals."""
        require_permission("wa.read")
        limit = max(1, min(int(limit), 200))
        drafts_dir = data_dir() / "drafts" / "wa"
        drafts_dir.mkdir(parents=True, exist_ok=True)
        drafts = sorted(drafts_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        return {"count": len(drafts), "drafts": [str(p) for p in drafts]}

    @mcp.tool()
    def wa_audit_tail(limit: int = 20) -> dict[str, Any]:
        """Read recent MCP audit events for WA agent operations."""
        require_permission("wa.read")
        return {"events": tail(limit)}


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _tenant_instances() -> list[str]:
    """Read tenant instance names from local repo config or return defaults."""
    instances: list[str] = []
    try:
        result = subprocess.check_output(
            ["pm2", "jlist"], text=True, timeout=10, stderr=subprocess.DEVNULL
        )
        for proc in json.loads(result):
            name = proc.get("name", "")
            if name.endswith("-runtime"):
                instances.append(name.removesuffix("-runtime"))
    except Exception:
        pass
    return instances


def _supabase_count(url: str, key: str, query: str) -> int:
    """Quick count from Supabase REST API using Content-Range header."""
    import urllib.request
    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/{query}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Prefer": "count=exact"},
            method="HEAD",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_range = resp.headers.get("Content-Range", "")
            if "/" in content_range:
                return int(content_range.split("/")[-1])
    except Exception:
        pass
    return 0
