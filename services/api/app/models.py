"""Relational schema. Every metric-bearing row carries a `source` so demo, manual and
official API data are never mixed silently."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Data sources shown in the UI next to every metric.
SOURCE_API = "instagram_api"
SOURCE_MANUAL = "manual"
SOURCE_CALCULATED = "calculated"
SOURCE_DEMO = "demo"

# Board columns, in order. "idea" doubles as the quick-capture inbox.
CONTENT_STATUSES = ("idea", "script", "recording", "editing", "ready", "published", "archived")
CATEGORIES = ("ai", "tech_concepts", "career", "skills", "relatable_learning")
FORMATS = ("talking_head", "motion_graphics", "screen_recording", "carousel", "mixed")
AUDIENCE_SEGMENTS = ("beginners", "developers", "ai_enthusiasts", "students", "career")


def iso_utc(v):
    """ISO-8601 with an explicit offset. SQLite returns naive datetimes; they are stored as UTC."""
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=UTC)).isoformat()
    return v.isoformat() if hasattr(v, "isoformat") else v


def utcnow() -> datetime:
    return datetime.now(UTC)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AppSetting(Base, TimestampMixin):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON)


class InstagramAccount(Base, TimestampMixin):
    __tablename__ = "instagram_accounts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ig_user_id: Mapped[str] = mapped_column(String(64), unique=True)
    username: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str | None] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    connected: Mapped[bool] = mapped_column(Boolean, default=True)
    granted_scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    token: Mapped[InstagramToken | None] = relationship(
        back_populates="account", cascade="all, delete-orphan", uselist=False
    )


class InstagramToken(Base, TimestampMixin):
    """Encrypted at rest with a Fernet key held outside the database."""

    __tablename__ = "instagram_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("instagram_accounts.id", ondelete="CASCADE"), unique=True
    )
    ciphertext: Mapped[str] = mapped_column(Text)
    key_version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    account: Mapped[InstagramAccount] = relationship(back_populates="token")


class OAuthState(Base):
    __tablename__ = "oauth_states"
    state: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    used: Mapped[bool] = mapped_column(Boolean, default=False)


class AccountSnapshot(Base):
    __tablename__ = "account_snapshots"
    __table_args__ = (
        UniqueConstraint("account_id", "snapshot_date", "source", name="uq_account_snapshot_day"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("instagram_accounts.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(20))
    followers: Mapped[int | None] = mapped_column(Integer)
    follows: Mapped[int | None] = mapped_column(Integer)
    unfollows: Mapped[int | None] = mapped_column(Integer)
    reach: Mapped[int | None] = mapped_column(Integer)
    views: Mapped[int | None] = mapped_column(Integer)
    accounts_engaged: Mapped[int | None] = mapped_column(Integer)
    total_interactions: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saves: Mapped[int | None] = mapped_column(Integer)
    profile_links_taps: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Media(Base, TimestampMixin):
    __tablename__ = "media"
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("instagram_accounts.id", ondelete="CASCADE"), index=True
    )
    ig_media_id: Mapped[str] = mapped_column(String(64), unique=True)
    media_type: Mapped[str | None] = mapped_column(String(30))
    media_product_type: Mapped[str | None] = mapped_column(String(30))
    caption: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(String(500))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(20))
    content_idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id", ondelete="SET NULL"))
    pillar: Mapped[str | None] = mapped_column(String(80))  # category: ai | tech_concepts | career | ...
    hook_style: Mapped[str | None] = mapped_column(String(80))  # hook formula name, auto-classified
    hook_text: Mapped[str | None] = mapped_column(Text)  # the first line actually said/shown
    format_style: Mapped[str | None] = mapped_column(String(40))  # talking_head | motion_graphics | ...
    length_seconds: Mapped[int | None] = mapped_column(Integer)
    audience: Mapped[str | None] = mapped_column(String(30))  # AUDIENCE_SEGMENTS; inferred when empty
    snapshots: Mapped[list[MediaSnapshot]] = relationship(
        back_populates="media", cascade="all, delete-orphan"
    )


class MediaSnapshot(Base):
    __tablename__ = "media_snapshots"
    __table_args__ = (UniqueConstraint("media_id", "snapshot_date", name="uq_media_snapshot_day"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    media_id: Mapped[int] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    snapshot_date: Mapped[date] = mapped_column(Date)
    source: Mapped[str] = mapped_column(String(20))
    views: Mapped[int | None] = mapped_column(Integer)
    reach: Mapped[int | None] = mapped_column(Integer)
    likes: Mapped[int | None] = mapped_column(Integer)
    comments: Mapped[int | None] = mapped_column(Integer)
    shares: Mapped[int | None] = mapped_column(Integer)
    saved: Mapped[int | None] = mapped_column(Integer)
    total_interactions: Mapped[int | None] = mapped_column(Integer)
    avg_watch_time_ms: Mapped[int | None] = mapped_column(Integer)
    total_watch_time_ms: Mapped[int | None] = mapped_column(BigInteger)  # ig_reels_video_view_total_time
    # Feed posts/carousels only (Instagram doesn't report these for Reels). None = not reported, never 0.
    follows: Mapped[int | None] = mapped_column(Integer)
    profile_visits: Mapped[int | None] = mapped_column(Integer)
    profile_activity: Mapped[int | None] = mapped_column(Integer)
    reposts: Mapped[int | None] = mapped_column(Integer)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    media: Mapped[Media] = relationship(back_populates="snapshots")


class ContentIdea(Base, TimestampMixin):
    __tablename__ = "content_ideas"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    pillar: Mapped[str | None] = mapped_column(String(80), index=True)
    audience_segment: Mapped[str | None] = mapped_column(String(80))
    audience_problem: Mapped[str | None] = mapped_column(Text)
    audience: Mapped[str | None] = mapped_column(String(30))  # AUDIENCE_SEGMENTS tag
    format: Mapped[str | None] = mapped_column(
        String(40)
    )  # talking_head | motion_graphics | carousel | mixed
    hook_options: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_hook: Mapped[str | None] = mapped_column(Text)
    script: Mapped[str | None] = mapped_column(Text)
    storyboard: Mapped[list[dict]] = mapped_column(JSON, default=list)
    on_screen_text: Mapped[list[str]] = mapped_column(JSON, default=list)
    visual_direction: Mapped[str | None] = mapped_column(Text)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    caption: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str]] = mapped_column(JSON, default=list)
    hashtags: Mapped[list[str]] = mapped_column(JSON, default=list)
    cta: Mapped[str | None] = mapped_column(Text)
    effort: Mapped[str | None] = mapped_column(String(20))  # low | medium | high
    evidence: Mapped[list[str]] = mapped_column(JSON, default=list)
    hypothesis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="idea", index=True)
    planned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_media_id: Mapped[str | None] = mapped_column(String(64))
    performance: Mapped[dict] = mapped_column(JSON, default=dict)
    lessons: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)  # free-form scratch notes (Ideas page)
    package: Mapped[dict] = mapped_column(JSON, default=dict)  # full Reel Studio package
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    assets: Mapped[list[ContentAsset]] = relationship(back_populates="idea", cascade="all, delete-orphan")


class ContentAsset(Base, TimestampMixin):
    __tablename__ = "content_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int] = mapped_column(ForeignKey("content_ideas.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20))  # video | image | audio | other
    local_path: Mapped[str | None] = mapped_column(String(500))
    public_url: Mapped[str | None] = mapped_column(String(1000))
    idea: Mapped[ContentIdea] = relationship(back_populates="assets")


class CalendarItem(Base, TimestampMixin):
    __tablename__ = "calendar_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    idea_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_ideas.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    format: Mapped[str | None] = mapped_column(String(40))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    timezone: Mapped[str] = mapped_column(String(40), default="Asia/Kolkata")
    caption: Mapped[str | None] = mapped_column(Text)
    asset_ref: Mapped[str | None] = mapped_column(String(1000))
    production_status: Mapped[str] = mapped_column(String(20), default="planned")
    approval_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected
    publishing_status: Mapped[str] = mapped_column(String(20), default="not_started")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_media_id: Mapped[str | None] = mapped_column(String(64))
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class ApprovalRequest(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(40))  # publish_media | post_comment_reply
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int] = mapped_column(Integer)
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    requested_by: Mapped[str] = mapped_column(String(60), default="user")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PublishingJob(Base, TimestampMixin):
    __tablename__ = "publishing_jobs"
    __table_args__ = (UniqueConstraint("calendar_item_id", name="uq_publish_once_per_item"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    calendar_item_id: Mapped[int] = mapped_column(ForeignKey("calendar_items.id", ondelete="CASCADE"))
    approval_id: Mapped[int] = mapped_column(ForeignKey("approval_requests.id"))
    container_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    media_id: Mapped[str | None] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)


class AudiencePersona(Base, TimestampMixin):
    __tablename__ = "audience_personas"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    evidence_level: Mapped[str] = mapped_column(
        String(20), default="hypothesis"
    )  # verified|inferred|hypothesis
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)
    problems: Mapped[list[str]] = mapped_column(JSON, default=list)
    angles: Mapped[list[str]] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Experiment(Base, TimestampMixin):
    __tablename__ = "experiments"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    hypothesis: Mapped[str] = mapped_column(Text)
    variable: Mapped[str] = mapped_column(String(60))
    control: Mapped[str] = mapped_column(Text)
    variant: Mapped[str] = mapped_column(Text)
    primary_metric: Mapped[str] = mapped_column(String(40), default="views")
    observation_days: Mapped[int] = mapped_column(Integer, default=7)
    min_samples_per_arm: Mapped[int] = mapped_column(Integer, default=3)
    status: Mapped[str] = mapped_column(String(20), default="planned")  # planned|running|complete
    decision: Mapped[str | None] = mapped_column(Text)
    next_test: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    observations: Mapped[list[ExperimentObservation]] = relationship(
        back_populates="experiment", cascade="all, delete-orphan"
    )


class ExperimentObservation(Base, TimestampMixin):
    __tablename__ = "experiment_observations"
    id: Mapped[int] = mapped_column(primary_key=True)
    experiment_id: Mapped[int] = mapped_column(ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    arm: Mapped[str] = mapped_column(String(10))  # control | variant
    media_ref: Mapped[str | None] = mapped_column(String(200))
    value: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default=SOURCE_MANUAL)
    experiment: Mapped[Experiment] = relationship(back_populates="observations")


class AgentDefinition(Base, TimestampMixin):
    __tablename__ = "agent_definitions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    responsibility: Mapped[str] = mapped_column(Text)
    tools: Mapped[list[str]] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(40), index=True)
    parent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    input_summary: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[str | None] = mapped_column(Text)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    est_cost_usd: Mapped[float | None] = mapped_column(Float)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    tool_calls: Mapped[list[ToolCallAudit]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ToolCallAudit(Base):
    __tablename__ = "tool_call_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool: Mapped[str] = mapped_column(String(60))
    args: Mapped[dict] = mapped_column(JSON, default=dict)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str | None] = mapped_column(Text)
    is_write: Mapped[bool] = mapped_column(Boolean, default=False)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    run: Mapped[AgentRun | None] = relationship(back_populates="tool_calls")


class ExternalWriteAudit(Base):
    __tablename__ = "external_write_audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(60))
    approval_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ok: Mapped[bool] = mapped_column(Boolean)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GrowthPlan(Base, TimestampMixin):
    __tablename__ = "growth_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    period: Mapped[str] = mapped_column(String(10))  # daily | weekly
    plan_date: Mapped[date] = mapped_column(Date, index=True)
    content: Mapped[dict] = mapped_column(JSON)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class DailyTask(Base, TimestampMixin):
    __tablename__ = "daily_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text)
    impact: Mapped[int] = mapped_column(Integer, default=2)  # 1..3
    effort_minutes: Mapped[int] = mapped_column(Integer, default=30)
    priority: Mapped[float] = mapped_column(Float, default=0)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ResearchSource(Base, TimestampMixin):
    __tablename__ = "research_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(300))
    published: Mapped[str | None] = mapped_column(String(40))
    claim: Mapped[str | None] = mapped_column(Text)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"))


class LearningRecord(Base, TimestampMixin):
    __tablename__ = "learning_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30))  # pattern|hook|experiment|question|preference|decision
    statement: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict] = mapped_column(JSON, default=dict)
    sample_size: Mapped[int] = mapped_column(Integer, default=1)
    confidence: Mapped[str] = mapped_column(String(10), default="low")
    decision: Mapped[str | None] = mapped_column(String(20))  # repeat|avoid|test_more
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Comment(Base, TimestampMixin):
    """Comments on the account's own media (instagram_business_manage_comments)."""

    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    ig_comment_id: Mapped[str] = mapped_column(String(64), unique=True)
    media_id: Mapped[int | None] = mapped_column(ForeignKey("media.id", ondelete="CASCADE"), index=True)
    username: Mapped[str | None] = mapped_column(String(120))
    text: Mapped[str] = mapped_column(Text)
    commented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    like_count: Mapped[int | None] = mapped_column(Integer)
    intent: Mapped[str] = mapped_column(
        String(20), default="other"
    )  # question|request|praise|feedback|spam|other
    draft_reply: Mapped[str | None] = mapped_column(Text)
    replied: Mapped[bool] = mapped_column(Boolean, default=False)
    reply_text: Mapped[str | None] = mapped_column(Text)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id", ondelete="SET NULL"))
    parent_ig_id: Mapped[str | None] = mapped_column(String(64), index=True)  # set on replies
    from_owner: Mapped[bool] = mapped_column(Boolean, default=False)  # reply written by the account itself
    source: Mapped[str] = mapped_column(String(20))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Mention(Base, TimestampMixin):
    """Media where the account was tagged (GET /{ig-user-id}/tags)."""

    __tablename__ = "mentions"
    id: Mapped[int] = mapped_column(primary_key=True)
    ig_media_id: Mapped[str] = mapped_column(String(64), unique=True)
    username: Mapped[str | None] = mapped_column(String(120))
    caption: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str | None] = mapped_column(String(500))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(20))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class AudienceSnapshot(Base):
    """follower_demographics / engaged_audience_demographics / online_followers, one row per day+kind."""

    __tablename__ = "audience_snapshots"
    __table_args__ = (UniqueConstraint("account_id", "snapshot_date", "kind", name="uq_audience_day_kind"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("instagram_accounts.id", ondelete="CASCADE"), index=True
    )
    snapshot_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(
        String(40)
    )  # followers_age|followers_gender|followers_city|followers_country|online_hours
    data: Mapped[dict] = mapped_column(JSON)
    source: Mapped[str] = mapped_column(String(20))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


INTEREST_SOURCES = ("saved", "liked", "following", "topic", "manual")


class InterestItem(Base, TimestampMixin):
    """Something the user saved, liked, follows or noted. Only from their own data download or typed in.
    URLs are stored as text and never fetched."""

    __tablename__ = "interest_items"
    __table_args__ = (UniqueConstraint("is_demo", "dedupe_key", name="uq_interest_item"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(20), index=True)  # INTEREST_SOURCES
    creator: Mapped[str | None] = mapped_column(String(120))
    url: Mapped[str | None] = mapped_column(String(1000))
    title: Mapped[str | None] = mapped_column(String(300))
    note: Mapped[str | None] = mapped_column(Text)
    collection: Mapped[str | None] = mapped_column(String(200))
    happened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    origin: Mapped[str] = mapped_column(String(20))  # import | manual | demo
    dedupe_key: Mapped[str] = mapped_column(String(300))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Recommendation(Base, TimestampMixin):
    """A next-reel suggestion as shown to the user, with its reasons, plus their verdict."""

    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(40))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    feedback: Mapped[str | None] = mapped_column(String(20))  # made_it | not_for_me
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    idea_id: Mapped[int | None] = mapped_column(ForeignKey("content_ideas.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
