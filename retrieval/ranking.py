from __future__ import annotations
import time
from typing import Any
from retrieval.mock_data import get_mock_entities
from retrieval.models import (
    Entity,
    RankedCandidate,
    RankedCandidateResponse,
    ScoreBreakdown,
    TeamContext,
)

def build_stub_candidate(entity: Entity, semantic: float, tag: float, support: float, waterloo: float) -> RankedCandidate:
    overall = (0.4*semantic) + (0.25*tag) + (0.2*support) + (0.15*waterloo)
    reasons = ["testing stub", "derive from retrieval signals later"]

    evidence = [f"{entity.summary} (from entity summary)"]
    if entity.tags:
        evidence.append(f"Entity tags: {', '.join(entity.tags[:4])} (from entity tags)")
    if entity.waterloo_affinity_evidence:
        evidence.append(
            f"{entity.waterloo_affinity_evidence[0].text} (from waterloo_affinity_evidence)"
        )
    return RankedCandidate(
        entity_id=entity.entity_id,
        name=entity.name,
        entity_type=entity.entity_type,
        overall_score=round(overall, 4),
        score_breakdown=ScoreBreakdown(
            semantic_score=semantic,
            tag_overlap_score=tag,
            support_fit_score=support,
            waterloo_affinity_score=waterloo,
        ),
        matched_reasons=reasons,
        evidence_snippets=evidence[:3],
        support_types=entity.support_types,
        waterloo_affinity_evidence=entity.waterloo_affinity_evidence,
    )

def rank_candidates(team_context: TeamContext, query: str, k: int = 5, filters: dict[str, Any] | None = None,) -> RankedCandidateResponse:
    start = time.perf_counter()
    cleaned = (query or "").strip()
    entities = {e.entity_id: e for e in get_mock_entities()}

    scored = [
        build_stub_candidate(entities["ent-mapbox"], semantic=0.90, tag=0.80, support=0.85, waterloo=0.00),
        build_stub_candidate(entities["ent-prof-chen"], semantic=0.86, tag=0.78, support=0.75, waterloo=0.60),
        build_stub_candidate(entities["ent-waterloo-geo"], semantic=0.84, tag=0.76, support=0.72, waterloo=0.80),
        build_stub_candidate(entities["ent-uw-maps-lab"], semantic=0.82, tag=0.70, support=0.68, waterloo=0.80),
        build_stub_candidate(entities["ent-cesium"], semantic=0.80, tag=0.66, support=0.60, waterloo=0.00),
        build_stub_candidate(entities["ent-gcp"], semantic=0.62, tag=0.44, support=0.76, waterloo=0.00),
        build_stub_candidate(entities["ent-aws"], semantic=0.60, tag=0.42, support=0.80, waterloo=0.00),
    ]

    if filters:
        entity_type_filter = filters.get("entity_type")
        if entity_type_filter:
            scored = [c for c in scored if c.entity_type == entity_type_filter]

    scored.sort(key=lambda c: c.overall_score, reverse=True)
    final_candidates = scored[: max(k, 0)]
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    query_summary = cleaned or "No query provided"

    return RankedCandidateResponse(
        query_summary=f"{query_summary} | team={team_context.team_name}",
        candidates=final_candidates,
        retrieval_metadata={
            "mode": "phase0_stub",
            "timing_ms": round(elapsed_ms, 2),
            "corpus_size": len(entities),
            "weights": {
                "semantic": 0.40,
                "tag_overlap": 0.25,
                "support_fit": 0.20,
                "waterloo_affinity": 0.15,
            },
            "filters_applied": filters or {},
        },
    )

#temp stubs:
def get_entity_embedding(entity_id: str) -> list[float] | None: return None
def reindex_entities(entities: list[Entity]) -> int: return len(entities)

