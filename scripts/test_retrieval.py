#!/usr/bin/env python3
"""
Test retrieval (vector search over entity_embeddings) with your generated embeddings.

Usage (from repo root):
  python scripts/test_retrieval.py
  python scripts/test_retrieval.py "geospatial mapping and RF support"
  python scripts/test_retrieval.py "cloud credits for student teams" --k 10

Requires:
  - .env: SUPABASE_URL, SUPABASE_KEY (or SUPABASE_ANON_KEY), OPENROUTER_API_KEY
  - Supabase: run migrations/003_match_entities_rpc.sql in SQL Editor so
    match_entities_for_team(query_embedding, k, filters) exists and uses entity_embeddings.
  - entity_embeddings populated (run scraper embeddings-only first).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Load env from repo root
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from retrieval.envload import load_project_env
load_project_env()

from retrieval.ranking import rank_candidates
from retrieval.models import TeamContext, Blocker


def main():
    query = "Who can help with geospatial mapping, RF, or cloud credits for student teams?"
    k = 10
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    if "--k" in sys.argv:
        i = sys.argv.index("--k")
        if i + 1 < len(sys.argv):
            k = int(sys.argv[i + 1])

    team_context = TeamContext(
        team_name="UW Orbital",
        repo="https://github.com/UWOrbital/satellite",
        active_blockers=[
            Blocker(summary="Need geospatial mapping for ground station coverage", tags=["mapping", "gis"], severity="high"),
            Blocker(summary="RF signal simulation pipeline", tags=["rf", "simulation"], severity="medium"),
        ],
        subsystems=["Ground Station", "Attitude Determination", "Power Systems"],
        inferred_support_needs=["technical_mentorship", "api_access", "cloud_credits"],
        context_summary="University student team building a cubesat; need sponsor support for tooling and expertise.",
    )

    print(f"Query: {query!r}")
    print(f"k: {k}")
    print()

    out = rank_candidates(team_context=team_context, query=query, k=k)

    meta = out.retrieval_metadata
    src = meta.get("candidate_source", "?")
    db_status = meta.get("db_status", "?")
    print(f"Source: {src}  (db_status={db_status})")
    if meta.get("used_fallback_local"):
        print("(Fell back to local mock data — RPC match_entities_for_team may be missing or failing.)")
    else:
        print("(Using vector embeddings from Supabase entity_embeddings.)")
    print(f"Raw rows: {meta.get('db_raw_row_count', 0)}, kept: {meta.get('db_kept_row_count', 0)}, dropped: {meta.get('db_dropped_row_count', 0)}")
    if meta.get("db_error"):
        print(f"DB error: {meta['db_error']}")
    print()

    print(f"Top {len(out.candidates)} candidates:")
    for i, c in enumerate(out.candidates, 1):
        print(f"  {i}. {c.name} (score={c.overall_score:.3f})")
        print(f"     semantic={c.score_breakdown.semantic_score:.3f} tag={c.score_breakdown.tag_overlap_score:.3f} support={c.score_breakdown.support_fit_score:.3f} affinity={c.score_breakdown.waterloo_affinity_score:.3f}")
        for r in (c.matched_reasons or [])[:2]:
            print(f"     - {r}")
    print()
    print("Done.")


if __name__ == "__main__":
    main()
