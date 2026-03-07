from retrieval.mock_data import get_mock_team_context
from retrieval.ranking import rank_candidates

#quick logic test
#pytest -q test_ranking.py

def test_rank_candidates_shape_golden_query():
    ctx = get_mock_team_context()
    out = rank_candidates(ctx, "Who can help with our ground station mapping subsystem?", k=5)

    assert out.query_summary
    assert isinstance(out.candidates, list)
    assert len(out.candidates) == 5

    first = out.candidates[0]
    assert first.entity_id
    assert first.name
    assert 0.0 <= first.overall_score <= 1.0
    assert first.score_breakdown is not None
    assert isinstance(first.matched_reasons, list)
    assert isinstance(first.evidence_snippets, list)

    sb = first.score_breakdown
    assert hasattr(sb, "semantic_score")
    assert hasattr(sb, "tag_overlap_score")
    assert hasattr(sb, "support_fit_score")
    assert hasattr(sb, "waterloo_affinity_score")


def test_rank_candidates_filter_entity_type():
    ctx = get_mock_team_context()
    out = rank_candidates(
        ctx,
        "need geospatial support",
        k=10,
        filters={"entity_type": "professor"},
    )

    for c in out.candidates:
        assert c.entity_type == "professor"


def test_rank_candidates_empty_query_no_crash():
    ctx = get_mock_team_context()
    out = rank_candidates(ctx, "", k=3)

    assert len(out.candidates) <= 3
    assert out.query_summary
    assert out.retrieval_metadata["mode"] in {"phase0_stub", "phase1_semantic_plus_rules"}

def test_query_shift_changes_some_results():
    ctx = get_mock_team_context()
    a = rank_candidates(ctx, "ground station mapping telemetry", k=5)
    b = rank_candidates(ctx, "pcb manufacturing sponsorship", k=5)

    a_ids = {x.entity_id for x in a.candidates}
    b_ids = {x.entity_id for x in b.candidates}

    assert len(a_ids.intersection(b_ids)) < 5
