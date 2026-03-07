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

from retrieval.config import RANKING_WEIGHTS, DEFAULT_K, LOW_CONFIDENCE_TOP1, MEDIUM_CONFIDENCE_TOP1, MIN_RESULT_SCORE
from retrieval.retrieval import semantic_search
from retrieval.embeddings import embed_entities, get_entity_embedding as _get_emb, index_ready, corpus_size
from retrieval.scoring import jacc, support_fit, waterloo_affinity, compose_scores, clamp01, to_set
from retrieval.reasons import build_matched_reasons, build_evidence_snippets
from retrieval.db_retrieval import fetch_candidates_from_db_with_meta

_ENTS = []

def _boot():
    global _ENTS
    if not _ENTS:
        _ENTS = get_mock_entities()
    if not index_ready():
        embed_entities(_ENTS)

def _s(xs):
    return to_set(xs)

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
    return jacc(a,b)

def _sup(e: Entity, ctx: TeamContext):
    return support_fit(e, ctx)

def _wat(e: Entity):
    return waterloo_affinity(e)

def _compose(sem,tag,sup,wat):
    return compose_scores(sem, tag, sup, wat)

def _reasons(sb,ov,suphits,wn):
    return build_matched_reasons(sb, ov, suphits, wn)

def _ev(e,ov,suphits):
    return build_evidence_snippets(e, ov, suphits)

def _rank_candidates_phase1(team_context: TeamContext, query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    t0 = time.perf_counter()
    _boot()

    raw=[]
    src="supabase"
    db_err=None
    db_status="db_ok"
    db_raw=0
    db_kept=0
    db_drop=0
    m = fetch_candidates_from_db_with_meta(team_context=team_context, query=query, k=max(1, k * 2), filters=filters)
    db_status = m.get("status", "db_error")
    db_err = m.get("error")
    db_raw = int(m.get("raw_row_count", 0) or 0)
    db_kept = int(m.get("kept_row_count", 0) or 0)
    db_drop = int(m.get("dropped_row_count", 0) or 0)
    raw = m.get("candidates") or []
    if not raw:
        src="fallback_local"
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

        if q_tags:
            if q_ov:
                allv += 0.18 * (len(q_ov) / max(1, len(q_tags)))
            else:
                allv -= 0.08
        allv = clamp01(allv)

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
    out = [x for x in out if x.overall_score >= MIN_RESULT_SCORE]
    out = out[:max(0,k)]

    top = out[0].overall_score if out else 0.0
    conf = "low"
    if top >= MEDIUM_CONFIDENCE_TOP1:
        conf = "high"
    elif top >= LOW_CONFIDENCE_TOP1:
        conf = "medium"
    if conf == "low" and len(out) > 3:
        out = out[:3]

    ms = (time.perf_counter()-t0)*1000.0
    return RankedCandidateResponse(
        query_summary=((query or "No query provided").strip()),
        candidates=out,
        retrieval_metadata={
            "mode":"phase1_semantic_plus_rules",
            "timing_ms":round(ms,2),
            "corpus_size":corpus_size(),
            "candidate_source":src,
            "db_error":db_err,
            "db_status":db_status,
            "db_raw_row_count":db_raw,
            "db_kept_row_count":db_kept,
            "db_dropped_row_count":db_drop,
            "confidence":conf,
            "weights":dict(RANKING_WEIGHTS),
            "filters_applied":filters or {},
        },
    )

def rank_candidates(team_context: TeamContext, query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    return _rank_candidates_phase1(team_context, query, k=k, filters=filters)

def get_entity_embedding(entity_id: str):
    return _get_emb(entity_id)

def reindex_entities(entities: list[Entity]):
    global _ENTS
    _ENTS = list(entities)
    return embed_entities(_ENTS)
