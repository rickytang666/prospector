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


def fetch_semantic_candidates_from_rpc(
    *,
    query: str | None = None,
    team_context_summary: str | None = None,
    blocker_summaries: list[str] | None = None,
    k: int = 10,
    filters: dict[str, Any] | None = None,
    query_embedding: list[float] | None = None,
    rpc_fn: str | None = None,
):
    """
    Call match_entities_for_team RPC. Pass either query_embedding (list of 1536 floats)
    or (query, team_context_summary, blocker_summaries) to build and embed the query.
    """
    fn = (rpc_fn or SUPABASE_RPC_MATCH_FN).strip()
    if not fn:
        raise RuntimeError("SUPABASE_RPC_MATCH_FN empty")

    if query_embedding is None and query is not None:
        from retrieval.embeddings import embed_text
        parts = [(query or "").strip()]
        if team_context_summary:
            parts.append("Team context: " + team_context_summary)
        if blocker_summaries:
            parts.append("Blockers: " + " | ".join(blocker_summaries[:4]))
        query_text = ". ".join(p for p in parts if p).strip() or "support"
        query_embedding = embed_text(query_text)

    if query_embedding is None:
        return []

    cl = get_supabase_client()
    payload = {
        "query_embedding": query_embedding,
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
