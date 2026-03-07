from __future__ import annotations

import os
from pathlib import Path


def _load_simple_env(path: Path):
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and (k not in os.environ):
            os.environ[k] = v


def load_project_env():
    root = Path(__file__).resolve().parents[1]
    p1 = root / ".env"
    p2 = root / "retrieval" / ".env"
    try:
        from dotenv import load_dotenv
        load_dotenv(p1)
        load_dotenv(p2)
    except Exception:
        _load_simple_env(p1)
        _load_simple_env(p2)
