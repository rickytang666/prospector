from __future__ import annotations
from retrieval.config import OVER_RETRIEVE_FACTOR

from retrieval.embeddings import embed_text, get_entity_embedding
from retrieval.models import Entity, TeamContext

def build_query_text(q: str, ctx: TeamContext):
    p = []
    q2 = (q or "").strip()
    if q2: p.append(q2)
    if ctx.context_summary: p.append("Team context: " + ctx.context_summary)
    bs = [b.summary for b in ctx.active_blockers if b.summary]
    if bs: p.append("Blockers: " + " | ".join(bs[:4]))
    if ctx.subsystems: p.append("Subsystems: " + ", ".join(ctx.subsystems[:6]))
    return ". ".join(p).strip()


def _dot(a,b):
    n=min(len(a),len(b)); i=0; s=0.0
    while i<n:
        s += a[i]*b[i]; i+=1
    return s



def _to01(x):
    z=(x+1.0)/2.0
    if z<0: return 0.0
    if z>1: return 1.0
    return z

def semantic_search(entities: list[Entity], query: str, team_context: TeamContext, k: int):
    qtxt = build_query_text(query, team_context)
    qv = embed_text(qtxt)

    out = []
    for e in entities:
        ev = get_entity_embedding(e.entity_id)
        if ev is None: continue
        sim = _to01(_dot(qv,ev))
        out.append((e,sim))

    out.sort(key=lambda x: x[1], reverse=True)
    take = max(1, k*OVER_RETRIEVE_FACTOR)
    return out[:take]
