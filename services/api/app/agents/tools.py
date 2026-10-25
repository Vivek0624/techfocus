"""Typed tools agents may call. Narrow by design:
- no shell, no SQL, no filesystem, no arbitrary network;
- read tools return summaries from the service layer;
- write tools only create drafts / proposals / pending approval requests. Nothing here publishes."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models import (
    CONTENT_STATUSES,
    ApprovalRequest,
    CalendarItem,
    ContentIdea,
    Experiment,
    ToolCallAudit,
)
from ..services import analytics as an
from ..services import queries as q


class ToolError(Exception):
    pass


@dataclass
class ToolContext:
    db: Session
    run_id: int | None
    allowed: set[str]
    demo: bool
    calls: list[str] = field(default_factory=list)


@dataclass
class ToolSpec:
    name: str
    description: str
    fn: Callable[..., Any]
    is_write: bool = False


def _audit(ctx: ToolContext, name: str, args: dict, ok: bool, err: str | None, write: bool) -> None:
    ctx.db.add(ToolCallAudit(run_id=ctx.run_id, tool=name, args=args, ok=ok, error=err, is_write=write))
    ctx.calls.append(name)


def call_tool(ctx: ToolContext, name: str, **args: Any) -> Any:
    spec = TOOLS.get(name)
    if spec is None:
        raise ToolError(f"unknown tool {name}")
    if name not in ctx.allowed:
        _audit(ctx, name, args, False, "not permitted for this agent", spec.is_write)
        raise ToolError(f"{name} is not permitted for this agent")
    try:
        out = spec.fn(ctx, **args)
    except ToolError as e:
        _audit(ctx, name, args, False, str(e), spec.is_write)
        raise
    except TypeError as e:
        _audit(ctx, name, args, False, "invalid arguments", spec.is_write)
        raise ToolError(f"invalid arguments for {name}: {e}") from e
    _audit(ctx, name, args, True, None, spec.is_write)
    return out


# ---------------- read tools ----------------


def get_account_summary(ctx: ToolContext) -> dict:
    return q.account_summary(ctx.db, demo=ctx.demo)


def get_follower_history(ctx: ToolContext, days: int = 30) -> list[dict]:
    days = max(1, min(int(days), 365))
    return q.follower_history(ctx.db, ctx.demo, days)


def get_instagram_insights(ctx: ToolContext, days: int = 7) -> dict:
    days = max(1, min(int(days), 90))
    return q.account_insights_window(ctx.db, ctx.demo, days)


def list_recent_media(ctx: ToolContext, limit: int = 12) -> list[dict]:
    limit = max(1, min(int(limit), 50))
    return q.media_with_latest(ctx.db, ctx.demo)[:limit]


def get_media_insights(ctx: ToolContext, media_id: str) -> dict:
    for m in q.media_with_latest(ctx.db, ctx.demo):
        if m["ig_media_id"] == media_id:
            return m
    raise ToolError("media not found")


def get_top_performing_reels(ctx: ToolContext, limit: int = 5) -> list[dict]:
    posts = an.outlier_multiples(q.media_with_latest(ctx.db, ctx.demo))
    ranked = sorted([p for p in posts if p["multiple"] is not None], key=lambda p: -p["multiple"])
    return ranked[: max(1, min(int(limit), 20))]


def get_content_ideas(ctx: ToolContext, status: str | None = None, limit: int = 20) -> list[dict]:
    stmt = select(ContentIdea).where(ContentIdea.is_demo.is_(ctx.demo))
    if status:
        if status not in CONTENT_STATUSES:
            raise ToolError(f"status must be one of {CONTENT_STATUSES}")
        stmt = stmt.where(ContentIdea.status == status)
    rows = ctx.db.scalars(stmt.order_by(ContentIdea.created_at.desc()).limit(min(int(limit), 50)))
    return [
        {"id": r.id, "title": r.title, "pillar": r.pillar, "status": r.status, "hook": r.recommended_hook}
        for r in rows
    ]


def search_content_library(ctx: ToolContext, query: str) -> list[dict]:
    if not query or len(query) > 100:
        raise ToolError("query must be 1-100 characters")
    like = f"%{query}%"
    rows = ctx.db.scalars(
        select(ContentIdea)
        .where(
            ContentIdea.is_demo.is_(ctx.demo),
            or_(
                ContentIdea.title.ilike(like),
                ContentIdea.recommended_hook.ilike(like),
                ContentIdea.pillar.ilike(like),
            ),
        )
        .limit(20)
    )
    return [{"id": r.id, "title": r.title, "status": r.status} for r in rows]


def get_experiment_results(ctx: ToolContext) -> list[dict]:
    out = []
    for e in ctx.db.scalars(select(Experiment).where(Experiment.is_demo.is_(ctx.demo))):
        c = [o.value for o in e.observations if o.arm == "control"]
        v = [o.value for o in e.observations if o.arm == "variant"]
        out.append(
            {
                "id": e.id,
                "name": e.name,
                "variable": e.variable,
                "status": e.status,
                "result": an.evaluate_experiment(c, v, e.min_samples_per_arm),
            }
        )
    return out


def get_audience_questions(ctx: ToolContext) -> dict:
    """Comment access needs instagram_business_manage_comments. Until synced, report unavailability."""
    return {
        "available": False,
        "questions": [],
        "note": "Comment sync is not enabled yet; no audience questions have been collected.",
    }


def get_growth_target_progress(ctx: ToolContext) -> dict:
    return q.target_progress_dict(ctx.db, ctx.demo)


# ---------------- write tools (local drafts only) ----------------


def save_content_draft(
    ctx: ToolContext,
    title: str,
    pillar: str,
    recommended_hook: str,
    script: str = "",
    caption: str = "",
    hypothesis: str = "",
) -> dict:
    if not (1 <= len(title) <= 200):
        raise ToolError("title must be 1-200 chars")
    idea = ContentIdea(
        title=title,
        pillar=pillar,
        recommended_hook=recommended_hook,
        script=script,
        caption=caption,
        hypothesis=hypothesis,
        status="idea",
        is_demo=ctx.demo,
        hook_options=[recommended_hook],
    )
    ctx.db.add(idea)
    ctx.db.flush()
    return {"id": idea.id, "status": idea.status}


def update_content_status(ctx: ToolContext, idea_id: int, status: str) -> dict:
    if status not in CONTENT_STATUSES or status == "published":
        raise ToolError("agents may not mark content published")
    idea = ctx.db.get(ContentIdea, int(idea_id))
    if idea is None or idea.is_demo != ctx.demo:
        raise ToolError("idea not found")
    idea.status = status
    return {"id": idea.id, "status": status}


def create_growth_experiment(
    ctx: ToolContext,
    name: str,
    hypothesis: str,
    variable: str,
    control: str,
    variant: str,
    primary_metric: str = "views",
) -> dict:
    e = Experiment(
        name=name[:200],
        hypothesis=hypothesis,
        variable=variable[:60],
        control=control,
        variant=variant,
        primary_metric=primary_metric[:40],
        status="planned",
        is_demo=ctx.demo,
    )
    ctx.db.add(e)
    ctx.db.flush()
    return {"id": e.id, "status": "planned"}


def propose_calendar_change(
    ctx: ToolContext, title: str, date_iso: str, time_ist: str = "19:00", idea_id: int | None = None
) -> dict:
    """Creates a calendar item in 'proposed' state. The user must approve it in the UI."""
    from datetime import datetime

    try:
        when = datetime.fromisoformat(f"{date_iso}T{time_ist}:00").replace(tzinfo=an.IST)
    except ValueError as e:
        raise ToolError("date_iso must be YYYY-MM-DD and time_ist HH:MM") from e
    item = CalendarItem(
        title=title[:200],
        idea_id=idea_id,
        scheduled_at=when,
        production_status="proposed",
        approval_status="pending",
        is_demo=ctx.demo,
    )
    ctx.db.add(item)
    ctx.db.flush()
    return {"calendar_item_id": item.id, "state": "proposed"}


def create_approval_request(ctx: ToolContext, action: str, target_id: int, summary: str) -> dict:
    if action not in ("publish_media", "post_comment_reply"):
        raise ToolError("unsupported action")
    ap = ApprovalRequest(
        action=action,
        target_type="calendar_item" if action == "publish_media" else "comment",
        target_id=int(target_id),
        summary=summary[:500],
        requested_by="agent",
    )
    ctx.db.add(ap)
    ctx.db.flush()
    return {"approval_id": ap.id, "status": "pending", "note": "A human must approve this in the dashboard."}


TOOLS: dict[str, ToolSpec] = {
    s.name: s
    for s in [
        ToolSpec(
            "get_account_summary", "Profile, follower count, data source and freshness.", get_account_summary
        ),
        ToolSpec(
            "get_follower_history", "Daily follower snapshots for the last N days.", get_follower_history
        ),
        ToolSpec(
            "get_instagram_insights",
            "Account-level reach, views, interactions over N days.",
            get_instagram_insights,
        ),
        ToolSpec("list_recent_media", "Recent posts with latest metrics.", list_recent_media),
        ToolSpec("get_media_insights", "Metrics for one media id.", get_media_insights),
        ToolSpec(
            "get_top_performing_reels",
            "Posts ranked by outlier multiple over account median.",
            get_top_performing_reels,
        ),
        ToolSpec("get_content_ideas", "Content library entries, optionally by status.", get_content_ideas),
        ToolSpec("search_content_library", "Search ideas by text.", search_content_library),
        ToolSpec("get_experiment_results", "Experiments with statistical read-outs.", get_experiment_results),
        ToolSpec(
            "get_audience_questions",
            "Recurring audience questions from comments, if synced.",
            get_audience_questions,
        ),
        ToolSpec(
            "get_growth_target_progress", "Progress toward the follower target.", get_growth_target_progress
        ),
        ToolSpec("save_content_draft", "Save a new idea as a local draft.", save_content_draft, True),
        ToolSpec(
            "update_content_status", "Move an idea between draft statuses.", update_content_status, True
        ),
        ToolSpec("create_growth_experiment", "Create a planned experiment.", create_growth_experiment, True),
        ToolSpec(
            "propose_calendar_change",
            "Propose a calendar slot (needs user approval).",
            propose_calendar_change,
            True,
        ),
        ToolSpec(
            "create_approval_request",
            "Ask the human to approve an external action.",
            create_approval_request,
            True,
        ),
    ]
}
