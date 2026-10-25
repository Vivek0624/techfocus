"""Read-side queries shared by the API and the agent tools. `demo` selects the data partition:
demo rows and real rows are never combined in one result."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    SOURCE_API,
    SOURCE_DEMO,
    AccountSnapshot,
    AppSetting,
    InstagramAccount,
    InstagramToken,
    Media,
    MediaSnapshot,
    iso_utc,
)
from . import analytics as an

DEFAULT_TARGET = {"target": 10000, "days": 30, "start_followers": None, "start_date": None}


def get_setting(db: Session, key: str, default=None):
    row = db.get(AppSetting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value) -> None:
    row = db.get(AppSetting, key)
    if row is None:
        db.add(AppSetting(key=key, value=value))
    else:
        row.value = value
    db.flush()


def data_mode(db: Session) -> str:
    """'live' if a real account is connected, 'manual' if manual data exists, else 'demo'."""
    if db.scalar(
        select(InstagramToken.id)
        .join(InstagramAccount)
        .where(InstagramAccount.is_demo.is_(False), InstagramAccount.connected.is_(True))
    ):
        return "live"
    if get_setting(db, "prefer_real_data", False):
        return "manual"
    return "demo"


def use_demo(db: Session) -> bool:
    return data_mode(db) == "demo"


def account(db: Session, demo: bool) -> InstagramAccount | None:
    stmt = select(InstagramAccount).where(InstagramAccount.is_demo.is_(demo))
    if demo:
        return db.scalar(stmt.order_by(InstagramAccount.id))
    stmt = stmt.where(InstagramAccount.connected.is_(True))
    # Prefer the OAuth-connected account over a manual-entry one.
    return db.scalar(stmt.join(InstagramToken).order_by(InstagramAccount.id)) or db.scalar(
        stmt.order_by(InstagramAccount.id)
    )


def follower_history(db: Session, demo: bool, days: int, today: date | None = None) -> list[dict]:
    acct = account(db, demo)
    if acct is None:
        return []
    today = today or date.today()
    rows = db.scalars(
        select(AccountSnapshot)
        .where(
            AccountSnapshot.account_id == acct.id,
            AccountSnapshot.snapshot_date >= today - timedelta(days=days),
        )
        .order_by(AccountSnapshot.snapshot_date)
    )
    return [
        {
            "date": r.snapshot_date.isoformat(),
            "followers": r.followers,
            "follows": r.follows,
            "unfollows": r.unfollows,
            "reach": r.reach,
            "views": r.views,
            "accounts_engaged": r.accounts_engaged,
            "likes": r.likes,
            "comments": r.comments,
            "shares": r.shares,
            "saves": r.saves,
            "profile_links_taps": r.profile_links_taps,
            "source": r.source,
            "fetched_at": iso_utc(r.fetched_at),
        }
        for r in rows
    ]


def _sum(rows: list[dict], k: str) -> int | None:
    vals = [r[k] for r in rows if r.get(k) is not None]
    return sum(vals) if vals else None


def account_insights_window(db: Session, demo: bool, days: int, today: date | None = None) -> dict:
    hist = follower_history(db, demo, days, today)
    first = next((r["followers"] for r in hist if r["followers"] is not None), None)
    last = next((r["followers"] for r in reversed(hist) if r["followers"] is not None), None)
    sources = sorted({r["source"] for r in hist})
    return {
        "days": days,
        "followers_start": first,
        "followers_end": last,
        "net_follower_growth": an.net_growth(first, last),
        "pct_follower_growth": an.pct_growth(first, last),
        "followers_gained": _sum(hist, "follows"),
        "followers_lost": _sum(hist, "unfollows"),
        "reach": _sum(hist, "reach"),
        "views": _sum(hist, "views"),
        "accounts_engaged": _sum(hist, "accounts_engaged"),
        "likes": _sum(hist, "likes"),
        "comments": _sum(hist, "comments"),
        "shares": _sum(hist, "shares"),
        "saves": _sum(hist, "saves"),
        "profile_links_taps": _sum(hist, "profile_links_taps"),
        "follows_per_1k_reach": an.follows_per_1k_reach(hist),
        "sources": sources,
        "last_refresh": hist[-1]["fetched_at"] if hist else None,
    }


def media_with_latest(db: Session, demo: bool, since: date | None = None) -> list[dict]:
    acct = account(db, demo)
    if acct is None:
        return []
    stmt = select(Media).where(Media.account_id == acct.id)
    if since:
        stmt = stmt.where(Media.published_at >= datetime.combine(since, time.min, tzinfo=UTC))
    out = []
    for m in db.scalars(stmt.order_by(Media.published_at.desc())):
        snap = db.scalar(
            select(MediaSnapshot)
            .where(MediaSnapshot.media_id == m.id)
            .order_by(MediaSnapshot.snapshot_date.desc())
            .limit(1)
        )
        out.append(
            {
                "id": m.id,
                "ig_media_id": m.ig_media_id,
                "caption": (m.caption or "")[:300],
                "media_product_type": m.media_product_type,
                "permalink": m.permalink,
                "published_at": m.published_at,
                "pillar": m.pillar,
                "hook_style": m.hook_style,
                "media_type": m.media_type,
                "audience": m.audience,
                "source": m.source,
                **(
                    {
                        k: getattr(snap, k)
                        for k in (
                            "views",
                            "reach",
                            "likes",
                            "comments",
                            "shares",
                            "saved",
                            "total_interactions",
                            "avg_watch_time_ms",
                            "total_watch_time_ms",
                            "follows",
                            "profile_visits",
                            "profile_activity",
                            "reposts",
                        )
                    }
                    if snap
                    else {}
                ),
                "metrics_fetched_at": iso_utc(snap.fetched_at) if snap else None,
            }
        )
    return out


def account_summary(db: Session, demo: bool) -> dict:
    acct = account(db, demo)
    hist = follower_history(db, demo, 400)
    cur = next((r["followers"] for r in reversed(hist) if r["followers"] is not None), None)
    return {
        "mode": "demo" if demo else data_mode(db),
        "username": acct.username if acct else None,
        "account_type": acct.account_type if acct else None,
        "followers": cur,
        "source": (SOURCE_DEMO if demo else (hist[-1]["source"] if hist else SOURCE_API)) if hist else None,
        "last_refresh": hist[-1]["fetched_at"] if hist else None,
    }


def target_config(db: Session, demo: bool) -> dict:
    return {**DEFAULT_TARGET, **(get_setting(db, "demo_target" if demo else "growth_target", {}) or {})}


def target_progress_dict(db: Session, demo: bool, today: date | None = None) -> dict:
    cfg = target_config(db, demo)
    summ = account_summary(db, demo)
    if cfg.get("start_followers") is None or not cfg.get("start_date"):
        return {
            "configured": False,
            "config": cfg,
            "note": "Set your starting follower count and start date in onboarding.",
        }
    today = today or date.today()
    tp = an.target_progress(
        int(cfg["start_followers"]),
        int(cfg["target"]),
        date.fromisoformat(cfg["start_date"]),
        int(cfg["days"]),
        summ["followers"],
        today,
    )
    d = tp.__dict__ | {"start_date": tp.start_date.isoformat(), "end_date": tp.end_date.isoformat()}
    d["scenarios"] = (
        an.scenarios(tp.current, tp.days_remaining, [25, 75, 150, tp.required_per_day or 0])
        if tp.current is not None
        else []
    )
    d["scenario_note"] = "Scenarios are arithmetic illustrations, not predictions."
    return {"configured": True, "config": cfg, **d}
