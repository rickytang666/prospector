from __future__ import annotations

from dataclasses import asdict
from typing import Any

from retrieval.ranking import rank_candidates
from retrieval.models import TeamContext
from retrieval.context_pack import retrieve_context_pack


def rank_candidates_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = 5,
    filters: dict[str, Any] | None = None,
    profile: str = "providers",
):
    out = rank_candidates(team_context=team_context, query=query, k=k, filters=filters, profile=profile)
    return asdict(out)


def rank_from_payload(payload: dict[str, Any]):
    q = str(payload.get("query", ""))
    tc = payload.get("team_context", {})
    k = payload.get("k", 5)
    if not isinstance(k, int):
        try:
            k = int(k)
        except Exception:
            k = 5
    f = payload.get("filters")
    profile = str(payload.get("profile", "providers"))
    if f is None:
        f = {}
    if not isinstance(f, dict):
        f = {}
    return rank_candidates_dict(team_context=tc, query=q, k=k, filters=f, profile=profile)


def find_providers_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k: int = 5,
    filters: dict[str, Any] | None = None,
):
    return rank_candidates_dict(
        team_context=team_context,
        query=query,
        k=k,
        filters=filters,
        profile="providers",
    )


def find_sponsors_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    message: str | None = None,
    k: int = 5,
    filters: dict[str, Any] | None = None,
):
    q = (query or "").strip()
    m = (message or "").strip()
    if m:
        q = f"{q}. Sponsor pitch: {m}"
    return rank_candidates_dict(
        team_context=team_context,
        query=q,
        k=k,
        filters=filters,
        profile="sponsors",
    )


def find_providers_from_payload(payload: dict[str, Any]):
    q = str(payload.get("query", ""))
    tc = payload.get("team_context", {})
    k = payload.get("k", 5)
    f = payload.get("filters", {})
    try:
        k = int(k)
    except Exception:
        k = 5
    if not isinstance(f, dict):
        f = {}
    return find_providers_dict(team_context=tc, query=q, k=k, filters=f)


def find_sponsors_from_payload(payload: dict[str, Any]):
    q = str(payload.get("query", ""))
    msg = payload.get("message")
    tc = payload.get("team_context", {})
    k = payload.get("k", 5)
    f = payload.get("filters", {})
    try:
        k = int(k)
    except Exception:
        k = 5
    if not isinstance(f, dict):
        f = {}
    return find_sponsors_dict(team_context=tc, query=q, message=msg, k=k, filters=f)


def retrieve_context_pack_dict(
    team_context: TeamContext | dict[str, Any],
    query: str,
    k_entities: int = 5,
    k_chunks: int = 5,
    entity_filters: dict[str, Any] | None = None,
    chunk_filters: dict[str, Any] | None = None,
):
    return retrieve_context_pack(
        team_context=team_context,
        query=query,
        k_entities=k_entities,
        k_chunks=k_chunks,
        entity_filters=entity_filters,
        chunk_filters=chunk_filters,
    )


def retrieve_context_pack_from_payload(payload: dict[str, Any]):
    q = str(payload.get("query", ""))
    tc = payload.get("team_context", {})
    ke = payload.get("k_entities", payload.get("k", 5))
    kc = payload.get("k_chunks", 5)
    ef = payload.get("entity_filters", payload.get("filters", {}))
    cf = payload.get("chunk_filters", {})
    try:
        ke = int(ke)
    except Exception:
        ke = 5
    try:
        kc = int(kc)
    except Exception:
        kc = 5
    if not isinstance(ef, dict):
        ef = {}
    if not isinstance(cf, dict):
        cf = {}
    return retrieve_context_pack_dict(
        team_context=tc,
        query=q,
        k_entities=ke,
        k_chunks=kc,
        entity_filters=ef,
        chunk_filters=cf,
    )


def rag_from_payload(payload: dict[str, Any]):
    return retrieve_context_pack_from_payload(payload)
