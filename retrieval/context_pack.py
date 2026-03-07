from __future__ import annotations

from dataclasses import asdict
from typing import Any

from retrieval.models import TeamContext, Blocker
from retrieval.ranking import rank_candidates
from retrieval.internal_retrieval import fetch_internal_chunks_with_meta


def _ctx_obj(team_context: TeamContext | dict[str, Any]):
    if isinstance(team_context, TeamContext):
        return team_context
    if not isinstance(team_context, dict):
        return TeamContext(team_name="unknown", repo="", active_blockers=[], subsystems=[], inferred_support_needs=[], context_summary="")
    ab = []
    for b in (team_context.get("active_blockers") or []):
        if isinstance(b, Blocker):
            ab.append(b)
        elif isinstance(b, dict):
            ab.append(Blocker(
                summary=str(b.get("summary", "")),
                tags=[str(x) for x in (b.get("tags") or [])],
                severity=str(b.get("severity", "medium")),
            ))
    return TeamContext(
        team_name=str(team_context.get("team_name", "unknown")),
        repo=str(team_context.get("repo", "")),
        active_blockers=ab,
        subsystems=[str(x) for x in (team_context.get("subsystems") or [])],
        inferred_support_needs=[str(x) for x in (team_context.get("inferred_support_needs") or [])],
        context_summary=str(team_context.get("context_summary", "")),
    )

def _q_terms(q: str):
    stop = {"the","and","for","our","with","who","can","help","need","to","of","we","someone","looking"}
    s = set()
    for w in (q or "").lower().replace("?"," ").replace(","," ").split():
        if len(w) > 2 and w not in stop:
            s.add(w)
    return s

def _infer_chunk_filters(q: str):
    qq = (q or "").lower()
    if any(x in qq for x in ["firmware", "embedded", "rtos", "interrupt"]):
        return {"source": "github_issue"}, {"github_issue": 0.12, "readme": 0.06}
    if any(x in qq for x in ["pcb", "manufacturing", "sponsor", "sponsorship", "procurement"]):
        return {"source": "github_issue"}, {"github_issue": 0.10, "discord": 0.08}
    if any(x in qq for x in ["mapping", "ground station", "telemetry", "geospatial"]):
        return {}, {"github_issue": 0.08, "readme": 0.08}
    return {}, {}

def _chunk_rerank(chunks: list[dict[str, Any]], query: str, src_boost: dict[str, float]):
    qt = _q_terms(query)
    out = []
    for ch in chunks:
        txt = (ch.get("text") or "").lower()
        st = (ch.get("source") or "").lower()
        base = float(ch.get("semantic_score") or 0.0)
        ov = 0.0
        if qt:
            hit = 0
            for t in qt:
                if t in txt:
                    hit += 1
            ov = hit / max(1, len(qt))
        sc = base + (0.25 * ov) + float(src_boost.get(st, 0.0))
        cc = dict(ch)
        cc["semantic_score"] = round(sc, 4)
        out.append(cc)
    out.sort(key=lambda x: (-(float(x.get("semantic_score") or 0.0)), str(x.get("chunk_id") or "")))
    return out


def retrieve_context_pack(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k_entities: int = 5,
    k_chunks: int = 5,
    entity_filters: dict[str, Any] | None = None,
    chunk_filters: dict[str, Any] | None = None,
):
    tc = _ctx_obj(team_context)
    ranked = rank_candidates(team_context=tc, query=query, k=k_entities, filters=entity_filters)
    f2 = chunk_filters or {}
    src_boost = {}
    if not f2:
        f2, src_boost = _infer_chunk_filters(query)
    cm = fetch_internal_chunks_with_meta(team_context=tc, query=query, k=max(3, k_chunks * 2), filters=f2)
    ents = [asdict(c) for c in ranked.candidates]
    chunks = _chunk_rerank(cm.get("chunks") or [], query, src_boost)[:max(0, k_chunks)]
    cits = []
    for c in ents[:3]:
        cits.append({
            "type": "entity",
            "id": c.get("entity_id"),
            "name": c.get("name"),
            "snippet": (c.get("evidence_snippets") or [""])[0],
        })
    for ch in chunks[:3]:
        cits.append({
            "type": "chunk",
            "id": ch.get("chunk_id"),
            "name": ch.get("source") or "internal_chunk",
            "snippet": ch.get("text", "")[:240],
        })
    return {
        "query": (query or "").strip(),
        "team_name": tc.team_name,
        "entity_matches": ents,
        "internal_chunks": chunks,
        "citations": cits,
        "retrieval_meta": {
            "entity": ranked.retrieval_metadata,
            "chunks": {
                "status": cm.get("status"),
                "error": cm.get("error"),
                "raw_row_count": cm.get("raw_row_count"),
                "kept_row_count": cm.get("kept_row_count"),
                "dropped_row_count": cm.get("dropped_row_count"),
                "filters_applied": f2,
            },
        },
    }
