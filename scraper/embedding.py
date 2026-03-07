#entity embeddings for semantic search
from __future__ import annotations

import math
import os
from typing import Any

# Same as retrieval.config for RPC compatibility
EMBEDDING_MODEL = "openai/text-embedding-3-small"
EMBEDDING_DIM = 1536

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    k = (os.getenv("OPENROUTER_API_KEY") or "").strip()
    if not k:
        return None
    try:
        from openai import OpenAI
        _client = OpenAI(
            api_key=k,
            base_url="https://openrouter.ai/api/v1",
        )
        return _client
    except Exception:
        return None


def _l2_normalize(v: list[float]) -> list[float]:
    s = sum(x * x for x in v)
    if s <= 0:
        return v
    d = math.sqrt(s)
    return [x / d for x in v]


def make_entity_text(entity: dict[str, Any]) -> str:

    name = (entity.get("name") or "").strip()
    summary = (entity.get("summary") or "").strip()
    tags = entity.get("tags") or []
    support_types = entity.get("support_types") or []
    if not isinstance(tags, list):
        tags = []
    if not isinstance(support_types, list):
        support_types = []
    tags_str = ", ".join(str(t).strip() for t in tags if str(t).strip())
    support_str = ", ".join(str(s).strip() for s in support_types if str(s).strip())
    return f"{name}. {summary}. Tags: {tags_str}. Support: {support_str}.".strip()


def embed_entity(entity: dict[str, Any]) -> list[float] | None:

    client = _get_client()
    if not client:
        return None
    text = make_entity_text(entity)
    if not text or not text.replace(".", "").strip():
        return None
    try:
        r = client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        vec = [float(x) for x in r.data[0].embedding]
        return _l2_normalize(vec)
    except Exception:
        return None


def get_embedding_error_hint() -> str:

    if not (os.getenv("OPENROUTER_API_KEY") or "").strip():
        return "OPENROUTER_API_KEY is not set in .env"
    try:
        from openai import OpenAI
        c = OpenAI(api_key=os.getenv("OPENROUTER_API_KEY"), base_url="https://openrouter.ai/api/v1")
        r = c.embeddings.create(model=EMBEDDING_MODEL, input="test")
        _ = [float(x) for x in r.data[0].embedding]
        return ""
    except Exception as e:
        return str(e)
