from __future__ import annotations
import time
from typing import Any
from retrieval.models import (
    Blocker,
    Entity,
    RankedCandidate,
    RankedCandidateResponse,
    ScoreBreakdown,
    TeamContext,
)
from retrieval.config import (
    RANKING_WEIGHTS,
    RANKING_WEIGHTS_PROVIDERS,
    RANKING_WEIGHTS_SPONSORS,
    DEFAULT_K,
    SEMANTIC_CANDIDATE_K,
    SPONSOR_POOL_K,
    LLM_RERANK_CANDIDATE_K,
    LOW_CONFIDENCE_TOP1,
    MEDIUM_CONFIDENCE_TOP1,
    MIN_RESULT_SCORE,
    MIN_SEMANTIC_SCORE,
)
from retrieval.scoring import jacc, support_fit, waterloo_affinity, clamp01, to_set
from retrieval.reasons import build_matched_reasons, build_evidence_snippets
from retrieval.db_retrieval import fetch_candidates_from_db_with_meta, fetch_team_sponsors, fill_canonical_urls
from retrieval.llm_ranking import llm_rerank


def _q_terms(q: str):
    s = set()
    for w in (q or "").lower().replace("?", " ").replace(",", " ").split():
        if len(w) > 2 and w not in {"the", "and", "for", "our", "with", "who", "can", "help", "need", "to", "of"}:
            s.add(w)
    return s


def _ctx_tags(ctx: TeamContext, q: str):
    c = set()
    for b in ctx.active_blockers:
        c.update(to_set(b.tags))
    for ss in ctx.subsystems:
        ss2 = (ss or "").strip().lower()
        if ss2:
            c.add(ss2)
    for w in (q or "").lower().replace("?", " ").replace(",", " ").split():
        if len(w) > 2 and w not in {"the", "and", "for", "our", "with", "who", "can", "help", "need", "to", "of"}:
            c.add(w)
    return c


def _compose(sem, tag, sup, wat, weights):
    return (
        float(weights["semantic"]) * sem +
        float(weights["tag_overlap"]) * tag +
        float(weights["support_fit"]) * sup +
        float(weights["waterloo_affinity"]) * wat
    )


def _profile_weights(profile: str):
    p = (profile or "").strip().lower()
    if p == "sponsors":
        return dict(RANKING_WEIGHTS_SPONSORS)
    if p == "providers":
        return dict(RANKING_WEIGHTS_PROVIDERS)
    return dict(RANKING_WEIGHTS)


def _already_sponsors_team(e: Entity, team_name: str) -> bool:
    """true if this entity is already a known sponsor of the querying team.
    checks affinity evidence text for the team name — data-driven, no hardcoding."""
    team_lower = team_name.strip().lower()
    for ev in (e.waterloo_affinity_evidence or []):
        if team_lower in (ev.text or "").lower():
            return True
    return False


def _entity_ok(e: Entity, filters: dict[str, Any] | None):
    if not filters:
        return True
    t = str(filters.get("entity_type", "")).strip().lower()
    if t and (e.entity_type or "").strip().lower() != t:
        return False
    tag_any = to_set([str(x) for x in (filters.get("tags_any") or [])])
    if tag_any and not to_set(e.tags).intersection(tag_any):
        return False
    sup_any = to_set([str(x) for x in (filters.get("support_types_any") or [])])
    if sup_any and not to_set(e.support_types).intersection(sup_any):
        return False
    return True


def _dedupe(rows: list[RankedCandidate]) -> list[RankedCandidate]:
    best: dict[str, RankedCandidate] = {}
    for c in rows:
        key = (c.name or "").strip().lower()
        prev = best.get(key)
        if prev is None or c.overall_score > prev.overall_score:
            best[key] = c
    out = list(best.values())
    out.sort(key=lambda x: (-x.overall_score, x.name.lower()))
    return out


def _ctx_obj(team_context: TeamContext | dict[str, Any]):
    warns = []
    if isinstance(team_context, TeamContext):
        return team_context, warns
    if not isinstance(team_context, dict):
        return TeamContext(team_name="unknown", repo="", active_blockers=[], subsystems=[], inferred_support_needs=[], context_summary=""), ["team_context_not_dict"]
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
    tc = TeamContext(
        team_name=str(team_context.get("team_name", "unknown")),
        repo=str(team_context.get("repo", "")),
        active_blockers=ab,
        subsystems=[str(x) for x in (team_context.get("subsystems") or [])],
        inferred_support_needs=[str(x) for x in (team_context.get("inferred_support_needs") or [])],
        context_summary=str(team_context.get("context_summary", "")),
    )
    if not tc.team_name or tc.team_name == "unknown":
        warns.append("team_name_missing")
    if not tc.active_blockers:
        warns.append("active_blockers_empty")
    return tc, warns


def _score_entity(e: Entity, sem: float, weights: dict, ctx_tags: set, q_tags: set, tc: TeamContext) -> RankedCandidate:
    et = to_set(e.tags)
    n = to_set(tc.inferred_support_needs)
    h = to_set(e.support_types)
    suphits = sorted(list(n.intersection(h)))

    q_ov = et.intersection(q_tags) if q_tags else set()
    c_ov = et.intersection(ctx_tags)
    ov = sorted(list(q_ov if q_ov else c_ov))

    q_tag_score = jacc(et, q_tags) if q_tags else 0.0
    ctx_tag_score = jacc(et, ctx_tags)
    tag_score = (0.7 * q_tag_score + 0.3 * ctx_tag_score) if q_tags else ctx_tag_score

    sup_score = support_fit(e, tc)
    wat_score = waterloo_affinity(e)
    total = _compose(sem, tag_score, sup_score, wat_score, weights)

    # small bonus if query tags directly match entity tags
    if q_tags and float(weights.get("tag_overlap", 0.0)) > 0.0:
        if q_ov:
            total += 0.03 * (len(q_ov) / max(1, len(q_tags)))
        else:
            total -= 0.01

    total = clamp01(total)

    sb = ScoreBreakdown(
        semantic_score=round(sem, 4),
        tag_overlap_score=round(tag_score, 4),
        support_fit_score=round(sup_score, 4),
        waterloo_affinity_score=round(wat_score, 4),
    )
    wn = e.waterloo_affinity_evidence[0].text if e.waterloo_affinity_evidence else None
    reasons = build_matched_reasons(sb, ov, suphits, wn)
    if not reasons:
        reasons = ["Relevant match based on available signals."]

    return RankedCandidate(
        entity_id=e.entity_id,
        name=e.name,
        entity_type=e.entity_type,
        overall_score=round(total, 4),
        score_breakdown=sb,
        matched_reasons=reasons,
        evidence_snippets=build_evidence_snippets(e, ov, suphits),
        support_types=e.support_types,
        canonical_url=e.canonical_url,
        tags=e.tags,
        waterloo_affinity_evidence=e.waterloo_affinity_evidence,
    )


def _rank_candidates_phase1(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = DEFAULT_K,
    filters: dict[str, Any] | None = None,
    profile: str = "providers",
):
    t0 = time.perf_counter()
    tc, norm_warn = _ctx_obj(team_context)
    q = (query or "").strip() or tc.context_summary or "general support"

    kk = max(1, min(int(k) if isinstance(k, int) else DEFAULT_K, 200))
    weights = _profile_weights(profile)
    filters2 = dict(filters or {})

    # step 1: semantic search — pull top 100
    m = fetch_candidates_from_db_with_meta(team_context=tc, query=q, k=SEMANTIC_CANDIDATE_K, filters=filters2)
    db_status = m.get("status", "db_error")
    db_err = m.get("error")
    semantic_raw = m.get("candidates") or []
    if semantic_raw:
        fill_canonical_urls(semantic_raw)

    # step 2: guaranteed sponsor pool — design team sponsors regardless of semantic score
    sponsor_raw = fetch_team_sponsors(limit=SPONSOR_POOL_K)

    if not semantic_raw and not sponsor_raw:
        ms = (time.perf_counter() - t0) * 1000.0
        return RankedCandidateResponse(
            query_summary=q,
            candidates=[],
            retrieval_metadata={
                "mode": "no_results",
                "timing_ms": round(ms, 2),
                "db_status": db_status,
                "db_error": db_err,
                "candidate_source": "none",
                "profile": profile,
            },
        )

    # step 3: merge + score
    ctx_tags = _ctx_tags(tc, "")
    q_tags = _q_terms(q)

    # track which entities came from sponsor pool (sem=0.0 already)
    all_raw = list(semantic_raw)
    sponsor_ids = {e.entity_id for e, _ in sponsor_raw}
    # only add sponsors not already in semantic results
    semantic_ids = {e.entity_id for e, _ in semantic_raw}
    for e, sem in sponsor_raw:
        if e.entity_id not in semantic_ids:
            all_raw.append((e, sem))

    team_lower = tc.team_name.strip().lower()
    scored = []
    for e, sem in all_raw:
        if not _entity_ok(e, filters2):
            continue
        # skip the team itself and any company already sponsoring this team
        if e.name.strip().lower() == team_lower:
            continue
        if _already_sponsors_team(e, tc.team_name):
            continue
        # hard semantic floor — high affinity can't rescue a semantically irrelevant company
        if sem < MIN_SEMANTIC_SCORE:
            continue
        scored.append(_score_entity(e, sem, weights, ctx_tags, q_tags, tc))

    # step 4: dedup + filter + sort
    scored = _dedupe(scored)
    scored = [x for x in scored if x.overall_score >= MIN_RESULT_SCORE]

    src = "supabase" if semantic_raw else ("sponsors_only" if sponsor_raw else "none")

    # step 5: llm rerank on top LLM_RERANK_CANDIDATE_K
    llm_input = scored[:LLM_RERANK_CANDIDATE_K]
    final = llm_rerank(llm_input, q, tc, kk)

    # confidence from top score
    top = final[0].overall_score if final else 0.0
    conf = "high" if top >= MEDIUM_CONFIDENCE_TOP1 else ("medium" if top >= LOW_CONFIDENCE_TOP1 else "low")
    if conf == "low" and len(final) > 3:
        final = final[:3]

    ms = (time.perf_counter() - t0) * 1000.0
    return RankedCandidateResponse(
        query_summary=q,
        candidates=final,
        retrieval_metadata={
            "mode": "semantic_plus_sponsors_llm_rerank",
            "timing_ms": round(ms, 2),
            "query_used": q,
            "requested_k": k,
            "returned_k": len(final),
            "semantic_candidates": len(semantic_raw),
            "sponsor_pool_size": len(sponsor_raw),
            "total_before_llm": len(llm_input),
            "candidate_source": src,
            "db_status": db_status,
            "db_error": db_err,
            "confidence": conf,
            "weights": weights,
            "profile": profile,
            "filters_applied": filters2,
            "normalization_warnings": norm_warn,
        },
    )


def rank_candidates(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = DEFAULT_K,
    filters: dict[str, Any] | None = None,
    profile: str = "providers",
):
    return _rank_candidates_phase1(team_context, query, k=k, filters=filters, profile=profile)


def get_entity_embedding(entity_id: str):
    from retrieval.embeddings import get_entity_embedding as _get_emb
    return _get_emb(entity_id)


def reindex_entities(entities: list[Entity]):
    from retrieval.embeddings import embed_entities
    return embed_entities(entities)
