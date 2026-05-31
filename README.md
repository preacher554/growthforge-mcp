# GrowthForge MCP

Internal role-scoped MCP server for GrowthForge agents.

This repo is the **house** for custom MCP tools. V1 starts with InstaGrow read/draft tools so Yuya can supervise and Nara/workers can later add their own modules safely.

## Runtime path

```text
/root/repos/growthforge-mcp
```

## Design

- One internal MCP server.
- Domain modules under `growthforge_mcp/tools/`.
- Role-scoped permissions under `config/roles.yaml`.
- Data/drafts/audit under `/root/hermes-workspace/instagrow/mcp-data` by default.
- Stdio transport first; HTTP can come later when we want one long-running local service.

## Run manually

```bash
cd /root/repos/growthforge-mcp
GROWTHFORGE_MCP_ROLE=yuya GROWTHFORGE_MCP_DATA_DIR=/root/hermes-workspace/instagrow/mcp-data /usr/local/lib/hermes-agent/venv/bin/python -m growthforge_mcp.server
```

Hermes will normally launch this as an MCP stdio subprocess.

## Hermes config snippet

```yaml
mcp_servers:
  growthforge:
    command: "/usr/local/lib/hermes-agent/venv/bin/python"
    args: ["-m", "growthforge_mcp.server"]
    env:
      PYTHONPATH: "/root/repos/growthforge-mcp"
      GROWTHFORGE_MCP_ROLE: "yuya"
      GROWTHFORGE_MCP_DATA_DIR: "/root/hermes-workspace/instagrow/mcp-data"
    timeout: 120
    connect_timeout: 60
```

For Nara profile, use the same command but role:

```yaml
GROWTHFORGE_MCP_ROLE: "nara"
```

## Current tools

Tool names after Hermes discovery will be prefixed by server name:

```text
mcp_growthforge_health
mcp_growthforge_instagrow_roster
mcp_growthforge_instagrow_status
mcp_growthforge_instagrow_list_workspaces
mcp_growthforge_instagrow_read_source_file
mcp_growthforge_instagrow_create_draft
mcp_growthforge_instagrow_list_drafts
mcp_growthforge_instagrow_audit_tail
mcp_growthforge_contributor_guide
```

## Safety

V1 intentionally avoids shell execution, service restarts, secrets, SSH, firewall, Docker destructive actions, and production publishing. Add write tools later with:

1. role permission check,
2. dry-run/validate mode,
3. audit log,
4. approval gate for production changes.
