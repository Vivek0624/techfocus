"""Endpoints for the five creator screens: Today, Ideas, Create, Insights, Connect."""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import (
    AUDIENCE_SEGMENTS,
    CATEGORIES,
    CONTENT_STATUSES,
    FORMATS,
    SOURCE_MANUAL,
    CalendarItem,
    ContentIdea,
    DailyTask,
    InstagramAccount,
    Media,
    MediaSnapshot,
    iso_utc,
    utcnow,
)
from ..services import coach, creator, growth
from ..services import queries as q
from ..services.analytics import IST

router = APIRouter()

Audience = Literal["beginner", "developer"]
Perspective = Literal["third", "you", "i"]


# ---------------- shared ----------------


def _posts(db: Session) -> list[dict]:
    demo = q.use_demo(db)
    rows = q.media_with_latest(db, demo)
    ids = [r["id"] for r in rows]
    extra = {m.id: m for m in db.scalars(select(Media).where(Media.id.in_(ids)))} if ids else {}
    titles = {}
    idea_ids = [m.content_idea_id for m in extra.values() if m.content_idea_id]
    if idea_ids:
        titles = {i.id: i.title for i in db.scalars(select(ContentIdea).where(ContentIdea.id.in_(idea_ids)))}
    out = []
    for r in rows:
        m = extra[r["id"]]
        out.append(
            {
                **r,
                "title": (titles.get(m.content_idea_id) if m.content_idea_id else None)
                or (r["caption"] or "").split("\n")[0][:80]
                or "(untitled)",
                "hook_text": m.hook_text,
                "format_style": m.format_style,
                "length_seconds": m.length_seconds,
                "content_idea_id": m.content_idea_id,
                "hook_style": m.hook_style or (creator.classify_hook(m.hook_text) if m.hook_text else None),
            }
        )
    return out


def _real_account(db: Session) -> InstagramAccount:
    acct = db.scalar(
        select(InstagramAccount).where(InstagramAccount.is_demo.is_(False)).order_by(InstagramAccount.id)
    )
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
    q.set_setting(db, "prefer_real_data", True)
    return acct


# ---------------- Today ----------------


@router.get("/today")
def today(db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    posts_now = _posts(db)
    analysis = coach.analyse(posts_now)
    tip = next((i for i in analysis["insights"] if i["confidence"] not in ("none",)), None)
    pipeline = {
        s: db.scalars(
            select(ContentIdea)
            .where(ContentIdea.is_demo.is_(demo), ContentIdea.status == s)
            .order_by(ContentIdea.updated_at.desc())
        ).all()
        for s in CONTENT_STATUSES
    }
    step = {
        "ready": "Post it",
        "editing": "Finish the edit",
        "recording": "Record it",
        "script": "Finish the script",
    }
    pick, verb = None, None
    for s in ("ready", "editing", "recording", "script"):
        if pipeline[s]:
            pick, verb = pipeline[s][0], step[s]
            break
    if pick is None:
        # Nothing in progress: choose an inbox idea, preferring the topic that is working.
        top_cat = next((i.get("group") for i in analysis["insights"] if i.get("key") == "pillar"), None)
        inbox = pipeline["idea"]
        pick = next((i for i in inbox if i.pillar == top_cat), inbox[0] if inbox else None)
        verb = "Script this idea" if pick else None
    suggestion = None
    if pick:
        hooks = creator.generate_hooks(pick.title, "beginner", "third", 3)
        hook = pick.recommended_hook or hooks[0].text
        cap = creator.generate_caption(pick.title, hook, pick.pillar or "tech_concepts")
        suggestion = {
            "idea_id": pick.id,
            "title": pick.title,
            "status": pick.status,
            "step": verb,
            "category": pick.pillar,
            "hook": hook,
            "hook_score": creator.score_hook(hook, "third"),
            "alt_hooks": [h.model_dump() for h in hooks if h.text != hook][:2],
            "caption": cap.full,
            "hashtags": cap.hashtags,
            "why": (
                tip["headline"]
                if tip and tip.get("group") == pick.pillar
                else "Next in your pipeline."
                if verb != "Script this idea"
                else "From your idea inbox."
            ),
        }
    now = utcnow()
    week_ago = now - timedelta(days=7)
    published_week = sum(
        1
        for p in analysis["posts"]
        if p.get("published_at")
        and (p["published_at"] if p["published_at"].tzinfo else p["published_at"].replace(tzinfo=UTC))
        >= week_ago
    )
    brand = q.get_setting(db, "brand", {}) or {}
    upcoming = db.scalars(
        select(CalendarItem)
        .where(
            CalendarItem.is_demo.is_(demo),
            CalendarItem.scheduled_at >= now,
            CalendarItem.scheduled_at < now + timedelta(days=2),
        )
        .order_by(CalendarItem.scheduled_at)
    ).all()
    brief = growth.shortlist([_idea_dict(i) for s_ in CONTENT_STATUSES for i in pipeline[s_]], posts_now)
    tasks = db.scalars(
        select(DailyTask)
        .where(DailyTask.is_demo.is_(demo), DailyTask.task_date == date.today())
        .order_by(DailyTask.done, DailyTask.priority.desc())
    ).all()
    acct = q.account(db, demo)
    return {
        "mode": "demo" if demo else q.data_mode(db),
        "last_sync_at": iso_utc(acct.last_sync_at) if acct and acct.last_sync_at else None,
        "suggestion": suggestion,
        "tip": tip,
        "goal": q.target_progress_dict(db, demo),
        "week": {"published": published_week, "target": int(brand.get("posts_per_week", 4))},
        "pipeline_counts": {s: len(v) for s, v in pipeline.items()},
        "reminders": [
            {"id": c.id, "title": c.title, "scheduled_at": iso_utc(c.scheduled_at)} for c in upcoming
        ],
        "tasks": [{"id": t.id, "title": t.title, "done": t.done} for t in tasks],
        "shortlist": brief["items"],
        "memory": brief["memory"],
    }


def _idea_dict(i: ContentIdea) -> dict:
    return {
        "id": i.id,
        "title": i.title,
        "status": i.status,
        "pillar": i.pillar,
        "format": i.format,
        "recommended_hook": i.recommended_hook,
        "audience": i.audience,
    }


# ---------------- Ideas ----------------


class QuickIdea(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    category: Literal[CATEGORIES] | None = None  # type: ignore[valid-type]
    force: bool = False


def _candidates(db: Session, exclude_id: int | None = None) -> list[tuple[str, str, int]]:
    demo = q.use_demo(db)
    c: list[tuple[str, str, int]] = []
    for i in db.scalars(
        select(ContentIdea).where(ContentIdea.is_demo.is_(demo), ContentIdea.status != "archived")
    ):
        if i.id != exclude_id:
            c.append(("idea", f"{i.title} || {i.recommended_hook or ''}", i.id))
    for p in _posts(db):
        c.append(("post", p["title"] + " || " + (p.get("hook_text") or ""), p["id"]))
    return c


@router.post("/ideas/check-duplicate")
def check_duplicate(body: QuickIdea, db: Session = Depends(get_db)):
    return {"similar": creator.similar(body.title + " " + (body.note or ""), _candidates(db))}


@router.post("/ideas/quick", status_code=201)
def quick_idea(body: QuickIdea, db: Session = Depends(get_db)):
    """Inbox capture. Warns (409) about near-duplicates unless force=true."""
    sim = creator.similar(body.title + " " + (body.note or ""), _candidates(db))
    if sim and not body.force:
        raise HTTPException(409, {"message": "Looks similar to something you already have", "similar": sim})
    idea = ContentIdea(
        title=body.title,
        pillar=body.category,
        status="idea",
        is_demo=q.use_demo(db),
        evidence=[body.note] if body.note else [],
        notes=body.note,
        hook_options=[],
    )
    db.add(idea)
    db.flush()
    return {"id": idea.id, "status": idea.status}


@router.get("/board")
def board(category: str | None = None, db: Session = Depends(get_db)):
    stmt = select(ContentIdea).where(
        ContentIdea.is_demo.is_(q.use_demo(db)), ContentIdea.status != "archived"
    )
    if category:
        stmt = stmt.where(ContentIdea.pillar == category)
    cols: dict[str, list] = {s: [] for s in CONTENT_STATUSES if s != "archived"}
    planned = {
        c.idea_id: c for c in db.scalars(select(CalendarItem).where(CalendarItem.idea_id.is_not(None)))
    }
    posts = _posts(db)
    for i in db.scalars(stmt.order_by(ContentIdea.updated_at.desc())):
        cal = planned.get(i.id)
        aud = growth.audience_of(_idea_dict(i))
        sh = growth.shareability(i.recommended_hook or i.title, i.pillar, i.format, posts)
        cols[i.status].append(
            {
                "id": i.id,
                "title": i.title,
                "category": i.pillar,
                "hook": i.recommended_hook,
                "format": i.format,
                "updated_at": iso_utc(i.updated_at),
                "planned_at": iso_utc(cal.scheduled_at) if cal else None,
                "calendar_id": cal.id if cal else None,
                "audience": aud["audience"],
                "audience_inferred": aud["inferred"],
                "shareability": sh["score"],
            }
        )
    return {
        "columns": [{"status": s, "items": v} for s, v in cols.items()],
        "categories": list(CATEGORIES),
        "formats": list(FORMATS),
        "audiences": list(AUDIENCE_SEGMENTS),
    }


class PlanIn(BaseModel):
    when: datetime  # naive = IST wall clock


@router.post("/ideas/{idea_id}/plan")
def plan_idea(idea_id: int, body: PlanIn, db: Session = Depends(get_db)):
    """Put an idea on the calendar (one slot per idea; re-planning moves it). Reminders fire 1h before."""
    idea = db.get(ContentIdea, idea_id)
    if idea is None:
        raise HTTPException(404, "idea not found")
    when = body.when if body.when.tzinfo else body.when.replace(tzinfo=IST)
    when = when.astimezone(UTC)
    cal = db.scalar(select(CalendarItem).where(CalendarItem.idea_id == idea_id))
    if cal is None:
        cal = CalendarItem(
            idea_id=idea_id,
            title=idea.title,
            scheduled_at=when,
            format=idea.format,
            caption=idea.caption,
            is_demo=idea.is_demo,
        )
        db.add(cal)
    cal.scheduled_at, cal.reminder_sent_at = when, None
    idea.planned_at = when
    db.flush()
    return {"calendar_id": cal.id, "scheduled_at": iso_utc(cal.scheduled_at)}


@router.get("/week")
def week(start: date | None = None, db: Session = Depends(get_db)):
    """Mon-Sun in IST."""
    today_ist = datetime.now(IST).date()
    start = start or today_ist - timedelta(days=today_ist.weekday())
    s = datetime.combine(start, datetime.min.time(), tzinfo=IST).astimezone(UTC)
    e = s + timedelta(days=7)
    items = db.scalars(
        select(CalendarItem)
        .where(
            CalendarItem.is_demo.is_(q.use_demo(db)),
            CalendarItem.scheduled_at >= s,
            CalendarItem.scheduled_at < e,
        )
        .order_by(CalendarItem.scheduled_at)
    ).all()
    status = (
        {
            i.id: i.status
            for i in db.scalars(
                select(ContentIdea).where(ContentIdea.id.in_([c.idea_id for c in items if c.idea_id]))
            )
        }
        if items
        else {}
    )
    return {
        "start": start.isoformat(),
        "items": [
            {
                "id": c.id,
                "idea_id": c.idea_id,
                "title": c.title,
                "scheduled_at": iso_utc(c.scheduled_at),
                "status": status.get(c.idea_id) if c.idea_id else None,
                "published": c.publishing_status == "published",
            }
            for c in items
        ],
    }


# ---------------- Create ----------------


class HookReq(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    audience: Audience = "beginner"
    perspective: Perspective = "third"


class HookList(BaseModel):
    hooks: list[creator.Hook]


@router.post("/create/hooks")
def create_hooks(body: HookReq):
    res, src = creator.generate_with_model(
        "Write 6 short Reel hooks (under 12 words each), each a different formula, in the requested perspective "
        "('third' = about someone else, e.g. 'Most beginners...'). Return text, formula, on_screen (<=5 words).",
        body.model_dump(),
        HookList,
        lambda: HookList(hooks=creator.generate_hooks(body.topic, body.audience, body.perspective)),
    )
    hooks = []
    for h in res.hooks:  # always score locally so template and model hooks are comparable
        sc = creator.score_hook(h.text, body.perspective)
        hooks.append(
            {
                **h.model_dump(),
                "score": sc["score"],
                "verdict": sc["verdict"],
                "fix": sc["fix"],
                "checks": sc["checks"],
            }
        )
    return {
        "source": src,
        "hooks": sorted(hooks, key=lambda h: -h["score"]),
        "note": "Scores catch weak hooks (too long, vague, slow to the point). They can't predict which good "
        "hook will travel: your delivery and edit decide that.",
    }


class ScoreReq(BaseModel):
    text: str = Field(min_length=1, max_length=300)
    perspective: Perspective = "you"


@router.post("/create/score-hook")
def score_one(body: ScoreReq):
    return {**creator.score_hook(body.text, body.perspective), "formula": creator.classify_hook(body.text)}


class CaptionReq(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    hook: str | None = Field(default=None, max_length=300)
    category: Literal[CATEGORIES] = "tech_concepts"  # type: ignore[valid-type]
    audience: Audience = "beginner"


@router.post("/create/caption")
def create_caption(body: CaptionReq):
    res, src = creator.generate_with_model(
        "Write an Instagram caption: first_line (<=125 chars, it's all people see before '... more'), body, one "
        "cta, 3-5 search keywords, 3-5 relevant hashtags (no claims that hashtags boost reach), full text, and "
        "preview_cut = first 125 chars of full + '... more'.",
        body.model_dump(),
        creator.Caption,
        lambda: creator.generate_caption(body.topic, body.hook, body.category, body.audience),
    )
    return {"source": src, **res.model_dump(), "length": len(res.full), "max": 2200}


class RepurposeReq(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    audience: Audience = "beginner"
    hook: str | None = None
    idea_id: int | None = None


@router.post("/create/repurpose")
def create_repurpose(body: RepurposeReq):
    res, src = creator.generate_with_model(
        "Turn one idea into: reel_30s (beats with t/say/screen), a 5-slide carousel, a LinkedIn post, a YouTube "
        "Short script and a short text post, rewritten for the audience ('beginner' = non-technical, "
        "'developer' = working engineers).",
        body.model_dump(),
        creator.Repurposed,
        lambda: creator.repurpose(body.topic, body.audience, body.hook),
    )
    return {"source": src, **res.model_dump()}


class SaveToIdea(BaseModel):
    idea_id: int | None = None
    title: str | None = Field(default=None, max_length=200)
    hook: str | None = None
    caption: str | None = None
    hashtags: list[str] | None = None
    category: str | None = None
    package: dict | None = None


@router.post("/create/save")
def save_to_idea(body: SaveToIdea, db: Session = Depends(get_db)):
    """Attach generated work to an existing idea, or create one. Links Create -> Ideas."""
    if body.idea_id:
        idea = db.get(ContentIdea, body.idea_id)
        if idea is None:
            raise HTTPException(404, "idea not found")
    else:
        if not body.title:
            raise HTTPException(422, "title required for a new idea")
        idea = ContentIdea(title=body.title, status="script", is_demo=q.use_demo(db), hook_options=[])
        db.add(idea)
    if body.hook:
        idea.recommended_hook = body.hook
        idea.hook_options = list(dict.fromkeys([*(idea.hook_options or []), body.hook]))
    if body.caption:
        idea.caption = body.caption
    if body.hashtags is not None:
        idea.hashtags = body.hashtags
    if body.category:
        idea.pillar = body.category
    if body.package:
        idea.package = {**(idea.package or {}), **body.package}
    if idea.status == "idea" and (body.hook or body.package):
        idea.status = "script"
    db.flush()
    return {"id": idea.id, "status": idea.status}


# ---------------- Insights / posts ----------------


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    res = coach.analyse(_posts(db))
    res["posts"] = [
        {
            **{k: iso_utc(v) for k, v in p.items()},
            "attribution": growth.attribution(p),
            "audience_tag": growth.audience_of(p),
            "retention": retention(p),
        }
        for p in res["posts"]
    ]
    res["mode"] = "demo" if q.use_demo(db) else q.data_mode(db)
    res["account"] = q.account_insights_window(db, q.use_demo(db), 30)
    res["follower_history"] = q.follower_history(db, q.use_demo(db), 30)
    return res


@router.get("/insights/coach-ai")
def insights_coach_ai(db: Session = Depends(get_db)):
    """AI-written coach brief. Separate from /insights so the page loads instantly and the brief follows."""
    from ..agents.providers import MODEL_MODES

    if get_settings().agent_mode not in MODEL_MODES:
        return {"available": False, "source": "data", "note": "AI is off (AGENT_MODE=mock)."}
    return coach.ai_brief(coach.analyse(_posts(db)))


def retention(p: dict) -> dict | None:
    """Average seconds watched vs reel length. Uses ig_reels_avg_watch_time, else total watch time / plays."""
    avg_ms = p.get("avg_watch_time_ms")
    if avg_ms is None and p.get("total_watch_time_ms") and p.get("views"):
        avg_ms = p["total_watch_time_ms"] / p["views"]
    if avg_ms is None:
        return None
    avg = round(avg_ms / 1000, 1)
    length = p.get("length_seconds")
    pct = round(min(avg / length, 1) * 100) if length else None
    if pct is None:
        verdict = "Add the reel length (Length column) to see how much of it people watch."
    elif pct < 30:
        verdict = "Most people leave early. Make the first 2 seconds say the payoff."
    elif pct < 60:
        verdict = "People watch about half. Cut slow parts in the middle."
    else:
        verdict = "People watch most of it. Keep this pacing."
    return {
        "avg_seconds": avg,
        "length_seconds": length,
        "percent_watched": pct,
        "total_watch_hours": round(p["total_watch_time_ms"] / 3_600_000, 1)
        if p.get("total_watch_time_ms")
        else None,
        "verdict": verdict,
    }


class PostIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    published_at: datetime
    permalink: str | None = None
    hook_text: str | None = None
    category: Literal[CATEGORIES] | None = None  # type: ignore[valid-type]
    format_style: Literal[FORMATS] | None = None  # type: ignore[valid-type]
    length_seconds: int | None = Field(default=None, ge=1, le=900)
    idea_id: int | None = None
    views: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    avg_watch_seconds: float | None = Field(default=None, ge=0)


class PostTags(BaseModel):
    audience: Literal[AUDIENCE_SEGMENTS] | None = None  # type: ignore[valid-type]
    hook_text: str | None = None
    category: Literal[CATEGORIES] | None = None  # type: ignore[valid-type]
    format_style: Literal[FORMATS] | None = None  # type: ignore[valid-type]
    length_seconds: int | None = Field(default=None, ge=1, le=900)
    idea_id: int | None = None
    views: int | None = Field(default=None, ge=0)
    reach: int | None = Field(default=None, ge=0)
    likes: int | None = Field(default=None, ge=0)
    comments: int | None = Field(default=None, ge=0)
    shares: int | None = Field(default=None, ge=0)
    saves: int | None = Field(default=None, ge=0)
    avg_watch_seconds: float | None = Field(default=None, ge=0)


METRIC_MAP = {
    "views": "views",
    "reach": "reach",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saves": "saved",
}


def _apply(db: Session, m: Media, data: dict) -> None:
    if "hook_text" in data:
        m.hook_text = data["hook_text"]
        m.hook_style = creator.classify_hook(data["hook_text"]) if data["hook_text"] else None
    if "category" in data:
        m.pillar = data["category"]
    if "audience" in data:
        m.audience = data["audience"]
    for k in ("format_style", "length_seconds"):
        if k in data:
            setattr(m, k, data[k])
    if "idea_id" in data and data["idea_id"]:
        idea = db.get(ContentIdea, data["idea_id"])
        if idea:
            m.content_idea_id = idea.id
            idea.status, idea.published_media_id = "published", m.ig_media_id
    metrics = {METRIC_MAP[k]: data[k] for k in METRIC_MAP if data.get(k) is not None}
    if data.get("avg_watch_seconds") is not None:
        metrics["avg_watch_time_ms"] = int(data["avg_watch_seconds"] * 1000)
    if metrics:
        today_ = date.today()
        snap = db.scalar(
            select(MediaSnapshot).where(MediaSnapshot.media_id == m.id, MediaSnapshot.snapshot_date == today_)
        )
        if snap is None:
            snap = MediaSnapshot(media_id=m.id, snapshot_date=today_, source=m.source)
            db.add(snap)
        for k, v in metrics.items():
            setattr(snap, k, v)


@router.get("/posts")
def list_posts(db: Session = Depends(get_db)):
    return [{k: iso_utc(v) for k, v in p.items()} for p in _posts(db)]


@router.post("/posts", status_code=201)
def add_post(body: PostIn, db: Session = Depends(get_db)):
    """Manual entry for when the API isn't connected (or for metrics the API doesn't give)."""
    acct = q.account(db, False) or _real_account(db)
    if acct.is_demo:
        acct = _real_account(db)
    when = body.published_at if body.published_at.tzinfo else body.published_at.replace(tzinfo=IST)
    m = Media(
        account_id=acct.id,
        ig_media_id=f"manual-{int(datetime.now().timestamp() * 1000)}",
        media_type="VIDEO",
        media_product_type="REELS",
        caption=body.title,
        permalink=body.permalink,
        published_at=when.astimezone(UTC),
        source=SOURCE_MANUAL,
    )
    db.add(m)
    db.flush()
    _apply(db, m, body.model_dump(exclude={"title", "published_at", "permalink"}, exclude_none=True))
    q.set_setting(db, "prefer_real_data", True)
    db.flush()
    return {"id": m.id}


@router.patch("/posts/{post_id}")
def tag_post(post_id: int, body: PostTags, db: Session = Depends(get_db)):
    m = db.get(Media, post_id)
    if m is None:
        raise HTTPException(404, "post not found")
    _apply(db, m, body.model_dump(exclude_unset=True))
    db.flush()
    return {"ok": True, "hook_style": m.hook_style}


CSV_COLUMNS = [
    "date",
    "title",
    "views",
    "reach",
    "likes",
    "comments",
    "shares",
    "saves",
    "avg_watch_seconds",
    "category",
    "format",
    "length_seconds",
    "hook",
    "link",
]


@router.get("/posts/csv-template")
def csv_template():
    return {
        "columns": CSV_COLUMNS,
        "example": "2026-10-02,How to speak confidently,405000,300000,8848,39,1200,"
        "2100,6.5,skills,talking_head,45,Most people freeze in interviews,",
    }


class CsvIn(BaseModel):
    csv_text: str = Field(min_length=1, max_length=2_000_000)


@router.post("/posts/import-csv")
def import_csv(body: CsvIn, db: Session = Depends(get_db)):
    reader = csv.DictReader(io.StringIO(body.csv_text.strip()))
    missing = {"date", "title"} - set(reader.fieldnames or [])
    if missing:
        raise HTTPException(
            422, f"CSV needs columns: {', '.join(sorted(missing))}. Template: {', '.join(CSV_COLUMNS)}"
        )
    added, errors = 0, []

    def num(v: str | None, cast=int):
        v = (v or "").replace(",", "").strip()
        return cast(v) if v else None

    for i, row in enumerate(reader, start=2):
        try:
            cat = (row.get("category") or "").strip() or None
            fmt = (row.get("format") or "").strip() or None
            p = PostIn(
                title=row["title"].strip(),
                published_at=datetime.fromisoformat(row["date"].strip()),
                permalink=(row.get("link") or "").strip() or None,
                hook_text=(row.get("hook") or "").strip() or None,
                category=cat if cat in CATEGORIES else None,
                format_style=fmt if fmt in FORMATS else None,
                length_seconds=num(row.get("length_seconds")),
                views=num(row.get("views")),
                reach=num(row.get("reach")),
                likes=num(row.get("likes")),
                comments=num(row.get("comments")),
                shares=num(row.get("shares")),
                saves=num(row.get("saves")),
                avg_watch_seconds=num(row.get("avg_watch_seconds"), float),
            )
            add_post(p, db)
            added += 1
        except Exception as e:
            errors.append(f"row {i}: {type(e).__name__}: {str(e)[:120]}")
    return {"added": added, "errors": errors[:20]}


@router.get("/meta")
def meta():
    return {
        "categories": list(CATEGORIES),
        "formats": list(FORMATS),
        "statuses": list(CONTENT_STATUSES),
        "audiences": list(AUDIENCE_SEGMENTS),
    }
