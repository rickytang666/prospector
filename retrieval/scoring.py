from __future__ import annotations
from retrieval.config import RANKING_WEIGHTS
from retrieval.models import Entity, TeamContext


def to_set(xs: list[str]):
    s=set()
    for x in xs:
        y=(x or "").strip().lower()
        if y: s.add(y)
    return s


def jacc(a: set[str], b: set[str]):
    if not a or not b: return 0.0
    u = len(a.union(b))
    if u == 0: return 0.0
    return len(a.intersection(b)) / u


def support_fit(e: Entity, ctx: TeamContext):
    n = to_set(ctx.inferred_support_needs)
    if not n: return 0.0
    h = to_set(e.support_types)
    return len(n.intersection(h)) / max(1, len(n))


def waterloo_tier_score_and_label(e: Entity):
    ev = e.waterloo_affinity_evidence or []
    if not ev:
        return 0.0, "None"
    tier = {
        "team_sponsor": (1.00, "Sponsor"),
        "waterloo_partner": (0.90, "Partner"),
        "official_partner": (0.90, "Partner"),
        "waterloo_alumni_founder": (0.75, "Alumni"),
        "alumni_link": (0.75, "Alumni"),
        "startup_incubator": (0.55, "Incubator"),
        "yc_company": (0.35, "YC"),
        "official_page": (0.35, "UW-Linked"),
    }
    best = 0.0
    best_label = "UW-Linked"
    seen = set()
    for z in ev:
        t = (z.type or "").strip().lower()
        if not t:
            continue
        seen.add(t)
        sc, lb = tier.get(t, (0.20, "UW-Linked"))
        if sc > best:
            best = sc
            best_label = lb
    if len(seen) > 1:
        best = min(1.0, best + 0.05)
    return best, best_label


def waterloo_affinity(e: Entity):
    sc, _ = waterloo_tier_score_and_label(e)
    return sc


def compose_scores(sem: float, tag: float, sup: float, wat: float):
    w = RANKING_WEIGHTS
    return (
        w["semantic"]*sem +
        w["tag_overlap"]*tag +
        w["support_fit"]*sup +
        w["waterloo_affinity"]*wat
    )


def clamp01(x: float):
    if x < 0.0: return 0.0
    if x > 1.0: return 1.0
    return x
