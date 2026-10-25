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


# ---------------- Reel Planner (Ideas → Reel Planner) ----------------

Potential = Literal["high", "medium", "low"]
Platform = Literal["instagram_reels", "youtube_shorts", "tiktok"]


class TrendSource(BaseModel):
    title: str = Field(description="page or post title, as found")
    url: str = Field(description="the URL the claim came from; never invented")


class TrendTopic(BaseModel):
    title: str = Field(max_length=140, description="the topic, phrased as a reel subject")
    why_trending: str = Field(description="what is driving attention to it right now")
    angle: str = Field(description="the specific angle for THIS creator's audience")
    engagement_potential: Potential
    potential_reason: str = Field(description="one line: why that rating")
    sources: list[TrendSource] = Field(
        default=[], description="empty when no live search ran; never fabricate URLs"
    )


class TrendReport(BaseModel):
    niche: str
    platform: Platform
    topics: list[TrendTopic] = Field(min_length=4, max_length=12)
    live_research_performed: bool = Field(
        description="true only when a real search provider returned results"
    )
    disclosure: str = Field(description="shown verbatim in the UI")


class Hook(BaseModel):
    text: str = Field(description="the spoken first 1-3 seconds, under 14 words")
    hook_type: Literal[
        "curiosity", "contrarian", "pain_point", "story", "stat", "negative_command", "question"
    ]
    why_it_works: str


class ScriptSection(BaseModel):
    section: Literal["hook", "setup", "value", "payoff", "cta"]
    t_start: float
    t_end: float
    spoken: str = Field(description="spoken word, short lines, no filler")
    on_screen_text: str = Field(description="<= 7 words, what the viewer reads")


class Shot(BaseModel):
    order: int
    shot_type: str = Field(description="e.g. talking head, over-the-shoulder, screen recording, insert")
    framing: str = Field(description="e.g. tight crop chest-up, eye level")
    location: str = Field(description="location / background")
    action: str = Field(description="what happens in frame")
    delivery_tone: str = Field(description="how to say it: pace, energy, pauses")
    b_roll: list[str] = Field(default=[], description="cutaway ideas for this shot")
    seconds: float


class ReelPlanOut(BaseModel):
    """One complete, shootable reel package."""

    topic: str
    platform: Platform
    audience: str = Field(description="who this reel is for, in the creator's own words")
    one_idea: str = Field(description="the single idea this reel delivers; one sentence")
    hooks: list[Hook] = Field(min_length=3, max_length=3)
    script: list[ScriptSection] = Field(min_length=4)
    shots: list[Shot] = Field(min_length=3)
    total_duration_seconds: int = Field(ge=15, le=45)
    caption: str = Field(description="with line breaks; first line must stand alone")
    hashtags: list[str] = Field(min_length=5, max_length=8)
    pinned_comment: str
    cta_primary: str = Field(description="one action only")
    cta_alternative: str
    audio_direction: str = Field(description="direction only; licensing is the creator's call")
    best_posting_time: str = Field(description="a window in IST plus the reason")
    ab_test_idea: str


class HooksOnly(BaseModel):
    hooks: list[Hook] = Field(min_length=3, max_length=3)


class ScriptOnly(BaseModel):
    script: list[ScriptSection] = Field(min_length=4)


class ShotsOnly(BaseModel):
    shots: list[Shot] = Field(min_length=3)


class CaptionOnly(BaseModel):
    caption: str
    hashtags: list[str] = Field(min_length=5, max_length=8)
    pinned_comment: str


class CtaOnly(BaseModel):
    cta_primary: str
    cta_alternative: str
