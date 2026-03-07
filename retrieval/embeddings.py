from __future__ import annotations
import os, math, hashlib
from retrieval.config import EMBEDDING_MODEL, ALLOW_LOCAL_EMBED_FALLBACK, LOCAL_DIM
from retrieval.models import Entity
from retrieval.envload import load_project_env

v_by_id = {}
txt_by_id = {}
client = None

load_project_env()

def _n(v):
    s=0.0
    for x in v: s += x*x
    if s <= 0: return v
    d = math.sqrt(s)
    return [x/d for x in v]

def _local(text: str):
    out = [0.0]*LOCAL_DIM
    t = (text or "").lower().split()
    if not t: return out
    for w in t:
        h = hashlib.sha256(w.encode("utf-8")).digest()
        i=0
        while i < 10:
            j = h[i] % LOCAL_DIM
            sg = 1.0 if h[i+10] % 2 == 0 else -1.0
            out[j] += sg
            i += 1
    return _n(out)

def _get_client():
    global client
    if client is not None: return client
    k = os.getenv("OPENROUTER_API_KEY","").strip()
    if not k: return None
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI(
            api_key=k,
            base_url="https://openrouter.ai/api/v1",
        )
        return client
    except Exception:
        return None


def embed_text(text: str):
    c = _get_client()
    if c is not None:
        try:
            r = c.embeddings.create(model=EMBEDDING_MODEL, input=text)
            return _n([float(x) for x in r.data[0].embedding])
        except Exception:
            pass
    if ALLOW_LOCAL_EMBED_FALLBACK: return _local(text)
    raise RuntimeError("embed failed")

def make_entity_text(e: Entity):
    return f"{e.name}. {e.summary}. Tags: {', '.join(e.tags)}. Support: {', '.join(e.support_types)}."

def embed_entities(entities: list[Entity]):
    v_by_id.clear(); txt_by_id.clear()
    for e in entities:
        t = make_entity_text(e)
        txt_by_id[e.entity_id] = t
        v_by_id[e.entity_id] = embed_text(t)
    return len(v_by_id)

def get_entity_embedding(entity_id: str):
    return v_by_id.get(entity_id)

def index_ready():
    return len(v_by_id) > 0

def corpus_size():
    return len(v_by_id)
