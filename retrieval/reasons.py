from __future__ import annotations

from retrieval.models import Entity, ScoreBreakdown


def build_matched_reasons(
    sb: ScoreBreakdown,
    overlap_tags: list[str],
    support_hits: list[str],
    waterloo_note: str | None,
):
    r = []
    if sb.semantic_score >= 0.60:
        r.append("Strong semantic relevance to your current need.")
    elif sb.semantic_score >= 0.45:
        r.append("Moderate semantic relevance to your current need.")
    if not r:
        r = ["Semantic match from available context."]
    return r[:1]


def build_evidence_snippets(entity: Entity, overlap_tags: list[str], support_hits: list[str]):
    z = [f"{entity.summary} (from entity summary)"]
    if overlap_tags:
        z.append("Matched tags: " + ", ".join(overlap_tags[:5]) + " (from tags)")
    if support_hits:
        z.append("Matching support: " + ", ".join(support_hits[:4]) + " (from support_types)")
    elif entity.support_types:
        z.append("Available support: " + ", ".join(entity.support_types[:4]) + " (from support_types)")
    if entity.waterloo_affinity_evidence:
        z.append(entity.waterloo_affinity_evidence[0].text + " (from waterloo_affinity_evidence)")
    return z[:3]
