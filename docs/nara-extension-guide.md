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

## Local + GitHub update rule

Every MCP tool change must be kept in two places:

1. local VPS repo, for the running Hermes/Nara environment;
2. GitHub repo, as the durable source of truth.

Current repo:

```text
local:  /root/repos/growthforge-mcp
GitHub: https://github.com/preacher554/growthforge-mcp
branch: main
```

When Nara adds or edits tools, she must do the full loop:

```bash
cd /root/repos/growthforge-mcp

# 1. Sync first so local is not behind GitHub
git checkout main
git pull --ff-only origin main

# 2. Edit/add the MCP module locally
# example: growthforge_mcp/tools/wa_agent.py

# 3. Run local validation
/usr/local/lib/hermes-agent/venv/bin/python -m compileall growthforge_mcp

# 4. Run MCP discovery smoke test through Hermes
hermes --profile growthforge-wa-operator mcp test growthforge
```

The smoke test must complete successfully and show discovered tools. Do not leave manual server processes running.

Then commit and push:

```bash
git status --short
git add growthforge_mcp/ config/ docs/ README.md AGENTS.md pyproject.toml
git commit -m "feat(wa): add <short tool description>"
git push origin main
```

After pushing, verify GitHub is updated:

```bash
git status --short --branch
git log --oneline --max-count=3
```

If the change is a meaningful stable milestone, create a tag:

```bash
git tag -a v0.x.0 -m "v0.x.0 - <release note>"
git push origin v0.x.0
```

Patch/fix changes can use:

```bash
git tag -a v0.x.y -m "v0.x.y - <fix note>"
git push origin v0.x.y
```

## What Nara must report back

After any MCP change, Nara should report:

```text
- files changed
- tools added/updated
- validation result
- commit SHA
- GitHub URL/branch
- tag, if created
- whether Hermes/gateway/profile restart is needed
```

Do not say “updated” until both local commit and GitHub push are done.
