from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class WaterlooAffinityEvidence:
    type: str
    text: str
    source_url: str = ""

@dataclass(slots=True)
class Entity:
    entity_id: str
    name: str
    entity_type: str  # only company for now, expand to profs/lab if mvp permits
    summary: str
    tags: list[str]
    support_types: list[str]
    waterloo_affinity_evidence: list[WaterlooAffinityEvidence] = field(default_factory=list)

@dataclass(slots=True)
class Blocker:
    summary: str
    tags: list[str]
    severity: str = "medium" # low | medium | high

@dataclass(slots=True)
class TeamContext:
    team_name: str
    repo: str
    active_blockers: list[Blocker]
    subsystems: list[str]
    inferred_support_needs: list[str]
    context_summary: str

@dataclass(slots=True)
class ScoreBreakdown:
    semantic_score: float
    tag_overlap_score: float
    support_fit_score: float
    waterloo_affinity_score: float

@dataclass(slots=True)
class RankedCandidate:
    entity_id: str
    name: str
    entity_type: str
    overall_score: float  # from 0 to 1, higher is better
    score_breakdown: ScoreBreakdown
    matched_reasons: list[str]
    evidence_snippets: list[str]
    support_types: list[str]
    waterloo_affinity_evidence: list[WaterlooAffinityEvidence] = field(default_factory=list)

@dataclass(slots=True)
class RankedCandidateResponse:
    query_summary: str
    candidates: list[RankedCandidate]
    retrieval_metadata: dict[str, Any] = field(default_factory=dict)
