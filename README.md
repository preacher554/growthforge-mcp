# GrowthForge MCP

Internal role-scoped MCP server for GrowthForge agents.

This repo is the **house** for custom MCP tools. V1 started with InstaGrow read/draft tools so Yuya can supervise approved GrowthForge workers safely. It now also includes safe Messaging/WA Agent read/draft tools for the messaging-agent product line. These tools are global and role-scoped; they are not tied to one persona.

## Runtime path

```text
/root/repos/growthforge-mcp
```

## Design

- One internal MCP server.
- Domain modules under `growthforge_mcp/tools/`.
- Role-scoped permissions under `config/roles.yaml`.
- Data/drafts/audit under `/root/hermes-workspace/instagrow/mcp-data` by default.
- Messaging/WA Agent drafts are stored under the MCP data dir at `wa-agent/drafts`.
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

For global Messaging/WA Agent work, set:

```yaml
GROWTHFORGE_MCP_ROLE: "messaging-agent-operator"
```

The `nara` role is kept only as a backward-compatible alias for the current WA Agent operator profile.

## Current tools

Tool names after Hermes discovery will be prefixed by server name:

```text
mcp_growthforge_health
mcp_growthforge_contributor_guide

mcp_growthforge_instagrow_roster
mcp_growthforge_instagrow_status
mcp_growthforge_instagrow_list_workspaces
mcp_growthforge_instagrow_read_source_file
mcp_growthforge_instagrow_create_draft
mcp_growthforge_instagrow_list_drafts
mcp_growthforge_instagrow_audit_tail

mcp_growthforge_wa_agent_roster
mcp_growthforge_wa_agent_status
mcp_growthforge_wa_agent_list_workspaces
mcp_growthforge_wa_agent_read_source_file
mcp_growthforge_wa_agent_create_draft
mcp_growthforge_wa_agent_list_drafts
mcp_growthforge_wa_agent_audit_tail
mcp_growthforge_wa_agent_client_respawn_checklist
```

## Messaging/WA Agent scope

The Messaging/WA Agent tools are intentionally safe read/draft helpers for any approved operator role:

- inspect approved Messaging/WA Agent architecture/runtime roots,
- read non-private source/playbook files,
- create draft proposals for onboarding, tenant setup, handoff rules, QA, and package scope,
- list Messaging/WA Agent drafts,
- review Messaging/WA Agent audit entries,
- return a client respawn checklist for Basic, Pro, or Custom tenants,
- help operators inspect/check client agent workspaces under `/root/hermes-workspace/wa-agent/tenants/<tenant_key>/`,
- surface tenant profile/knowledge draft concepts for Supabase tables such as `tenants`, `tenant_agent_profiles`, and `tenant_knowledge`,
- explain Evolution API instance-to-tenant mapping via `tenants.whatsapp_instance`,
- reinforce the shared runtime port model: one WA Runtime port can serve many tenants, while a dedicated port is reserved for staging, enterprise isolation, heavy traffic, special auth/network needs, or high-SLA deployments.

V1 does not apply production changes, restart services, send WhatsApp messages, edit live Supabase rows, expose Evolution API keys, or mutate live runtime data.

## Safety

V1 intentionally avoids shell execution, service restarts, secrets, SSH, firewall, Docker destructive actions, live WhatsApp sends, live runtime mutation, and production publishing. Add write tools later with:

1. role permission check,
2. dry-run/validate mode,
3. audit log,
4. approval gate for production changes.
