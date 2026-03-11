from __future__ import annotations

from typing import Any
import json

from retrieval.models import Entity, TeamContext, WaterlooAffinityEvidence
from retrieval.supabase_client import fetch_semantic_candidates_from_rpc, get_supabase_client


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


def _to_str_list(v: Any):
    v = _parse_json_maybe(v)
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
    v = _parse_json_maybe(v)
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

def _norm_entity_type(v: Any):
    s = str(v or "").strip().lower()
    if not s:
        return "unknown"
    m = {
        "company": "company",
        "startup": "company",
        "corporation": "company",
        "corp": "company",
        "org": "company",
        "organization": "company",
        "industry_partner": "company",
        "sponsor": "company",
        "provider": "provider",
        "vendor": "provider",
        "tool": "provider",
        "platform": "provider",
        "professor": "professor",
        "faculty": "professor",
        "lab": "lab",
        "research_lab": "lab",
    }
    if s in m:
        return m[s]
    if "prof" in s:
        return "professor"
    if "lab" in s:
        return "lab"
    if "company" in s or "startup" in s or "corp" in s or "org" in s or "sponsor" in s:
        return "company"
    if "provider" in s or "vendor" in s or "tool" in s or "platform" in s:
        return "provider"
    return s


def _row_to_entity(row: dict[str, Any]):
    row = _parse_json_maybe(row)
    if not isinstance(row, dict):
        return None
    eid = str(row.get("entity_id") or row.get("entityId") or row.get("id") or "")
    nm = str(row.get("name") or row.get("entity_name") or row.get("entityName") or "")
    et = _norm_entity_type(row.get("entity_type") or row.get("entityType") or row.get("type"))
    sm = str(row.get("summary") or row.get("description") or row.get("entity_summary") or "")
    tg = _to_str_list(row.get("tags") or row.get("entity_tags"))
    st = _to_str_list(row.get("support_types") or row.get("supports") or row.get("support"))
    wa = _norm_affinity(row.get("waterloo_affinity_evidence") or row.get("waterloo_affinity") or row.get("affinity_evidence"))

    ent = Entity(
        entity_id=eid,
        name=nm,
        entity_type=et,
        summary=sm,
        tags=tg,
        support_types=st,
        waterloo_affinity_evidence=wa,
    )
    sem = _score01(
        row.get(
            "semantic_score",
            row.get("similarity", row.get("score", row.get("cosine_similarity", 0.0))),
        )
    )
    return ent, sem


def fetch_team_sponsors(limit: int = 50) -> list[tuple[Entity, float]]:
    """direct db pull for entities with team_sponsor affinity — guaranteed sponsor pool.
    returns (entity, sem=0.0) so they go through the same scoring pipeline."""
    try:
        cl = get_supabase_client()

        # get entity ids that have team_sponsor evidence
        r = cl.table("affinity_evidence").select("entity_id").eq("type", "team_sponsor").execute()
        ids = list({row["entity_id"] for row in (r.data or []) if row.get("entity_id")})
        if not ids:
            return []
        ids = ids[:limit]

        # fetch entity data in batches
        entity_rows = []
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            r2 = cl.table("entities").select("id, name, entity_type, summary, tags, support_types").in_("id", batch).execute()
            entity_rows.extend(r2.data or [])

        # fetch their affinity evidence
        aff_by_eid: dict[str, list] = {}
        for i in range(0, len(ids), 100):
            batch = ids[i:i + 100]
            r3 = cl.table("affinity_evidence").select("entity_id, type, text, source_url").in_("entity_id", batch).execute()
            for arow in (r3.data or []):
                eid = arow.get("entity_id", "")
                aff_by_eid.setdefault(eid, []).append(arow)

        out = []
        for row in entity_rows:
            eid = str(row.get("id") or "")
            nm = str(row.get("name") or "")
            if not eid or not nm:
                continue
            ent = Entity(
                entity_id=eid,
                name=nm,
                entity_type=str(row.get("entity_type") or "provider"),
                summary=str(row.get("summary") or ""),
                tags=_to_str_list(row.get("tags")),
                support_types=_to_str_list(row.get("support_types")),
                waterloo_affinity_evidence=_norm_affinity(aff_by_eid.get(eid, [])),
            )
            out.append((ent, 0.0))  # sem=0.0, gets boosted by waterloo_affinity weight

        return out
    except Exception as e:
        print(f"fetch_team_sponsors failed: {e}")
        return []


def fetch_candidates_from_db(
    team_context: TeamContext,
    query: str,
    k: int,
    filters: dict[str, Any] | None = None,
):
    x = fetch_candidates_from_db_with_meta(team_context=team_context, query=query, k=k, filters=filters)
    return x["candidates"]


def fetch_candidates_from_db_with_meta(
    team_context: TeamContext,
    query: str,
    k: int,
    filters: dict[str, Any] | None = None,
):
    blockers = []
    for b in team_context.active_blockers:
        if b.summary:
            blockers.append(b.summary)

    try:
        rows = fetch_semantic_candidates_from_rpc(
            query=query,
            team_context_summary=team_context.context_summary,
            blocker_summaries=blockers,
            k=k,
            filters=filters or {},
        )
    except Exception as e:
        return {
            "status": "db_error",
            "error": str(e),
            "raw_row_count": 0,
            "kept_row_count": 0,
            "dropped_row_count": 0,
            "candidates": [],
        }

    out: list[tuple[Entity, float]] = []
    dropped = 0
    for r in rows:
        rr = _parse_json_maybe(r)
        if not isinstance(rr, dict):
            dropped += 1
            continue
        x = _row_to_entity(rr)
        if x is None:
            dropped += 1
            continue
        e, sem = x
        if not e.entity_id or not e.name:
            dropped += 1
            continue
        out.append((e, sem))
    if not out:
        return {
            "status": "db_empty",
            "error": None,
            "raw_row_count": len(rows),
            "kept_row_count": 0,
            "dropped_row_count": dropped,
            "candidates": [],
        }
    return {
        "status": "db_ok",
        "error": None,
        "raw_row_count": len(rows),
        "kept_row_count": len(out),
        "dropped_row_count": dropped,
        "candidates": out,
    }
