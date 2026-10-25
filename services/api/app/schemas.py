"""Request/response contracts for the HTTP API."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import CONTENT_STATUSES

T = TypeVar("T")
Status = Literal["idea", "script", "recording", "editing", "ready", "published", "archived"]
Format = Literal["talking_head", "motion_graphics", "screen_recording", "carousel", "mixed", "image"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    @field_validator("*", mode="before")
    @classmethod
    def _utc(cls, v: Any) -> Any:
        # SQLite drops tzinfo; everything is stored as UTC, so re-attach it on the way out.
        if isinstance(v, datetime) and v.tzinfo is None:
            return v.replace(tzinfo=UTC)
        return v


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


AudienceTag = Literal["beginners", "developers", "ai_enthusiasts", "students", "career"]


class ContentBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    pillar: str | None = Field(default=None, max_length=80)
    audience_segment: str | None = Field(default=None, max_length=80)
    audience: AudienceTag | None = None
    audience_problem: str | None = None
    format: Format | None = None
    hook_options: list[str] = []
    recommended_hook: str | None = None
    script: str | None = None
    storyboard: list[dict[str, Any]] = []
    on_screen_text: list[str] = []
    visual_direction: str | None = None
    duration_seconds: int | None = Field(default=None, ge=3, le=900)
    caption: str | None = Field(default=None, max_length=2200)
    keywords: list[str] = []
    hashtags: list[str] = Field(default=[], max_length=30)
    cta: str | None = None
    effort: Literal["low", "medium", "high"] | None = None
    evidence: list[str] = []
    hypothesis: str | None = None
    status: Status = "idea"
    planned_at: datetime | None = None
    lessons: str | None = None
    notes: str | None = Field(default=None, max_length=10000)
    package: dict[str, Any] = {}

    @field_validator("hashtags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return [t if t.startswith("#") else f"#{t}" for t in (x.strip() for x in v) if t]


class ContentCreate(ContentBase):
    pass


class ContentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    pillar: str | None = None
    audience_segment: str | None = None
    audience: AudienceTag | None = None
    audience_problem: str | None = None
    format: Format | None = None
    hook_options: list[str] | None = None
    recommended_hook: str | None = None
    script: str | None = None
    storyboard: list[dict[str, Any]] | None = None
    on_screen_text: list[str] | None = None
    visual_direction: str | None = None
    duration_seconds: int | None = Field(default=None, ge=3, le=900)
    caption: str | None = Field(default=None, max_length=2200)
    keywords: list[str] | None = None
    hashtags: list[str] | None = None
    cta: str | None = None
    effort: Literal["low", "medium", "high"] | None = None
    evidence: list[str] | None = None
    hypothesis: str | None = None
    status: Status | None = None
    planned_at: datetime | None = None
    lessons: str | None = None
    notes: str | None = Field(default=None, max_length=10000)
    performance: dict[str, Any] | None = None
    package: dict[str, Any] | None = None


class ContentOut(ContentBase, ORM):
    id: int
    created_at: datetime
    updated_at: datetime
    published_media_id: str | None
    performance: dict[str, Any]
    is_demo: bool


class CalendarCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    idea_id: int | None = None
    format: Format | None = None
    scheduled_at: datetime
    caption: str | None = Field(default=None, max_length=2200)
    asset_ref: str | None = Field(default=None, max_length=1000)
    production_status: str = "planned"


class CalendarUpdate(BaseModel):
    title: str | None = None
    format: Format | None = None
    scheduled_at: datetime | None = None
    caption: str | None = Field(default=None, max_length=2200)
    asset_ref: str | None = Field(default=None, max_length=1000)
    production_status: str | None = None
    approval_status: Literal["pending", "approved", "rejected"] | None = None


class CalendarOut(ORM):
    id: int
    idea_id: int | None
    title: str
    format: str | None
    scheduled_at: datetime
    timezone: str
    caption: str | None
    asset_ref: str | None
    production_status: str
    approval_status: str
    publishing_status: str
    published_at: datetime | None
    published_media_id: str | None
    is_demo: bool


class PersonaIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    evidence_level: Literal["verified", "inferred", "hypothesis"] = "hypothesis"
    interests: list[str] = []
    problems: list[str] = []
    angles: list[str] = []
    notes: str | None = None


class PersonaOut(PersonaIn, ORM):
    id: int
    is_demo: bool


class ExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    hypothesis: str = Field(min_length=1)
    variable: Literal[
        "hook_style", "duration", "format", "storytelling", "cta", "pillar", "publish_window", "caption_style"
    ]
    control: str
    variant: str
    primary_metric: Literal["views", "reach", "saves", "shares", "follows", "multiple"] = "views"
    observation_days: int = Field(default=7, ge=1, le=60)
    min_samples_per_arm: int = Field(default=3, ge=2, le=50)


class ExperimentUpdate(BaseModel):
    status: Literal["planned", "running", "complete"] | None = None
    decision: str | None = None
    next_test: str | None = None


class ObservationIn(BaseModel):
    arm: Literal["control", "variant"]
    value: float = Field(ge=0)
    media_ref: str | None = None


class ExperimentOut(ORM):
    id: int
    name: str
    hypothesis: str
    variable: str
    control: str
    variant: str
    primary_metric: str
    observation_days: int
    min_samples_per_arm: int
    status: str
    decision: str | None
    next_test: str | None
    is_demo: bool
    created_at: datetime
    result: dict[str, Any] = {}
    observations: list[dict[str, Any]] = []


class TargetIn(BaseModel):
    target: int = Field(ge=1, le=100_000_000)
    days: int = Field(ge=1, le=365)
    start_followers: int = Field(ge=0)
    start_date: date


class ManualSnapshotIn(BaseModel):
    snapshot_date: date
    followers: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    views: int | None = Field(default=None, ge=0)
    follows: int | None = Field(default=None, ge=0)
    unfollows: int | None = Field(default=None, ge=0)


class AgentRunIn(BaseModel):
    input: dict[str, Any] = {}
    wait: bool = False


class AgentRunOut(ORM):
    id: int
    agent_id: str
    parent_run_id: int | None
    mode: str
    status: str
    input_summary: str | None
    input: dict[str, Any]
    output_summary: str | None
    output: dict[str, Any]
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    est_cost_usd: float | None
    created_at: datetime
    is_demo: bool
    tools_called: list[str] = []


class TaskOut(ORM):
    id: int
    task_date: date
    title: str
    reason: str | None
    impact: int
    effort_minutes: int
    priority: float
    done: bool
    is_demo: bool


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    impact: int = Field(default=2, ge=1, le=3)
    effort_minutes: int = Field(default=30, ge=5, le=480)


class ApprovalOut(ORM):
    id: int
    action: str
    target_type: str
    target_id: int
    summary: str
    payload: dict[str, Any]
    status: str
    requested_by: str
    created_at: datetime
    decided_at: datetime | None


VALID_STATUSES = CONTENT_STATUSES
