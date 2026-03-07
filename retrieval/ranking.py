from __future__ import annotations
import time
from typing import Any
from retrieval.mock_data import get_mock_entities
from retrieval.models import (
    Blocker,
    Entity,
    RankedCandidate,
    RankedCandidateResponse,
    ScoreBreakdown,
    TeamContext,
)
from retrieval.config import RANKING_WEIGHTS, DEFAULT_K, LOW_CONFIDENCE_TOP1, MEDIUM_CONFIDENCE_TOP1, MIN_RESULT_SCORE
from retrieval.retrieval import semantic_search
from retrieval.embeddings import embed_entities, get_entity_embedding as _get_emb, index_ready, corpus_size
from retrieval.scoring import jacc, support_fit, waterloo_affinity, compose_scores, clamp01, to_set
from retrieval.reasons import build_matched_reasons, build_evidence_snippets
from retrieval.db_retrieval import fetch_candidates_from_db_with_meta

_ENTS = []

def _q_terms(q: str):
    s=set()
    for w in (q or "").lower().replace("?"," ").replace(","," ").split():
        if len(w)>2 and w not in {"the","and","for","our","with","who","can","help","need","to","of"}:
            s.add(w)
    return s

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
    r = build_matched_reasons(sb, ov, suphits, wn)
    if not r:
        return ["Moderate match from available signals."]
    return r

def _ev(e,ov,suphits):
    z = build_evidence_snippets(e, ov, suphits)
    if not z:
        return [f"{e.summary} (from entity summary)"] if e.summary else ["No evidence available (fallback)."]
    return z

def _arr(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    if isinstance(v, str):
        if "," in v:
            return [x.strip() for x in v.split(",") if x.strip()]
        z = v.strip()
        return [z] if z else []
    return [str(v)]

def _entity_ok(e: Entity, filters: dict[str, Any] | None):
    if not filters:
        return True
    t = str(filters.get("entity_type", "")).strip().lower()
    if t and (e.entity_type or "").strip().lower() != t:
        return False
    tag_any = to_set(_arr(filters.get("tags_any")))
    if tag_any:
        et = to_set(e.tags)
        if not et.intersection(tag_any):
            return False
    sup_any = to_set(_arr(filters.get("support_types_any")))
    if sup_any:
        es = to_set(e.support_types)
        if not es.intersection(sup_any):
            return False
    return True

def _src_from_db(db_status: str, has_rows: bool):
    if has_rows:
        return "supabase"
    if db_status == "db_error":
        return "fallback_local_db_error"
    if db_status == "db_empty":
        return "fallback_local_db_empty"
    return "fallback_local"

def _dedupe_candidates(rows: list[RankedCandidate]):
    best = {}
    for c in rows:
        key = ((c.name or "").strip().lower(), (c.entity_type or "").strip().lower())
        prev = best.get(key)
        if prev is None or c.overall_score > prev.overall_score:
            best[key] = c
    out = list(best.values())
    out.sort(key=lambda x: (-x.overall_score, x.name.lower(), x.entity_id))
    return out

def _ctx_obj(team_context: TeamContext | dict[str, Any]):
    warns=[]
    if isinstance(team_context, TeamContext):
        return team_context, warns
    if not isinstance(team_context, dict):
        return TeamContext(team_name="unknown", repo="", active_blockers=[], subsystems=[], inferred_support_needs=[], context_summary=""), ["team_context_not_dict"]
    ab = []
    for b in (team_context.get("active_blockers") or []):
        if isinstance(b, Blocker):
            ab.append(b)
            continue
        if isinstance(b, dict):
            ab.append(Blocker(
                summary=str(b.get("summary","")),
                tags=[str(x) for x in (b.get("tags") or [])],
                severity=str(b.get("severity","medium")),
            ))
            continue
    tc = TeamContext(
        team_name=str(team_context.get("team_name","unknown")),
        repo=str(team_context.get("repo","")),
        active_blockers=ab,
        subsystems=[str(x) for x in (team_context.get("subsystems") or [])],
        inferred_support_needs=[str(x) for x in (team_context.get("inferred_support_needs") or [])],
        context_summary=str(team_context.get("context_summary","")),
    )
    if not tc.team_name or tc.team_name == "unknown":
        warns.append("team_name_missing")
    if not tc.active_blockers:
        warns.append("active_blockers_empty")
    return tc, warns

def _rank_candidates_phase1(team_context: TeamContext | dict[str, Any], query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    t0 = time.perf_counter()
    _boot()
    tc, norm_warn = _ctx_obj(team_context)
    q = (query or "").strip()
    if not q:
        q = tc.context_summary or "general support"
    kk = int(k) if isinstance(k, int) else DEFAULT_K
    if kk < 1:
        kk = 1
    if kk > 25:
        kk = 25
    kk2 = max(1, kk * 2)

    raw=[]
    db_err=None
    db_status="db_ok"
    db_raw=0
    db_kept=0
    db_drop=0
    m = fetch_candidates_from_db_with_meta(team_context=tc, query=q, k=kk2, filters=filters)
    db_status = m.get("status", "db_error")
    db_err = m.get("error")
    db_raw = int(m.get("raw_row_count", 0) or 0)
    db_kept = int(m.get("kept_row_count", 0) or 0)
    db_drop = int(m.get("dropped_row_count", 0) or 0)
    raw = m.get("candidates") or []
    src = _src_from_db(db_status, bool(raw))
    if not raw:
        raw = semantic_search(_ENTS, query=q, team_context=tc, k=kk)
    ctx_tags = _ctx_tags(tc, "")
    q_tags = _q_terms(q)

    out=[]
    for e,sem in raw:
        if not _entity_ok(e, filters):
            continue
        et = _s(e.tags)
        n = _s(tc.inferred_support_needs)
        h = _s(e.support_types)
        suphits = sorted(list(n.intersection(h)))
        q_ov = et.intersection(q_tags) if q_tags else set()
        c_ov = et.intersection(ctx_tags)
        ov = sorted(list(q_ov if q_ov else c_ov))
        q_tag_score = _jac(et, q_tags) if q_tags else 0.0
        ctx_tag_score = _jac(et, ctx_tags)
        t = (0.7 * q_tag_score + 0.3 * ctx_tag_score) if q_tags else ctx_tag_score
        s = _sup(e,tc)
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

    out = _dedupe_candidates(out)
    out = [x for x in out if x.overall_score >= MIN_RESULT_SCORE]
    out = out[:kk]
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
        query_summary=q,
        candidates=out,
        retrieval_metadata={
            "mode":"phase1_semantic_plus_rules",
            "timing_ms":round(ms,2),
            "query_used":q,
            "requested_k":k,
            "returned_k":len(out),
            "over_retrieve_k":kk2,
            "corpus_size":corpus_size(),
            "candidate_source":src,
            "db_error":db_err,
            "db_status":db_status,
            "db_raw_row_count":db_raw,
            "db_kept_row_count":db_kept,
            "db_dropped_row_count":db_drop,
            "confidence":conf,
            "used_fallback_local":src != "supabase",
            "normalization_warnings":norm_warn,
            "weights":dict(RANKING_WEIGHTS),
            "filters_applied":filters or {},
        },
    )

def rank_candidates(team_context: TeamContext | dict[str, Any], query: str, k: int = DEFAULT_K, filters: dict[str, Any] | None = None):
    return _rank_candidates_phase1(team_context, query, k=k, filters=filters)

def get_entity_embedding(entity_id: str):
    return _get_emb(entity_id)

def reindex_entities(entities: list[Entity]):
    global _ENTS
    _ENTS = list(entities)
    return embed_entities(_ENTS)
