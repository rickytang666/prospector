"""quick rag test — run with: python test_rag.py "your query here" """
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from retrieval.api import find_support_dict as find_sponsors_dict

# edit this to match the team you want to test with
TEAM_CONTEXT = {
    "team_name": "UW Orbital",
    "repo": "",
    "subsystems": [
        "Ground Station Communication",
        "Attitude Determination and Control",
        "Power Systems",
        "On-Board Data Handling",
        "Payload Imaging",
    ],
    "active_blockers": [
        {"summary": "Lacks geospatial mapping tooling for ground station coverage", "tags": ["gis", "mapping"], "severity": "high"},
        {"summary": "No existing RF signal simulation pipeline", "tags": ["rf", "communications"], "severity": "high"},
        {"summary": "Limited embedded ML inference experience", "tags": ["embedded", "ai"], "severity": "medium"},
    ],
    "inferred_support_needs": ["sponsorship", "software_credits", "technical_mentorship"],
    "context_summary": "Satellite design team building a CubeSat with ground station and on-board computing challenges.",
}

query = sys.argv[1] if len(sys.argv) > 1 else "We need RF and embedded systems support for our satellite ground station."

print(f"query: {query}")
print(f"team:  {TEAM_CONTEXT['team_name']}\n")

result = find_sponsors_dict(team_context=TEAM_CONTEXT, query=query, k=10)

candidates = result.get("candidates", [])
if not candidates:
    print("no results returned")
    meta = result.get("retrieval_metadata", {})
    print(f"status: {meta.get('db_status')} | error: {meta.get('db_error')}")
    sys.exit(0)

print(f"--- top {len(candidates)} results ---\n")
for i, c in enumerate(candidates):
    score = c.get("overall_score", 0)
    sb = c.get("score_breakdown", {})
    print(f"[{i+1}] {c.get('name')}  (score={score})")
    print(f"     sem={sb.get('semantic_score')} | aff={sb.get('waterloo_affinity_score')} | tag={sb.get('tag_overlap_score')} | sup={sb.get('support_fit_score')}")
    for r in c.get("matched_reasons", []):
        print(f"     > {r}")
    print()

meta = result.get("retrieval_metadata", {})
print(f"mode: {meta.get('mode')} | semantic: {meta.get('semantic_candidates')} | sponsors: {meta.get('sponsor_pool_size')} | time: {meta.get('timing_ms')}ms")
