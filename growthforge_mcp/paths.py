from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = Path(os.environ.get("GROWTHFORGE_MCP_DATA_DIR", "/root/hermes-workspace/instagrow/mcp-data"))
INSTAGROW_ROOTS = [
    Path("/root/instagrow"),
    Path("/root/hermes-workspace/instagrow"),
    Path("/root/repos/instagrow"),
    Path("/root/work/growthforge-instagram"),
]


def data_dir() -> Path:
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DEFAULT_DATA_DIR / "drafts").mkdir(parents=True, exist_ok=True)
    (DEFAULT_DATA_DIR / "audit").mkdir(parents=True, exist_ok=True)
    return DEFAULT_DATA_DIR


def safe_resolve_under(root: Path, rel_path: str) -> Path:
    candidate = (root / rel_path).resolve()
    root_resolved = root.resolve()
    if not str(candidate).startswith(str(root_resolved) + os.sep) and candidate != root_resolved:
        raise ValueError(f"Path escapes allowed root: {rel_path}")
    return candidate
