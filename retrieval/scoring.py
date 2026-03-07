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


def waterloo_affinity(e: Entity):
    ev = e.waterloo_affinity_evidence or []
    if not ev: return 0.0

    strong = {"team_sponsor","official_page","official_partner"}

    if len(ev) >= 2:
        got_strong = False
        for z in ev:
            if (z.type or "").lower() in strong:
                got_strong = True
                break
        if got_strong: return 1.0
        return 0.8

    t = (ev[0].type or "").lower()
    if t in strong: return 0.6
    return 0.3


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
