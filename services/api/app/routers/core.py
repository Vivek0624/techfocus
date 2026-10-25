"""Dashboard, settings, growth target, analytics, daily plan."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (
    SOURCE_MANUAL,
    AccountSnapshot,
    AgentRun,
    CalendarItem,
    DailyTask,
    GrowthPlan,
    InstagramAccount,
    iso_utc,
    utcnow,
)
from ..schemas import AgentRunOut, ManualSnapshotIn, TargetIn, TaskIn, TaskOut
from ..seed import reset_demo
from ..services import analytics as an
from ..services import queries as q

router = APIRouter()


def _range(days: int | None, start: date | None, end: date | None) -> tuple[date, date, int]:
    end = end or date.today()
    if start:
        if start > end:
            raise HTTPException(422, "start must be before end")
        return start, end, (end - start).days or 1
    d = days or 30
    return end - timedelta(days=d), end, d


@router.get("/health")
def health(db: Session = Depends(get_db)):
    s = get_settings()
    db.execute(select(1))
    return {
        "status": "ok",
        "env": s.app_env,
        "agent_mode": s.agent_mode,
        "data_mode": q.data_mode(db),
        "instagram_configured": s.instagram_configured,
    }


@router.get("/dashboard")
def dashboard(
    days: int | None = Query(default=30, ge=1, le=365),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    demo = q.use_demo(db)
    s_, e_, n = _range(days, start, end)
    ins = q.account_insights_window(db, demo, n, today=e_)
    media = q.media_with_latest(db, demo)
    window_media = [m for m in media if m["published_at"] and s_ <= m["published_at"].date() <= e_]
    ranked = sorted(
        [m for m in an.outlier_multiples(window_media) if m["multiple"] is not None],
        key=lambda m: -m["multiple"],
    )
    upcoming = db.scalars(
        select(CalendarItem)
        .where(CalendarItem.is_demo.is_(demo), CalendarItem.scheduled_at >= utcnow())
        .order_by(CalendarItem.scheduled_at)
        .limit(5)
    )
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.is_demo.is_(demo), AgentRun.parent_run_id.is_(None))
        .order_by(AgentRun.created_at.desc())
        .limit(5)
    )
    plan = db.scalar(select(GrowthPlan).where(GrowthPlan.is_demo.is_(demo)).order_by(GrowthPlan.id.desc()))
    tasks = db.scalars(
        select(DailyTask)
        .where(DailyTask.is_demo.is_(demo), DailyTask.task_date == date.today(), DailyTask.done.is_(False))
        .order_by(DailyTask.priority.desc())
    )
    top_task = next(iter(tasks), None)
    return {
        "mode": "demo" if demo else q.data_mode(db),
        "range": {"start": s_.isoformat(), "end": e_.isoformat(), "days": n},
        "account": q.account_summary(db, demo),
        "metrics": ins,
        "metric_sources": {
            "followers": "demo" if demo else "instagram_api|manual",
            "reach/views/interactions": "demo" if demo else "instagram_api (Account Insights, day period)",
            "engagement_rate_by_reach": "calculated",
            "follows_per_1k_reach": "calculated",
        },
        "limitations": [
            "Instagram returns empty (not zero) when a metric is unavailable; those show as 'unavailable'.",
            "follows/unfollows are unavailable for accounts under 100 followers.",
            "Insights can lag up to 48 hours.",
            "History before the first sync is not available from the API.",
        ],
        "posts_published": len(window_media),
        "engagement_rate_by_reach": an.engagement_rate_by_reach(window_media),
        "reach_per_post": an.reach_per_post(m.get("reach") for m in window_media),
        "best_reels": [_post(m) for m in ranked[:5]],
        "recent_posts": [
            _post(m) for m in an.outlier_multiples(window_media)[:8]
        ],  # same baseline as /analytics
        "target": q.target_progress_dict(db, demo),
        "upcoming": [
            {
                "id": c.id,
                "title": c.title,
                "scheduled_at": iso_utc(c.scheduled_at),
                "approval_status": c.approval_status,
            }
            for c in upcoming
        ],
        "top_action": (
            {"title": top_task.title, "reason": top_task.reason}
            if top_task
            else {"title": plan.content.get("next_action"), "reason": "latest growth plan"}
            if plan
            else None
        ),
        "recent_agent_runs": [AgentRunOut.model_validate(r).model_dump(mode="json") for r in runs],
    }


def _post(m: dict) -> dict:
    return {k: iso_utc(v) for k, v in m.items()}


@router.get("/analytics")
def analytics(
    days: int | None = Query(default=30, ge=1, le=365),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    demo = q.use_demo(db)
    s_, e_, n = _range(days, start, end)
    media = [
        m for m in q.media_with_latest(db, demo) if m["published_at"] and s_ <= m["published_at"].date() <= e_
    ]
    posts = an.outlier_multiples(media)
    return {
        "mode": "demo" if demo else q.data_mode(db),
        "range": {"start": s_.isoformat(), "end": e_.isoformat()},
        "follower_history": q.follower_history(db, demo, n, today=e_),
        "insights": q.account_insights_window(db, demo, n, today=e_),
        "posts": [_post(p) for p in posts],
        "by_pillar": an.compare_groups(posts, "pillar"),
        "by_hook": an.compare_groups(posts, "hook_style"),
        "by_format": an.compare_groups(posts, "media_product_type"),
        "best_time": an.best_time_analysis(media),
        "definitions": an.METRIC_DEFINITIONS,
    }


@router.get("/settings")
def get_settings_view(db: Session = Depends(get_db)):
    s = get_settings()
    return {  # never returns secrets, only whether they are set
        "app_env": s.app_env,
        "agent_mode": s.agent_mode,
        "aws_region": s.aws_region,
        "bedrock_model_id": s.bedrock_model_id,
        "agentcore_runtime_configured": bool(s.agentcore_runtime_arn),
        "aws_profile": s.aws_profile,
        "meta_app_configured": bool(s.meta_app_id and s.meta_app_secret),
        "token_encryption_key_set": s.token_encryption_key is not None,
        "meta_redirect_uri": s.meta_redirect_uri,
        "meta_scopes": s.meta_scopes.split(","),
        "s3_media_bucket": s.s3_media_bucket,
        "research_provider_configured": bool(s.research_api_url),
        "local_scheduler": s.enable_local_scheduler,
        "data_mode": q.data_mode(db),
        "prefer_real_data": q.get_setting(db, "prefer_real_data", False),
        "brand": q.get_setting(
            db, "brand", {"handle": "vivek_techfocus", "posts_per_week": 5, "hours_per_week": 8}
        ),
    }


@router.put("/settings")
def update_settings(body: dict, db: Session = Depends(get_db)):
    allowed = {"prefer_real_data", "brand"}
    bad = set(body) - allowed
    if bad:
        raise HTTPException(422, f"not editable here: {sorted(bad)} (secrets live in .env)")
    for k, v in body.items():
        q.set_setting(db, k, v)
    return get_settings_view(db)


@router.post("/demo/reset")
def demo_reset(db: Session = Depends(get_db)):
    reset_demo(db)
    return {"ok": True, "note": "Demo data reset. Real account records were not touched."}


@router.get("/growth/target")
def get_target(db: Session = Depends(get_db)):
    return q.target_progress_dict(db, q.use_demo(db))


@router.put("/growth/target")
def set_target(body: TargetIn, db: Session = Depends(get_db)):
    key = "demo_target" if q.use_demo(db) else "growth_target"
    q.set_setting(db, key, body.model_dump(mode="json"))
    return q.target_progress_dict(db, q.use_demo(db))


@router.post("/growth/manual-snapshot")
def manual_snapshot(body: ManualSnapshotIn, db: Session = Depends(get_db)):
    """Manual import for when the API is not connected. Stored with source='manual'."""
    acct = db.scalar(select(InstagramAccount).where(InstagramAccount.is_demo.is_(False)))
    if acct is None:
        acct = InstagramAccount(
            ig_user_id="manual",
            username="vivek_techfocus (manual)",
            is_demo=False,
            connected=True,
            account_type="MEDIA_CREATOR",
        )
        db.add(acct)
        db.flush()
    row = db.scalar(
        select(AccountSnapshot).where(
            AccountSnapshot.account_id == acct.id,
            AccountSnapshot.snapshot_date == body.snapshot_date,
            AccountSnapshot.source == SOURCE_MANUAL,
        )
    )
    if row is None:
        row = AccountSnapshot(account_id=acct.id, snapshot_date=body.snapshot_date, source=SOURCE_MANUAL)
        db.add(row)
    for k, v in body.model_dump(exclude={"snapshot_date"}).items():
        setattr(row, k, v)
    q.set_setting(db, "prefer_real_data", True)
    db.flush()
    return {"ok": True}


@router.get("/growth/daily-plan", response_model=list[TaskOut])
def daily_plan(day: date | None = None, db: Session = Depends(get_db)):
    d = day or date.today()
    return db.scalars(
        select(DailyTask)
        .where(DailyTask.is_demo.is_(q.use_demo(db)), DailyTask.task_date == d)
        .order_by(DailyTask.done, DailyTask.priority.desc())
    ).all()


@router.post("/growth/daily-plan", response_model=TaskOut, status_code=201)
def add_task(body: TaskIn, db: Session = Depends(get_db)):
    t = DailyTask(
        task_date=date.today(),
        title=body.title,
        impact=body.impact,
        effort_minutes=body.effort_minutes,
        priority=body.impact * 10 - body.effort_minutes / 10,
        is_demo=q.use_demo(db),
        reason="added by you",
    )
    db.add(t)
    db.flush()
    return t


@router.patch("/growth/daily-plan/{task_id}", response_model=TaskOut)
def toggle_task(task_id: int, done: bool, db: Session = Depends(get_db)):
    t = db.get(DailyTask, task_id)
    if t is None:
        raise HTTPException(404, "task not found")
    t.done = done
    return t
