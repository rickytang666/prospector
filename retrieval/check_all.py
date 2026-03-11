from __future__ import annotations

from retrieval.mock_data import get_mock_team_context, get_mock_entities
from retrieval.models import Entity, TeamContext, Blocker, WaterlooAffinityEvidence
from retrieval.ranking import rank_candidates, reindex_entities
from retrieval.scoring import to_set, jacc, support_fit, waterloo_affinity, compose_scores, clamp01
from retrieval.api import rank_candidates_dict, rank_from_payload, retrieve_context_pack_dict, find_sponsors_dict


def _ctx(needs=None):
    if needs is None:
        needs = []
    return TeamContext(
        team_name="UW Orbital",
        repo="x/y",
        active_blockers=[Blocker(summary="map stuff", tags=["mapping", "telemetry"], severity="high")],
        subsystems=["ground station"],
        inferred_support_needs=needs,
        context_summary="ctx",
    )


def _ent(support=None, ev=None):
    if support is None:
        support = []
    if ev is None:
        ev = []
    return Entity(
        entity_id="e1",
        name="n1",
        entity_type="provider",
        summary="s",
        tags=["mapping", "rf"],
        support_types=support,
        waterloo_affinity_evidence=ev,
    )


def check_rank_shape():
    ctx = get_mock_team_context()
    out = rank_candidates(ctx, "Who can help with our ground station mapping subsystem?", k=5)
    assert out.query_summary
    assert isinstance(out.candidates, list)
    assert len(out.candidates) == 5
    c0 = out.candidates[0]
    assert c0.entity_id
    assert c0.name
    assert 0.0 <= c0.overall_score <= 1.0
    assert hasattr(c0.score_breakdown, "semantic_score")
    assert hasattr(c0.score_breakdown, "tag_overlap_score")
    assert hasattr(c0.score_breakdown, "support_fit_score")
    assert hasattr(c0.score_breakdown, "waterloo_affinity_score")


def check_filter():
    ctx = get_mock_team_context()
    out = rank_candidates(ctx, "need geospatial support", k=10, filters={"entity_type": "professor"})
    for c in out.candidates:
        assert c.entity_type == "professor"
    out2 = rank_candidates(ctx, "support", k=10, filters={"support_types_any": ["software_licenses"]})
    for c in out2.candidates:
        assert "software_licenses" in [x.lower() for x in c.support_types]


def check_empty():
    ctx = get_mock_team_context()
    out = rank_candidates(ctx, "", k=3)
    assert len(out.candidates) <= 3
    assert out.query_summary
    assert out.retrieval_metadata["mode"] == "phase1_semantic_plus_rules"
    assert out.retrieval_metadata["candidate_source"] in {"supabase", "fallback_local", "fallback_local_db_error", "fallback_local_db_empty"}
    assert "db_error" in out.retrieval_metadata
    assert out.retrieval_metadata["db_status"] in {"db_ok", "db_empty", "db_error"}
    assert out.retrieval_metadata["query_used"]
    assert "db_raw_row_count" in out.retrieval_metadata
    assert "db_kept_row_count" in out.retrieval_metadata
    assert "db_dropped_row_count" in out.retrieval_metadata
    assert out.retrieval_metadata["confidence"] in {"low", "medium", "high"}
    assert isinstance(out.retrieval_metadata["used_fallback_local"], bool)
    if out.retrieval_metadata["candidate_source"] == "supabase":
        assert out.retrieval_metadata["used_fallback_local"] is False
    else:
        assert out.retrieval_metadata["used_fallback_local"] is True
    assert "requested_k" in out.retrieval_metadata
    assert "returned_k" in out.retrieval_metadata
    assert "over_retrieve_k" in out.retrieval_metadata


def check_query_shift():
    ctx = get_mock_team_context()
    a = rank_candidates(ctx, "ground station mapping telemetry", k=5)
    b = rank_candidates(ctx, "pcb manufacturing sponsorship", k=5)
    assert a.candidates[0].entity_id != b.candidates[0].entity_id
    a2 = rank_candidates(ctx, "ground station mapping telemetry", k=5)
    assert [x.entity_id for x in a.candidates] == [x.entity_id for x in a2.candidates]


def check_reindex():
    ents = get_mock_entities()
    n = reindex_entities(ents)
    assert n == len(ents)

def check_dict_team_context():
    ctx = {
        "team_name": "UW Orbital",
        "repo": "x/y",
        "active_blockers": [{"summary": "map drift", "tags": ["mapping", "telemetry"], "severity": "high"}],
        "subsystems": ["ground station"],
        "inferred_support_needs": ["software_credits"],
        "context_summary": "needs mapping support",
    }
    out = rank_candidates(ctx, "mapping", k=4)
    assert out.retrieval_metadata["mode"] == "phase1_semantic_plus_rules"
    assert isinstance(out.retrieval_metadata["normalization_warnings"], list)
    assert len(out.candidates) >= 1

def check_api_dict_output():
    ctx = get_mock_team_context()
    out = rank_candidates_dict(ctx, "mapping telemetry support", k=4)
    assert isinstance(out, dict)
    assert isinstance(out.get("query_summary"), str)
    assert isinstance(out.get("candidates"), list)
    assert isinstance(out.get("retrieval_metadata"), dict)
    if out["candidates"]:
        c0 = out["candidates"][0]
        assert "score_breakdown" in c0
        assert "matched_reasons" in c0
        assert "evidence_snippets" in c0

def check_payload_api():
    p = {
        "query": "ground station mapping help",
        "team_context": {
            "team_name": "UW Orbital",
            "repo": "x/y",
            "active_blockers": [{"summary": "map drift", "tags": ["mapping", "telemetry"], "severity": "high"}],
            "subsystems": ["ground station"],
            "inferred_support_needs": ["software_credits"],
            "context_summary": "needs mapping support",
        },
        "k": "4",
        "filters": {"entity_type": "provider"},
    }
    out = rank_from_payload(p)
    assert isinstance(out, dict)
    assert isinstance(out.get("candidates"), list)
    assert isinstance(out.get("retrieval_metadata"), dict)

def check_context_pack():
    ctx = get_mock_team_context()
    out = retrieve_context_pack_dict(ctx, "ground station mapping help", k_entities=4, k_chunks=3)
    assert isinstance(out, dict)
    assert isinstance(out.get("entity_matches"), list)
    assert isinstance(out.get("internal_chunks"), list)
    assert isinstance(out.get("citations"), list)
    assert isinstance(out.get("retrieval_meta"), dict)

def check_sponsor_wrapper():
    ctx = get_mock_team_context()
    s = find_sponsors_dict(ctx, "sponsor pcb manufacturing", message="we can offer demo visibility", k=5)
    assert isinstance(s, dict)
    assert s.get("retrieval_metadata", {}).get("profile") == "sponsors"
    for c in s.get("candidates", []):
        assert (c.get("entity_type") or "").lower() == "company"


def check_scoring():
    assert to_set(["  Mapping ", "mapping", "RF", "", "  "]) == {"mapping", "rf"}
    assert jacc({"a", "b"}, {"b", "c"}) == 1 / 3
    assert jacc(set(), {"x"}) == 0.0
    e = _ent(support=["software_credits", "mentorship"])
    c = _ctx(needs=["software_credits", "cloud_credits"])
    assert support_fit(e, c) == 0.5
    assert waterloo_affinity(_ent()) == 0.0
    assert waterloo_affinity(_ent(ev=[WaterlooAffinityEvidence(type="alumni_link", text="x", source_url="")])) == 0.3
    assert waterloo_affinity(_ent(ev=[WaterlooAffinityEvidence(type="official_page", text="x", source_url="")])) == 0.6
    assert waterloo_affinity(_ent(ev=[
        WaterlooAffinityEvidence(type="alumni_link", text="x", source_url=""),
        WaterlooAffinityEvidence(type="team_sponsor", text="y", source_url=""),
    ])) == 0.60  # 0.55 team_sponsor + 0.05 multi-tier bonus
    z = compose_scores(0.8, 0.5, 0.25, 1.0)
    assert 0.0 <= z <= 1.0
    assert clamp01(-1.0) == 0.0
    assert clamp01(2.0) == 1.0
    assert clamp01(0.42) == 0.42


def check_db_norm_helpers():
    from retrieval.db_retrieval import _to_str_list, _norm_affinity, _row_to_entity
    assert _to_str_list('["a","b"]') == ["a", "b"]
    a = _norm_affinity('[{"type":"official_page","text":"x","source_url":"u"}]')
    assert len(a) == 1
    r = {
        "id": "z1",
        "name": "n",
        "type": "provider",
        "entity_summary": "s",
        "entity_tags": '["mapping","rf"]',
        "support": "software_credits, mentorship",
        "affinity_evidence": '[{"type":"alumni_link","text":"t","source_url":"u"}]',
        "score": 0.77,
    }
    x = _row_to_entity(r)
    assert x is not None
    e, sem = x
    assert e.entity_id == "z1"
    assert e.name == "n"
    assert "mapping" in e.tags
    assert sem == 0.77


def run_all():
    checks = [
        ("rank_shape", check_rank_shape),
        ("filter", check_filter),
        ("empty", check_empty),
        ("query_shift", check_query_shift),
        ("reindex", check_reindex),
        ("dict_ctx", check_dict_team_context),
        ("api_dict", check_api_dict_output),
        ("api_payload", check_payload_api),
        ("context_pack", check_context_pack),
        ("sponsor", check_sponsor_wrapper),
        ("scoring", check_scoring),
        ("db_norm", check_db_norm_helpers),
    ]
    bad = 0
    for name, fn in checks:
        try:
            fn()
            print("ok   ", name)
        except Exception as e:
            bad += 1
            print("fail ", name, "-", str(e))
    if bad:
        raise SystemExit(1)
    print("all checks passed")


if __name__ == "__main__":
    run_all()
