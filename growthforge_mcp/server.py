from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .auth import role_summary
from .tools import instagrow

mcp = FastMCP("growthforge")


@mcp.tool()
def health() -> dict[str, Any]:
    """Return GrowthForge MCP server health and current role permissions."""
    return {"ok": True, "server": "growthforge-mcp", **role_summary()}


@mcp.tool()
def contributor_guide() -> dict[str, Any]:
    """Explain how a GrowthForge worker should add new MCP tools safely."""
    return {
        "repo": "/root/repos/growthforge-mcp",
        "steps": [
            "Add a domain module under growthforge_mcp/tools/<domain>.py",
            "Define register(mcp) and decorate functions with @mcp.tool()",
            "Add permissions to config/roles.yaml",
            "Call require_permission('<domain>.<action>') inside every tool",
            "Add audit(...) calls for draft/write/apply actions",
            "Import and register the module in growthforge_mcp/server.py",
            "Run python -m compileall growthforge_mcp and a manual MCP smoke test",
            "Restart the relevant Hermes gateway/profile so tools are rediscovered",
        ],
        "hard_no": [
            "No raw shell/root execution tools",
            "No SSH key/firewall/systemd destructive tools",
            "No secrets returned in tool output",
            "No live publishing/apply without approval gates",
        ],
    }


instagrow.register(mcp)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
