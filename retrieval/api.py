from __future__ import annotations

from dataclasses import asdict
from typing import Any

from retrieval.ranking import rank_candidates
from retrieval.models import TeamContext


def rank_candidates_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = 5,
    filters: dict[str, Any] | None = None,
):
    out = rank_candidates(team_context=team_context, query=query, k=k, filters=filters)
    return asdict(out)


def rank_from_payload(payload: dict[str, Any]):
    q = str(payload.get("query", ""))
    tc = payload.get("team_context", {})
    k = payload.get("k", 5)
    if not isinstance(k, int):
        try:
            k = int(k)
        except Exception:
            k = 5
    f = payload.get("filters")
    if f is None:
        f = {}
    if not isinstance(f, dict):
        f = {}
    return rank_candidates_dict(team_context=tc, query=q, k=k, filters=f)
