from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .paths import REPO_ROOT


class PermissionError(Exception):
    pass


@lru_cache(maxsize=1)
def roles_config() -> dict[str, Any]:
    path = REPO_ROOT / "config" / "roles.yaml"
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"roles": {}}


def current_role() -> str:
    return os.environ.get("GROWTHFORGE_MCP_ROLE", "readonly").strip() or "readonly"


def permissions_for(role: str | None = None) -> set[str]:
    role = role or current_role()
    roles = roles_config().get("roles", {})
    return set(roles.get(role, roles.get("readonly", {})).get("permissions", []))


def require_permission(permission: str) -> None:
    perms = permissions_for()
    if permission not in perms:
        raise PermissionError(f"Role '{current_role()}' lacks permission '{permission}'")


def role_summary() -> dict[str, Any]:
    role = current_role()
    return {"role": role, "permissions": sorted(permissions_for(role))}
