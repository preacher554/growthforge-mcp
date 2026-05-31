# Nara Extension Guide

Nara may add future WA-agent modules here after the MCP house is verified.

## Suggested WA module path

```text
growthforge_mcp/tools/wa_agent.py
```

## Minimum safe tools

Start with:

```text
wa_status
wa_list_clients
wa_get_client_config
wa_create_draft_change
wa_list_drafts
```

Avoid production mutation first. Draft, validate, then ask Yuya/Chief approval.

## Required pattern

```python
from ..auth import require_permission
from ..audit import audit

def register(mcp):
    @mcp.tool()
    def wa_status():
        require_permission("wa.read")
        return {"ok": True}
```

Then import/register in `growthforge_mcp/server.py`:

```python
from .tools import wa_agent
wa_agent.register(mcp)
```

## Security line

Nara should not add tools that touch:

- SSH authorized keys
- VPS firewall
- raw shell execution
- systemd destructive operations
- Docker volume deletion
- env/secrets dumping

Those stay Yuya/Chief approved only.
