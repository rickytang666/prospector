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

def _q_terms(q: str):
    s=set()
    for w in (q or "").lower().replace("?"," ").replace(","," ").split():
        if len(w)>2 and w not in {"the","and","for","our","with","who","can","help","need","to","of"}:
            s.add(w)
    return s


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

from retrieval.config import RANKING_WEIGHTS, DEFAULT_K
from retrieval.retrieval import semantic_search
from retrieval.embeddings import embed_entities, get_entity_embedding as _get_emb, index_ready, corpus_size

_old_rank_candidates = rank_candidates
_old_get_entity_embedding = get_entity_embedding
_old_reindex_entities = reindex_entities

_ENTS = []

def _boot():
    global _ENTS
    if not _ENTS:
        _ENTS = get_mock_entities()
    if not index_ready():
        embed_entities(_ENTS)

def _s(xs):
    o=set()
    for x in xs:
        x2=(x or "").strip().lower()
        if x2: o.add(x2)
    return o

def _ctx_tags(ctx: TeamContext, q: str):
    c=set()
    for b in ctx.active_blockers: c.update(_s(b.tags))
    for ss in ctx.subsystems:
        ss2=(ss or "").strip().lower()
        if ss2: c.add(ss2)
    for w in (q or "").lower().replace("?"," ").replace(","," ").split():
        if len(w)>2 and w not in {"the","and","for","our","with","who","can","help","need","to","of"}:
            c.add(w)
    return c

def _jac(a,b):
    if not a or not b: return 0.0
    u=len(a.union(b))
    if u==0: return 0.0
    return len(a.intersection(b))/u

def _sup(e: Entity, ctx: TeamContext):
    n=_s(ctx.inferred_support_needs)
    if not n: return 0.0
    h=_s(e.support_types)
    return len(n.intersection(h))/max(1,len(n))

def _wat(e: Entity):
    ev = e.waterloo_affinity_evidence or []
    if not ev: return 0.0
    st={"team_sponsor","official_page","official_partner"}
    if len(ev)>=2:
        for i in ev:
            if (i.type or "").lower() in st: return 1.0
        return 0.8
    if (ev[0].type or "").lower() in st: return 0.6
    return 0.3

def _compose(sem,tag,sup,wat):
    w=RANKING_WEIGHTS
    return w["semantic"]*sem + w["tag_overlap"]*tag + w["support_fit"]*sup + w["waterloo_affinity"]*wat

def _reasons(sb,ov,suphits,wn):
    r=[]
    if sb.semantic_score >= 0.70: r.append("Strong semantic relevance to your current need.")
    if ov: r.append("Direct tag overlap: " + ", ".join(ov[:4]) + ".")
    if suphits: r.append("Support fit: " + ", ".join(suphits[:3]) + ".")
    if wn: r.append("Waterloo-connected: " + wn)
    if not r: r=["Moderate match from available signals."]
    return r[:4]

def _ev(e,ov,suphits):
    z=[f"{e.summary} (from entity summary)"]
    if ov: z.append("Matched tags: " + ", ".join(ov[:5]) + " (from tags)")
    if suphits: z.append("Matching support: " + ", ".join(suphits[:4]) + " (from support_types)")
    elif e.support_types: z.append("Available support: " + ", ".join(e.support_types[:4]) + " (from support_types)")
    if e.waterloo_affinity_evidence: z.append(e.waterloo_affinity_evidence[0].text + " (from waterloo_affinity_evidence)")
    return z[:3]

def _rank_candidates_phase1(team_context: TeamContext, query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    t0 = time.perf_counter()
    _boot()

    raw = semantic_search(_ENTS, query=query, team_context=team_context, k=max(1,k))
    ctx_tags = _ctx_tags(team_context, "") 
    q_tags = _q_terms(query)                

    out=[]
    for e,sem in raw:
        if filters and filters.get("entity_type") and e.entity_type != filters["entity_type"]:
            continue

        et = _s(e.tags)
        n = _s(team_context.inferred_support_needs)
        h = _s(e.support_types)
        suphits = sorted(list(n.intersection(h)))

        q_ov = et.intersection(q_tags) if q_tags else set()
        c_ov = et.intersection(ctx_tags)

        ov = sorted(list(q_ov if q_ov else c_ov))

        q_tag_score = _jac(et, q_tags) if q_tags else 0.0
        ctx_tag_score = _jac(et, ctx_tags)

        t = (0.7 * q_tag_score + 0.3 * ctx_tag_score) if q_tags else ctx_tag_score

        s = _sup(e,team_context)
        w = _wat(e)
        allv = _compose(sem,t,s,w)

        # force query intent to matter more in hackathon mode
        if q_tags:
            if q_ov:
                allv += 0.18 * (len(q_ov) / max(1, len(q_tags)))
            else:
                allv -= 0.08
        if allv < 0.0: allv = 0.0
        if allv > 1.0: allv = 1.0

        sb = ScoreBreakdown(
            semantic_score=round(sem,4),
            tag_overlap_score=round(t,4),
            support_fit_score=round(s,4),
            waterloo_affinity_score=round(w,4),
        )

        wn = e.waterloo_affinity_evidence[0].text if e.waterloo_affinity_evidence else None

        out.append(RankedCandidate(
            entity_id=e.entity_id,
            name=e.name,
            entity_type=e.entity_type,
            overall_score=round(allv,4),
            score_breakdown=sb,
            matched_reasons=_reasons(sb,ov,suphits,wn),
            evidence_snippets=_ev(e,ov,suphits),
            support_types=e.support_types,
            waterloo_affinity_evidence=e.waterloo_affinity_evidence,
        ))

    out.sort(key=lambda x: x.overall_score, reverse=True)
    out = out[:max(0,k)]

    ms = (time.perf_counter()-t0)*1000.0
    return RankedCandidateResponse(
        query_summary=((query or "No query provided").strip()),
        candidates=out,
        retrieval_metadata={
            "mode":"phase1_semantic_plus_rules",
            "timing_ms":round(ms,2),
            "corpus_size":corpus_size(),
            "weights":dict(RANKING_WEIGHTS),
            "filters_applied":filters or {},
        },
    )

# override old stubs, but keep fallback
def rank_candidates(team_context: TeamContext, query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    try:
        return _rank_candidates_phase1(team_context, query, k=k, filters=filters)
    except Exception:
        return _old_rank_candidates(team_context, query, k=k, filters=filters)

def get_entity_embedding(entity_id: str):
    x = _get_emb(entity_id)
    if x is not None: return x
    return _old_get_entity_embedding(entity_id)

def reindex_entities(entities: list[Entity]):
    global _ENTS
    _ENTS = list(entities)
    try:
        return embed_entities(_ENTS)
    except Exception:
        return _old_reindex_entities(entities)
