from __future__ import annotations

from typing import Any
import json

from retrieval.config import SUPABASE_RPC_MATCH_CHUNKS_FN
from retrieval.models import TeamContext
from retrieval.supabase_client import get_supabase_client


def _parse_json_maybe(v: Any):
    if not isinstance(v, str):
        return v
    s = v.strip()
    if not s:
        return v
    if not ((s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]"))):
        return v
    try:
        return json.loads(s)
    except Exception:
        return v


def _score01(x: Any):
    try:
        f = float(x)
    except Exception:
        return 0.0
    if f < 0.0:
        return 0.0
    if f > 1.0:
        return 1.0
    return f


def _row_to_chunk(r: dict[str, Any]):
    rr = _parse_json_maybe(r)
    if not isinstance(rr, dict):
        return None
    cid = str(rr.get("chunk_id") or rr.get("id") or "")
    txt = str(rr.get("text") or rr.get("content") or rr.get("chunk_text") or "")
    src = str(rr.get("source") or rr.get("source_type") or "")
    ref = str(rr.get("source_ref") or rr.get("source_url") or rr.get("url") or "")
    sem = _score01(rr.get("semantic_score", rr.get("similarity", rr.get("score", 0.0))))
    if not cid and not txt:
        return None
    return {
        "chunk_id": cid,
        "text": txt,
        "source": src,
        "source_ref": ref,
        "semantic_score": sem,
    }


def fetch_internal_chunks_with_meta(
    team_context: TeamContext,
    query: str,
    k: int,
    filters: dict[str, Any] | None = None,
    rpc_fn: str | None = None,
):
    fn = (rpc_fn or SUPABASE_RPC_MATCH_CHUNKS_FN).strip()
    if not fn:
        return {
            "status": "db_error",
            "error": "SUPABASE_RPC_MATCH_CHUNKS_FN empty",
            "raw_row_count": 0,
            "kept_row_count": 0,
            "dropped_row_count": 0,
            "chunks": [],
        }
    blockers = []
    for b in team_context.active_blockers:
        if b.summary:
            blockers.append(b.summary)
    payload = {
        "query": query,
        "team_context_summary": team_context.context_summary,
        "blocker_summaries": blockers,
        "team_name": team_context.team_name,
        "repo": team_context.repo,
        "k": k,
        "filters": filters or {},
    }
    try:
        cl = get_supabase_client()
        res = cl.rpc(fn, payload).execute()
        data = getattr(res, "data", None)
        rows = data if isinstance(data, list) else []
    except Exception as e:
        return {
            "status": "db_error",
            "error": str(e),
            "raw_row_count": 0,
            "kept_row_count": 0,
            "dropped_row_count": 0,
            "chunks": [],
        }
    out = []
    dropped = 0
    for r in rows:
        x = _row_to_chunk(r if isinstance(r, dict) else {"text": str(r)})
        if x is None:
            dropped += 1
            continue
        out.append(x)
    if not out:
        return {
            "status": "db_empty",
            "error": None,
            "raw_row_count": len(rows),
            "kept_row_count": 0,
            "dropped_row_count": dropped,
            "chunks": [],
        }
    return {
        "status": "db_ok",
        "error": None,
        "raw_row_count": len(rows),
        "kept_row_count": len(out),
        "dropped_row_count": dropped,
        "chunks": out,
    }
