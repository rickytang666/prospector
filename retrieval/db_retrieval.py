from __future__ import annotations

from typing import Any

from retrieval.models import Entity, TeamContext, WaterlooAffinityEvidence
from retrieval.supabase_client import fetch_semantic_candidates_from_rpc


def _to_str_list(v: Any):
    if v is None:
        return []
    if isinstance(v, list):
        out = []
        for x in v:
            if x is None:
                continue
            out.append(str(x))
        return out
    if isinstance(v, str):
        if "," in v:
            return [p.strip() for p in v.split(",") if p.strip()]
        vv = v.strip()
        return [vv] if vv else []
    return [str(v)]


def _norm_affinity(v: Any):
    out: list[WaterlooAffinityEvidence] = []
    if not v:
        return out

    if isinstance(v, list):
        for it in v:
            if isinstance(it, dict):
                out.append(
                    WaterlooAffinityEvidence(
                        type=str(it.get("type", "")),
                        text=str(it.get("text", "")),
                        source_url=str(it.get("source_url", "")),
                    )
                )
            else:
                out.append(WaterlooAffinityEvidence(type="unknown", text=str(it), source_url=""))
        return out

    if isinstance(v, dict):
        out.append(
            WaterlooAffinityEvidence(
                type=str(v.get("type", "")),
                text=str(v.get("text", "")),
                source_url=str(v.get("source_url", "")),
            )
        )
        return out

    return [WaterlooAffinityEvidence(type="unknown", text=str(v), source_url="")]


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


def _row_to_entity(row: dict[str, Any]):
    eid = str(row.get("entity_id") or row.get("id") or "")
    nm = str(row.get("name") or "")
    et = str(row.get("entity_type") or row.get("type") or "unknown")
    sm = str(row.get("summary") or row.get("description") or "")
    tg = _to_str_list(row.get("tags"))
    st = _to_str_list(row.get("support_types"))
    wa = _norm_affinity(row.get("waterloo_affinity_evidence"))

    ent = Entity(
        entity_id=eid,
        name=nm,
        entity_type=et,
        summary=sm,
        tags=tg,
        support_types=st,
        waterloo_affinity_evidence=wa,
    )
    sem = _score01(row.get("semantic_score", row.get("similarity", 0.0)))
    return ent, sem


def fetch_candidates_from_db(
    team_context: TeamContext,
    query: str,
    k: int,
    filters: dict[str, Any] | None = None,
):
    blockers = []
    for b in team_context.active_blockers:
        if b.summary:
            blockers.append(b.summary)

    rows = fetch_semantic_candidates_from_rpc(
        query=query,
        team_context_summary=team_context.context_summary,
        blocker_summaries=blockers,
        k=k,
        filters=filters or {},
    )

    out: list[tuple[Entity, float]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        e, sem = _row_to_entity(r)
        if not e.entity_id or not e.name:
            continue
        out.append((e, sem))
    return out
