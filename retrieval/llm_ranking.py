import json
import os
from retrieval.models import RankedCandidate, TeamContext
from retrieval.config import LLM_RERANK_MODEL


def _get_client():
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    except Exception:
        return None


def llm_rerank(
    candidates: list[RankedCandidate],
    query: str,
    tc: TeamContext,
    k: int,
) -> list[RankedCandidate]:
    """single llm call on top candidates — picks best k and generates specific reasons.
    falls back to math order if llm fails or no key."""
    if not candidates:
        return []
    if len(candidates) <= k:
        return candidates

    client = _get_client()
    if not client:
        return candidates[:k]

    # build compact candidate list for the prompt
    lines = []
    for i, c in enumerate(candidates):
        summary = ""
        if c.evidence_snippets:
            summary = c.evidence_snippets[0].replace(" (from entity summary)", "").strip()[:120]
        aff = c.waterloo_affinity_evidence[0].text if c.waterloo_affinity_evidence else ""
        tags_str = ", ".join(c.tags[:6]) if c.tags else ""
        line = f"{i}. {c.name}"
        if tags_str:
            line += f" | {tags_str}"
        if summary:
            line += f" | {summary}"
        if aff:
            line += f" | UW: {aff}"
        lines.append(line)

    blockers = " | ".join(b.summary for b in tc.active_blockers if b.summary)
    subsystems = ", ".join(tc.subsystems[:5]) if tc.subsystems else ""
    needs = ", ".join(tc.inferred_support_needs[:5]) if tc.inferred_support_needs else ""

    prompt = f"""You match engineering design teams with companies for sponsorship or technical support.

Team: {tc.team_name}
Query: {query}
Subsystems: {subsystems}
Blockers: {blockers}
Support needs: {needs}

Candidates (pre-ranked by math score, pick the best {k}):
{chr(10).join(lines)}

Pick the best {k} companies. Rules:
- Only include companies whose domain is genuinely relevant to the query — if the query is about drones/hardware/aerospace, do NOT include software-only companies like GitHub, Slack, Notion, etc.
- Be specific in reasons — mention the team's actual technical needs, not generic praise.
- Return JSON only:
{{"picks": [{{"idx": 0, "reason": "one specific sentence why this company fits this team's needs"}}]}}

Order by best match first. idx must be from the list above."""

    try:
        resp = client.chat.completions.create(
            model=LLM_RERANK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=1000,
        )
        raw = json.loads(resp.choices[0].message.content)
        picks = raw.get("picks", [])

        out = []
        seen: set[int] = set()
        for p in picks:
            idx = p.get("idx")
            reason = str(p.get("reason", "")).strip()
            if not isinstance(idx, int) or idx < 0 or idx >= len(candidates):
                continue
            if idx in seen:
                continue
            seen.add(idx)
            c = candidates[idx]
            if reason:
                c.matched_reasons = [reason]
            out.append(c)
            if len(out) >= k:
                break

        if not out:
            return candidates[:k]

        # backfill from math order if llm returned fewer than k
        for i, c in enumerate(candidates):
            if i not in seen and len(out) < k:
                out.append(c)

        return out[:k]

    except Exception as e:
        print(f"llm rerank failed: {e}")
        return candidates[:k]
