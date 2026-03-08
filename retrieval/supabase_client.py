from __future__ import annotations

import os
from typing import Any

from retrieval.config import SUPABASE_RPC_MATCH_FN
from retrieval.envload import load_project_env

_client = None

load_project_env()


def _must(v: str | None, k: str):
    if v and v.strip():
        return v.strip()
    raise RuntimeError(f"missing env: {k}")


def get_supabase_client():
    global _client
    if _client is not None:
        return _client

    url = _must(os.getenv("SUPABASE_URL"), "SUPABASE_URL")
    key = _must(os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_ANON_KEY"), "SUPABASE_KEY or SUPABASE_ANON_KEY")

    try:
        from supabase import create_client  # type: ignore
    except Exception as e:
        raise RuntimeError("supabase client import failed; install with `pip install supabase`") from e

    _client = create_client(url, key)
    return _client


def supabase_ok():
    try:
        get_supabase_client()
        return True
    except Exception:
        return False



