"""
Weight tuning eval for the ranking system.

Usage:
    python3 -m retrieval.weight_eval             # run with current weights
    python3 -m retrieval.weight_eval --grid      # grid search over weight combos

Each EvalCase defines:
  - query: the user's search string
  - team_context: optional per-case context dict (defaults to drone team)
  - want_in_top5: company names that SHOULD appear (case-insensitive substring match)
  - want_not_in_top5: company names that should NOT appear
  - note: human explanation of why

Add new cases whenever you spot a bad result in production — this becomes
your regression suite for future weight tuning.
"""
from __future__ import annotations

import argparse
import itertools
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import patch

from retrieval.ranking import rank_candidates


# ---------------------------------------------------------------------------
# Contexts — one per team type so queries don't bleed into each other
# ---------------------------------------------------------------------------

def _ctx_drone() -> dict:
    return {
        "team_name": "UW Aerial Robotics",
        "repo": "",
        "active_blockers": [
            {"summary": "need hardware partners for arctic drone build", "tags": ["hardware", "drones", "arctic"], "severity": "high"}
        ],
        "subsystems": ["drone frame", "flight controller", "payload"],
        "inferred_support_needs": ["hardware_discounts", "sponsorship", "technical_guidance"],
        "context_summary": "hardware drone team looking for hardware sponsors",
    }


def _ctx_software() -> dict:
    return {
        "team_name": "UW Software Design Team",
        "repo": "",
        "active_blockers": [
            {"summary": "need dev tools and cloud credits", "tags": ["cloud", "software", "simulation"], "severity": "medium"}
        ],
        "subsystems": ["simulation", "data pipeline", "dashboard"],
        "inferred_support_needs": ["cloud_credits", "software_licenses", "technical_guidance"],
        "context_summary": "software team needing cloud and dev tool sponsorships",
    }


def _ctx_aerospace() -> dict:
    return {
        "team_name": "UW Rocketry",
        "repo": "",
        "active_blockers": [
            {"summary": "need aerospace industry sponsors", "tags": ["aerospace", "propulsion", "rocket"], "severity": "high"}
        ],
        "subsystems": ["propulsion", "avionics", "recovery"],
        "inferred_support_needs": ["sponsorship", "hardware_discounts", "mentorship"],
        "context_summary": "rocketry team looking for aerospace company sponsors",
    }


def _ctx_electronics() -> dict:
    return {
        "team_name": "UW Robotics — Electronics",
        "repo": "",
        "active_blockers": [
            {"summary": "need PCB design tools and manufacturing support", "tags": ["pcb", "electronics", "hardware"], "severity": "high"}
        ],
        "subsystems": ["PCB design", "motor drivers", "power management"],
        "inferred_support_needs": ["software_licenses", "hardware_discounts", "technical_guidance"],
        "context_summary": "electronics subteam needing PCB tooling and manufacturing support",
    }


# ---------------------------------------------------------------------------
# Ground-truth eval cases — add more whenever you see a bad production result
# ---------------------------------------------------------------------------

@dataclass
class EvalCase:
    query: str
    team_context: dict[str, Any] | None = None  # None = drone ctx
    want_in_top5: list[str] = field(default_factory=list)
    want_not_in_top5: list[str] = field(default_factory=list)
    note: str = ""


CASES: list[EvalCase] = [
    EvalCase(
        query="we want companies that are professional in building drones that are durable and will survive arctic weather",
        team_context=_ctx_drone(),
        want_in_top5=["skydio", "boeing", "brp", "auterion"],
        want_not_in_top5=["github", "slack", "notion", "altium", "solidworks"],
        note="hardware drone query — devtools should not surface",
    ),
    EvalCase(
        query="we need PCB design software sponsorship",
        team_context=_ctx_electronics(),
        want_in_top5=["altium"],
        want_not_in_top5=["github", "boeing", "brp"],
        note="EDA tools query — Altium should lead",
    ),
    EvalCase(
        query="looking for aerospace companies that sponsor university teams",
        team_context=_ctx_aerospace(),
        want_in_top5=["boeing", "spacex", "rocket lab"],
        want_not_in_top5=["github", "notion"],
        note="aerospace sponsorship",
    ),
    EvalCase(
        query="we need cloud computing credits for simulation",
        team_context=_ctx_software(),
        want_in_top5=["aws", "google cloud", "microsoft azure"],
        want_not_in_top5=["boeing", "brp"],
        note="cloud credits — infra companies should lead",
    ),
    EvalCase(
        query="looking for sensor manufacturers for lidar and imu",
        team_context=_ctx_drone(),
        want_in_top5=["bosch", "velodyne", "hesai", "luminar"],
        want_not_in_top5=["github", "altium"],
        note="sensor hardware query",
    ),
]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _names_in_top5(candidates: list) -> list[str]:
    return [(c.name or "").lower() for c in candidates[:5]]


def _score_case(candidates: list, case: EvalCase) -> dict:
    top5 = _names_in_top5(candidates)

    hits = sum(
        1 for want in case.want_in_top5
        if any(want.lower() in name for name in top5)
    )
    bad_hits = sum(
        1 for bad in case.want_not_in_top5
        if any(bad.lower() in name for name in top5)
    )

    want_total = max(1, len(case.want_in_top5))
    precision = hits / want_total
    penalty = bad_hits / max(1, len(case.want_not_in_top5))
    score = max(0.0, precision - 0.5 * penalty)

    return {
        "score": round(score, 3),
        "hits": hits,
        "want_total": want_total,
        "bad_hits": bad_hits,
        "top5_names": top5,
    }


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

@contextmanager
def _no_llm():
    """Patch llm_rerank to a passthrough so grid search tests math only."""
    def _passthrough(candidates, query, tc, k):
        return candidates[:k]
    with patch("retrieval.ranking.llm_rerank", side_effect=_passthrough):
        yield


def run_eval(weights: dict | None = None, verbose: bool = True, skip_llm: bool = False) -> float:
    """Run all cases and return average score (0–1)."""
    import retrieval.config as cfg
    if weights:
        original = dict(cfg.RANKING_WEIGHTS)
        cfg.RANKING_WEIGHTS.update(weights)

    try:
        total = 0.0
        if verbose:
            print(f"\nWeights: {dict(cfg.RANKING_WEIGHTS)}")
            if skip_llm:
                print("(LLM reranker bypassed — math scores only)")
            print("-" * 70)

        ctx_mgr = _no_llm() if skip_llm else _noop_ctx()
        with ctx_mgr:
            for i, case in enumerate(CASES, 1):
                ctx = case.team_context or _ctx_drone()
                out = rank_candidates(ctx, case.query, k=10)
                res = _score_case(out.candidates, case)
                total += res["score"]

                if verbose:
                    status = "✓" if res["score"] >= 0.5 else "✗"
                    print(f"{status} [{i}] {case.note}")
                    print(f"      want={case.want_in_top5}")
                    print(f"      got ={res['top5_names']}")
                    print(f"      hits={res['hits']}/{res['want_total']}  bad_hits={res['bad_hits']}  score={res['score']}")

        avg = round(total / max(1, len(CASES)), 3)
        if verbose:
            print("-" * 70)
            print(f"avg_score={avg}  ({'✓ good' if avg >= 0.6 else '✗ needs tuning'})")
        return avg
    finally:
        if weights:
            cfg.RANKING_WEIGHTS.clear()
            cfg.RANKING_WEIGHTS.update(original)


@contextmanager
def _noop_ctx():
    yield


# ---------------------------------------------------------------------------
# Grid search — bypasses LLM entirely (tests math weights only)
# ---------------------------------------------------------------------------

def grid_search(skip_llm: bool = False):
    """Fast weight search: math scan over all combos, then LLM-validates top 3.

    Total cost: N math runs (fast) + 3 LLM runs (slow) = best of both worlds.
    Pass --no-llm to skip the LLM validation step entirely.
    """
    sem_opts = [0.50, 0.55, 0.60, 0.65, 0.70]
    tag_opts = [0.05, 0.10, 0.15]
    fit_opts = [0.10, 0.15, 0.20]
    aff_opts = [0.02, 0.05, 0.10]

    combos = [
        (s, t, f, a)
        for s, t, f, a in itertools.product(sem_opts, tag_opts, fit_opts, aff_opts)
        if round(s + t + f + a, 10) == 1.0
    ]

    # --- phase 1: fast math-only scan ---
    print(f"Phase 1: math scan over {len(combos)} combos (LLM bypassed)...")
    math_results = []
    with _no_llm():
        for s, t, f, a in combos:
            w = {"semantic": s, "tag_overlap": t, "support_fit": f, "waterloo_affinity": a}
            score = run_eval(weights=w, verbose=False, skip_llm=False)
            math_results.append((score, w))
    math_results.sort(key=lambda x: -x[0])

    print(f"Top candidates (math only):")
    for sc, w in math_results[:5]:
        print(f"  {sc:.3f}  sem={w['semantic']}  tag={w['tag_overlap']}  fit={w['support_fit']}  aff={w['waterloo_affinity']}")

    if skip_llm:
        best_score, best_w = math_results[0]
        print(f"\nBest (math only): score={best_score}  weights={best_w}")
        print(f"RANKING_WEIGHTS = {best_w}")
        return

    # --- phase 2: LLM-validate top 3 only ---
    top3 = [w for _, w in math_results[:3]]
    # dedupe in case of ties at the same combo
    seen, unique = set(), []
    for w in top3:
        key = tuple(w.values())
        if key not in seen:
            seen.add(key)
            unique.append(w)

    print(f"\nPhase 2: LLM-validating top {len(unique)} combos end-to-end...")
    llm_results = []
    for w in unique:
        score = run_eval(weights=w, verbose=False, skip_llm=False)
        llm_results.append((score, w))
        print(f"  {score:.3f}  sem={w['semantic']}  tag={w['tag_overlap']}  fit={w['support_fit']}  aff={w['waterloo_affinity']}")
    llm_results.sort(key=lambda x: -x[0])

    best_score, best_w = llm_results[0]
    print(f"\nBest (end-to-end): score={best_score}")
    print(f"Apply in retrieval/config.py:")
    print(f"  RANKING_WEIGHTS = {best_w}")




# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Eval and tune ranking weights")
    parser.add_argument("--grid", action="store_true", help="Grid search over weight combos (with LLM by default)")
    parser.add_argument("--no-llm", action="store_true", dest="no_llm", help="Bypass LLM reranker (fast, math only)")
    args = parser.parse_args()

    if args.grid:
        grid_search(skip_llm=args.no_llm)
    else:
        run_eval(verbose=True, skip_llm=args.no_llm)

