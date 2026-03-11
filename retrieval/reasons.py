from __future__ import annotations

from retrieval.models import Entity, ScoreBreakdown


def build_matched_reasons(
    sb: ScoreBreakdown,
    overlap_tags: list[str],
    support_hits: list[str],
    waterloo_note: str | None,
) -> list[str]:
    r = []

    if waterloo_note:
        r.append(waterloo_note)
    elif sb.waterloo_affinity_score >= 0.9:
        r.append("Confirmed Waterloo design team sponsor.")
    elif sb.waterloo_affinity_score >= 0.5:
        r.append("Has known ties to the University of Waterloo.")

    if support_hits:
        r.append(f"Offers {', '.join(support_hits[:3])} — matches your team's stated needs.")

    if overlap_tags:
        r.append(f"Relevant expertise in: {', '.join(overlap_tags[:4])}.")

    if not r:
        if sb.semantic_score >= 0.60:
            r.append("Strong semantic match to your query.")
        elif sb.semantic_score >= 0.40:
            r.append("Moderate match based on company profile.")
        else:
            r.append("Potential match based on available signals.")

    return r[:2]


def build_evidence_snippets(entity: Entity, overlap_tags: list[str], support_hits: list[str]) -> list[str]:
    z = []
    if entity.summary:
        z.append(f"{entity.summary} (from entity summary)")
    if overlap_tags:
        z.append("Matched tags: " + ", ".join(overlap_tags[:5]) + " (from tags)")
    if support_hits:
        z.append("Matching support: " + ", ".join(support_hits[:4]) + " (from support_types)")
    elif entity.support_types:
        z.append("Available support: " + ", ".join(entity.support_types[:4]) + " (from support_types)")
    if entity.waterloo_affinity_evidence:
        z.append(entity.waterloo_affinity_evidence[0].text + " (from waterloo_affinity_evidence)")
    return z[:3]
