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
    cm = fetch_internal_chunks_with_meta(team_context=tc, query=query, k=k_chunks, filters=chunk_filters)
    ents = [asdict(c) for c in ranked.candidates]
    chunks = cm.get("chunks") or []
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
            },
        },
    }
