"""Structured outputs. Every agent result is validated against one of these before it is stored."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Confidence = Literal["none", "low", "medium", "high"]


class Evidence(BaseModel):
    claim: str
    source: str = Field(description="tool name, metric or URL the claim rests on")


class GrowthPlan(BaseModel):
    bottleneck: str
    next_action: str
    daily_priorities: list[str]
    weekly_priorities: list[str]
    experiment_to_run: str | None = None
    expected_learning: str
    evidence: list[Evidence]
    confidence: Confidence
    limitations: list[str] = []


class AudienceInsight(BaseModel):
    segment: str
    need: str
    angle: str
    hook_ideas: list[str]
    evidence_level: Literal["observed", "inferred", "hypothesis"]
    evidence: list[Evidence] = []


class AudienceReport(BaseModel):
    insights: list[AudienceInsight]
    limitations: list[str] = []


class ResearchReport(BaseModel):
    topic: str
    summary: str
    key_claims: list[Evidence]
    proposed_angles: list[str]
    live_research_performed: bool
    disclosure: str


class Scene(BaseModel):
    t_start: float
    t_end: float
    visual: str
    voiceover: str
    on_screen_text: str = ""


class ReelPackage(BaseModel):
    title: str
    audience_segment: str
    audience_problem: str
    format: Literal["talking_head", "motion_graphics", "mixed"]
    hook_options: list[str] = Field(min_length=3, max_length=3)
    recommended_hook: str
    hook_reasoning: str
    script: str
    timeline: list[Scene]
    on_screen_text: list[str]
    visual_direction: str
    sound_direction: str = Field(description="direction only; licensing not assumed")
    caption: str
    keywords: list[str]
    hashtags: list[str] = Field(max_length=5)
    cta: str
    hypothesis: str
    success_metrics: list[str]
    follow_up_experiment: str
    duration_seconds: int


class ReelOptions(BaseModel):
    options: list[ReelPackage] = Field(min_length=1, max_length=3)


class AnalyticsReport(BaseModel):
    key_findings: list[Evidence]
    outliers: list[str]
    weak_patterns: list[str]
    recommended_action: str
    limitations: list[str]
    sample_size: int


class ScheduleProposal(BaseModel):
    slots: list[dict]
    reasons: list[str]
    issues: list[str]
    required_user_actions: list[str]


class CommunityReport(BaseModel):
    available: bool
    common_questions: list[str]
    draft_responses: list[str]
    content_ideas: list[str]
    note: str
    approval_required: bool = True


class ExperimentReport(BaseModel):
    proposal: dict | None
    analyses: list[dict]
    recommendations: list[str]
    caveats: list[str]


class OrchestratorReport(BaseModel):
    workflow: str
    steps: list[dict]
    summary: str
    failures: list[str]
