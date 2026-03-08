import json
import os
from typing import Any
from pydantic import BaseModel

from retrieval.models import RankedCandidate, ScoreBreakdown, TeamContext
from openai import OpenAI
from config import OPENROUTER_API_KEY

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# You can use gemini-2.5-flash or similar with a large context window
MODEL = "google/gemini-2.5-flash-lite"

_companies_cache = None

def _load_companies():
    global _companies_cache
    if _companies_cache is not None:
        return _companies_cache
    
    import pathlib
    # Load data/companies.json
    path = pathlib.Path(__file__).parent.parent / "data" / "companies.json"
    if not path.exists():
        _companies_cache = []
        return []
    
    with open(path, "r") as f:
        _companies_cache = json.load(f)
    return _companies_cache

def llm_rank_candidates_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = 5,
    filters: dict[str, Any] | None = None,
    profile: str = "providers"
) -> dict[str, Any]:
    companies = _load_companies()
    
    # Optional filtering by profile could be done here if needed.
    
    # Prepare the list of companies for the prompt:
    # We only need 'name', 'source_type', and 'association' to save tokens and give context.
    companies_min = []
    for c in companies:
        nm = c.get("name")
        if not nm:
            continue
        st = c.get("source_type", "")
        asc = c.get("association", "")
        # Minimal string to represent this company
        rep = f'"{nm}"'
        if st or asc:
            rep += f' (Tags: {st} {asc})'
        companies_min.append(rep)
        
    companies_str = "\n".join(companies_min)
    
    q_text = (query or "").strip()
    
    if isinstance(team_context, dict):
        tc_dict = team_context
    else:
        tc_dict = {
            "team_name": team_context.team_name,
            "subsystems": team_context.subsystems,
            "tech_stack": getattr(team_context, "tech_stack", []),
            "blockers": [b.summary for b in getattr(team_context, "active_blockers", []) if hasattr(b, "summary")]
        }
        
    prompt = f"""You are a specialized RAG engine that matches university engineering design/software teams with companies for support or sponsorship.

Query/Need:
{q_text}

Team Context:
{json.dumps(tc_dict, indent=2)}

Available Companies (name and tags):
{companies_str}

Please select the top {k} MOST relevant companies from the 'Available Companies' list that can fulfill the query and support this team.
Output exactly a JSON object in this format (no markdown code blocks, just pure JSON):
{{
  "candidates": [
    {{
      "name": "Exact matched name from the list",
      "score": 0.95,
      "reasons": ["Reason 1 why this matches the team", "Reason 2"]
    }}
  ]
}}
Order them by score descending. Include {k} candidates.
"""

    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )

    raw = res.choices[0].message.content
    
    try:
        parsed = json.loads(raw)
        extracted = parsed.get("candidates", [])
    except Exception as e:
        print(f"Failed to parse LLM ranking: {e}")
        extracted = []
        
    out = []
    for idx, c in enumerate(extracted):
        nm = c.get("name", "Unknown")
        score = float(c.get("score", 1.0 - (idx * 0.1)))
        reasons = c.get("reasons", ["Matched by LLM reasoning"])
        
        # Match back to original company to get URLs etc.
        orig = next((x for x in companies if x.get("name", "").lower() == nm.lower()), {})
        
        url = orig.get("url", "")
        if url:
            reasons.append(f"Website: {url}")
            
        sb = ScoreBreakdown(
            semantic_score=score,
            tag_overlap_score=0.0,
            support_fit_score=0.0,
            waterloo_affinity_score=0.0,
        )
        
        cand = RankedCandidate(
            entity_id=nm.lower().replace(" ", "_"),
            name=nm,
            entity_type="company",
            overall_score=score,
            score_breakdown=sb,
            matched_reasons=reasons,
            evidence_snippets=["LLM selected this candidate"],
            support_types=[],
            waterloo_affinity_evidence=[]
        )
        out.append(cand)
        
    from retrieval.api import asdict
    return {
        "query_summary": q_text,
        "candidates": [asdict(c) for c in out],
        "retrieval_metadata": {
            "mode": "llm_full_array",
            "timing_ms": 0,
            "query_used": q_text,
            "requested_k": k,
            "returned_k": len(out),
            "corpus_size": len(companies),
            "candidate_source": "llm_in_memory",
            "confidence": "high",
            "profile": profile,
            "filters_applied": filters
        }
    }
