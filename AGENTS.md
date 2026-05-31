# GrowthForge MCP Agent Contract

This repo is the shared MCP home for GrowthForge internal agents.

## Boundaries

- Yuya owns operator/orchestration scope.
- Nara may add WA-agent modules later, but must keep WA tools role-scoped.
- InstaGrow modules must respect Scout/Quill/Pixel/Dispatch boundaries.
- Never add root shell, SSH key, firewall, or destructive Docker/systemd tools without explicit Chief approval and a separate security review.

## Tool requirements

Every new tool must:

1. have a clear role permission in `config/roles.yaml`,
2. call `require_permission(...)`,
3. write audit logs for write/draft/apply actions,
4. default to read-only or draft mode,
5. avoid returning secrets,
6. include a manual smoke test in README or docs.

## File layout

```text
growthforge_mcp/server.py        MCP entrypoint
growthforge_mcp/auth.py          role + permission helpers
growthforge_mcp/audit.py         JSONL audit logging
growthforge_mcp/tools/instagrow.py
config/roles.yaml
docs/nara-extension-guide.md
```
