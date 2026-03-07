from __future__ import annotations

import os
from typing import Any

from retrieval.config import SUPABASE_RPC_MATCH_FN

_client = None


def _must(v: str | None, k: str):
    if v and v.strip():
        return v.strip()
    raise RuntimeError(f"missing env: {k}")


def get_supabase_client():
    global _client
    if _client is not None:
        return _client

    url = _must(os.getenv("SUPABASE_URL"), "SUPABASE_URL")
    key = _must(os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY"), "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY")

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


def fetch_semantic_candidates_from_rpc(
    *,
    query: str,
    team_context_summary: str,
    blocker_summaries: list[str],
    k: int,
    filters: dict[str, Any] | None = None,
    rpc_fn: str | None = None,
):
    fn = (rpc_fn or SUPABASE_RPC_MATCH_FN).strip()
    if not fn:
        raise RuntimeError("SUPABASE_RPC_MATCH_FN empty")

    cl = get_supabase_client()
    payload = {
        "query": query,
        "team_context_summary": team_context_summary,
        "blocker_summaries": blocker_summaries,
        "k": k,
        "filters": filters or {},
    }

    res = cl.rpc(fn, payload).execute()
    data = getattr(res, "data", None)
    if data is None:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        return data["rows"]
    return []
