"""Interests (own data download + manual notes), next-reel recommendations with feedback, and bulk idea actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..agents.providers import MODEL_MODES
from ..config import get_settings
from ..db import get_db
from ..models import (
    CONTENT_STATUSES,
    AudienceSnapshot,
    ContentIdea,
    InterestItem,
    Recommendation,
    iso_utc,
    utcnow,
)
from ..services import activity as act
from ..services import growth, recommend
from ..services import interests as ints
from ..services import queries as q
from .creator import _candidates, _idea_dict, _posts
from .growth import _own_comments

router = APIRouter()

MAX_UPLOAD = 300 * 1024 * 1024


def _partition(db: Session, partition: str) -> bool:
    return True if partition == "demo" else q.use_demo(db)


# ---------------- interests ----------------


@router.post("/interests/import")
async def import_interests(
    files: list[UploadFile] = File(...),
    partition: Literal["current", "demo"] = "current",
    db: Session = Depends(get_db),
):
    """Upload the Instagram data download (.zip) or individual JSON files from it. Nothing is fetched online."""
    demo = _partition(db, partition)
    blobs: list[tuple[str, bytes]] = []
    total = 0
    for f in files[:40]:
        raw = await f.read(MAX_UPLOAD + 1)
        total += len(raw)
        if total > MAX_UPLOAD:
            raise HTTPException(413, "Upload is larger than 300 MB. Upload just the JSON files you need.")
        blobs.append((f.filename or "upload.json", raw))
    res = ints.import_files(db, blobs, demo)
    res["partition"] = "demo" if demo else "live"
    return res


class ManualInterest(BaseModel):
    url: str | None = Field(default=None, max_length=1000)
    note: str = Field(min_length=1, max_length=500)
    creator: str | None = Field(default=None, max_length=120)

    @field_validator("url")
    @classmethod
    def _url(cls, v: str | None) -> str | None:
        v = (v or "").strip() or None
        if v and not v.startswith(("https://www.instagram.com/", "https://instagram.com/")):
            raise ValueError("paste an instagram.com link (it is stored, never opened)")
        return v


@router.post("/interests/manual", status_code=201)
def add_manual(body: ManualInterest, db: Session = Depends(get_db)):
    row = ints.add_manual(db, body.url, body.note.strip(), body.creator, q.use_demo(db))
    return {"id": row.id, "creator": row.creator}


@router.get("/interests/profile")
def interests_profile(db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    return {**ints.profile(db, demo), "mode": "demo" if demo else q.data_mode(db)}


@router.get("/interests/items")
def interest_items(
    source: str | None = None, limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)
):
    stmt = select(InterestItem).where(InterestItem.is_demo.is_(q.use_demo(db)))
    if source:
        stmt = stmt.where(InterestItem.source == source)
    rows = db.scalars(stmt.order_by(InterestItem.happened_at.desc().nulls_last()).limit(limit))
    return [
        {
            "id": r.id,
            "source": r.source,
            "creator": r.creator,
            "url": r.url,
            "note": r.note,
            "collection": r.collection,
            "happened_at": iso_utc(r.happened_at),
        }
        for r in rows
    ]


@router.delete("/interests/items/{item_id}", status_code=204)
def delete_interest(item_id: int, db: Session = Depends(get_db)):
    row = db.get(InterestItem, item_id)
    if row is None or row.is_demo != q.use_demo(db):
        raise HTTPException(404, "item not found")
    db.delete(row)


# ---------------- recommendations ----------------


def _aware(dt: datetime | None) -> datetime | None:
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _history(db: Session, demo: bool, limit: int = 200) -> list[Recommendation]:
    return list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.is_demo.is_(demo))
            .order_by(Recommendation.created_at.desc())
            .limit(limit)
        )
    )


def _rec_out(r: Recommendation) -> dict:
    return {
        "id": r.id,
        **r.payload,
        "topic": r.topic,
        "category": r.category,
        "feedback": r.feedback,
        "feedback_at": iso_utc(r.feedback_at),
        "idea_id": r.idea_id or r.payload.get("idea_id"),
        "created_at": iso_utc(r.created_at),
    }


@router.get("/recommendations/next")
def next_reel(k: int = Query(default=3, ge=1, le=6), db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    acct = q.account(db, demo)
    online: dict[str, int] = {}
    if acct is not None:
        snap = db.scalar(
            select(AudienceSnapshot)
            .where(AudienceSnapshot.account_id == acct.id, AudienceSnapshot.kind == "online_hours")
            .order_by(AudienceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        online = snap.data if snap else {}
    posts = _posts(db)
    ideas = [
        {**_idea_dict(i), "pillar": i.pillar}
        for i in db.scalars(select(ContentIdea).where(ContentIdea.is_demo.is_(demo)))
    ]
    hist = _history(db, demo)
    res = recommend.recommend(
        posts,
        ints.profile(db, demo),
        ideas,
        growth.opportunity_gaps(_own_comments(db), _candidates(db)),
        growth.posting_windows(posts, online),
        act.audience_view(db, acct.id if acct else None),
        [
            {
                "topic": h.topic,
                "category": h.category,
                "feedback": h.feedback,
                "feedback_at": _aware(h.feedback_at),
            }
            for h in hist
        ],
        k,
    )
    # Persist what was shown. Re-use today's open row for the same data pick so reloads don't pile up history
    # (rows written by the AI layer keep the data's topic in payload["data_topic"]).
    today_open = {
        str(h.payload.get("data_topic") or h.topic).lower(): h
        for h in hist
        if h.feedback is None and (ca := _aware(h.created_at)) is not None and ca.date() == utcnow().date()
    }
    items = res["items"]
    cached = [today_open.get(it["topic"].lower()) for it in items]
    written_by = "data"
    if items and all(c is not None and c.payload.get("written_by") for c in cached):
        first = cached[0]
        assert first is not None
        written_by = str(first.payload["written_by"])  # today's AI write-up exists: no new model call
    elif get_settings().agent_mode in MODEL_MODES:
        top = sorted((p for p in posts if p.get("views")), key=lambda p: -(p.get("views") or 0))[:5]
        items, written_by = recommend.ai_enhance(items, top, ints.profile(db, demo))
    out = []
    for item in items:
        key = str(item.get("data_topic") or item["topic"]).lower()
        row = today_open.get(key)
        if row is not None and row.payload.get("written_by") and not item.get("written_by"):
            out.append(_rec_out(row))  # cached AI version
            continue
        payload = {k_: v for k_, v in item.items() if k_ not in ("topic", "category")}
        if row is None:
            row = Recommendation(
                topic=item["topic"][:200], category=item["category"], payload=payload, is_demo=demo
            )
            db.add(row)
        else:
            row.topic = item["topic"][:200]
            row.payload = payload
        db.flush()
        out.append(_rec_out(row))
    return {
        **res,
        "items": out,
        "written_by": written_by,
        "mode": "demo" if demo else q.data_mode(db),
    }


class Feedback(BaseModel):
    verdict: Literal["made_it", "not_for_me", "clear"]


@router.post("/recommendations/{rec_id}/feedback")
def rec_feedback(rec_id: int, body: Feedback, db: Session = Depends(get_db)):
    r = db.get(Recommendation, rec_id)
    if r is None or r.is_demo != q.use_demo(db):
        raise HTTPException(404, "recommendation not found")
    r.feedback = None if body.verdict == "clear" else body.verdict
    r.feedback_at = None if body.verdict == "clear" else utcnow()
    db.flush()
    return _rec_out(r)


@router.post("/recommendations/{rec_id}/save", status_code=201)
def rec_save(rec_id: int, db: Session = Depends(get_db)):
    """Save a suggestion to Ideas (or return the idea it already points to)."""
    r = db.get(Recommendation, rec_id)
    if r is None or r.is_demo != q.use_demo(db):
        raise HTTPException(404, "recommendation not found")
    existing = r.idea_id or r.payload.get("idea_id")
    if existing and db.get(ContentIdea, existing):
        return {"idea_id": existing, "created": False}
    hook = (r.payload.get("hook") or {}).get("text")
    why = "\n".join(f"- {x['text']} ({x['source_label']})" for x in r.payload.get("reasons", []))
    idea = ContentIdea(
        title=r.topic,
        pillar=r.category,
        recommended_hook=hook,
        hook_options=[hook] if hook else [],
        notes=f"Why this was suggested:\n{why}" if why else None,
        audience=(r.payload.get("for_who") or {}).get("segment"),
        status="idea",
        is_demo=r.is_demo,
    )
    db.add(idea)
    db.flush()
    r.idea_id = idea.id
    return {"idea_id": idea.id, "created": True}


@router.get("/recommendations/history")
def rec_history(db: Session = Depends(get_db)):
    return [_rec_out(r) for r in _history(db, q.use_demo(db), 50)]


# ---------------- ideas: bulk ----------------


class BulkIdeas(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=500)
    action: Literal["delete", "archive", "move", "restore"]
    status: Literal[CONTENT_STATUSES] | None = None  # type: ignore[valid-type]


@router.post("/ideas/bulk")
def bulk_ideas(body: BulkIdeas, db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    rows = db.scalars(
        select(ContentIdea).where(ContentIdea.id.in_(body.ids), ContentIdea.is_demo.is_(demo))
    ).all()
    if body.action == "delete":
        db.execute(delete(ContentIdea).where(ContentIdea.id.in_([r.id for r in rows])))
    elif body.action == "move":
        if body.status is None:
            raise HTTPException(422, "status is required to move ideas")
        for r in rows:
            r.status = body.status
    else:
        for r in rows:
            r.status = "archived" if body.action == "archive" else "idea"
    db.flush()
    return {"ok": True, "affected": len(rows)}
