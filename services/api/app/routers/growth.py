"""Growth features computed from the account's own data: audience segments, shareability, fatigue, comment
gaps, brand voice, reel scripts, posting windows and the daily shortlist. Read-only except saving ideas and the
voice profile; nothing here posts to Instagram."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AUDIENCE_SEGMENTS, CATEGORIES, FORMATS, AudienceSnapshot, Comment, ContentIdea, Media
from ..services import creator, growth
from ..services import queries as q
from .creator import _candidates, _idea_dict, _posts

router = APIRouter()

VOICE_KEY = "voice_profile"


@router.get("/growth/segments")
def segments(db: Session = Depends(get_db)):
    return growth.segment_performance(_posts(db))


@router.get("/growth/fatigue")
def content_fatigue(window: int = 6, db: Session = Depends(get_db)):
    return growth.fatigue(_posts(db), max(4, min(window, 20)))


def _own_comments(db: Session) -> list[dict]:
    demo = q.use_demo(db)
    acct = q.account(db, demo)
    if acct is None:
        return []
    rows = db.scalars(
        select(Comment)
        .join(Media, Comment.media_id == Media.id)
        .where(Media.account_id == acct.id, Comment.is_demo.is_(demo), Comment.hidden.is_(False))
    )
    return [
        {
            "id": c.id,
            "text": c.text,
            "intent": c.intent,
            "username": c.username,
            "like_count": c.like_count,
            "idea_id": c.idea_id,
        }
        for c in rows
    ]


@router.get("/growth/gaps")
def gaps(db: Session = Depends(get_db)):
    return growth.opportunity_gaps(_own_comments(db), _candidates(db))


class GapIdea(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    comment_ids: list[int] = Field(default=[], max_length=50)


@router.post("/growth/gaps/to-idea", status_code=201)
def gap_to_idea(body: GapIdea, db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    comments = (
        db.scalars(select(Comment).where(Comment.id.in_(body.comment_ids), Comment.is_demo.is_(demo))).all()
        if body.comment_ids
        else []
    )
    idea = ContentIdea(
        title=body.title,
        status="idea",
        is_demo=demo,
        hook_options=[],
        evidence=[f"Comment by @{c.username}: {c.text}" for c in comments],
        hypothesis=f"{len(comments)} viewer(s) asked for this in your comments and no post covers it yet.",
    )
    idea.audience = growth.infer_audience(body.title)["audience"]
    db.add(idea)
    db.flush()
    for c in comments:
        c.idea_id = c.idea_id or idea.id
    return {"id": idea.id, "status": idea.status}


@router.get("/growth/schedule")
def schedule(db: Session = Depends(get_db)):
    acct = q.account(db, q.use_demo(db))
    online: dict[str, int] = {}
    if acct is not None:
        snap = db.scalar(
            select(AudienceSnapshot)
            .where(AudienceSnapshot.account_id == acct.id, AudienceSnapshot.kind == "online_hours")
            .order_by(AudienceSnapshot.snapshot_date.desc())
            .limit(1)
        )
        online = snap.data if snap else {}
    return growth.posting_windows(_posts(db), online)


@router.get("/growth/briefing")
def briefing(db: Session = Depends(get_db)):
    ideas = db.scalars(
        select(ContentIdea).where(ContentIdea.is_demo.is_(q.use_demo(db)), ContentIdea.status != "archived")
    ).all()
    return growth.shortlist([_idea_dict(i) for i in ideas], _posts(db))


class AudienceReq(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    category: str | None = None


@router.post("/growth/infer-audience")
def infer(body: AudienceReq):
    return growth.infer_audience(body.text, body.category)


class ShareReq(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    category: Literal[CATEGORIES] | None = None  # type: ignore[valid-type]
    format: Literal[FORMATS] | None = None  # type: ignore[valid-type]


@router.post("/create/shareability")
def share_score(body: ShareReq, db: Session = Depends(get_db)):
    res = growth.shareability(body.text, body.category, body.format, _posts(db))
    return {**res, "audience": growth.infer_audience(body.text, body.category)}


class ScriptReq(BaseModel):
    topic: str = Field(min_length=2, max_length=200)
    audience: Literal["beginner", "developer"] = "beginner"
    hook: str | None = Field(default=None, max_length=300)
    duration: Literal[15, 30, 45, 60] = 30
    category: Literal[CATEGORIES] = "tech_concepts"  # type: ignore[valid-type]


@router.post("/create/reel-script")
def create_reel_script(body: ScriptReq):
    res, src = creator.generate_with_model(
        "Write a full Reel script: hook, beats with start/end seconds covering the whole duration, each with "
        "voiceover, on_screen (<=5 words), visual (b-roll / shot instruction); then caption and shot_list. "
        "Plain spoken English, no em dashes.",
        body.model_dump(),
        growth.ReelScript,
        lambda: growth.reel_script(body.topic, body.audience, body.hook, body.duration, body.category),
    )
    return {"source": src, **res.model_dump()}


class VoiceIn(BaseModel):
    tone_words: list[str] = Field(default=[], max_length=8)
    banned_words: list[str] = Field(default=[], max_length=40)
    preferred_cta: str | None = Field(default=None, max_length=120)
    signature_hashtags: list[str] = Field(default=[], max_length=5)
    emoji_level: Literal["none", "low", "medium", "high"] = "low"

    @field_validator("signature_hashtags")
    @classmethod
    def _tags(cls, v: list[str]) -> list[str]:
        return [t if t.startswith("#") else f"#{t}" for t in (x.strip().replace(" ", "") for x in v) if t]

    @field_validator("tone_words", "banned_words")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        return [x.strip() for x in v if x.strip()]


@router.get("/voice")
def get_voice(db: Session = Depends(get_db)):
    return growth.voice_profile(q.get_setting(db, VOICE_KEY))


@router.put("/voice")
def put_voice(body: VoiceIn, db: Session = Depends(get_db)):
    q.set_setting(db, VOICE_KEY, body.model_dump())
    return growth.voice_profile(body.model_dump())


class LintReq(BaseModel):
    text: str = Field(min_length=1, max_length=5000)


@router.post("/create/voice-check")
def voice_check(body: LintReq, db: Session = Depends(get_db)):
    return growth.lint_voice(body.text, q.get_setting(db, VOICE_KEY) or {})


@router.get("/growth/audiences")
def audiences():
    return {"audiences": [{"value": a, "label": growth.SEGMENT_LABEL[a]} for a in AUDIENCE_SEGMENTS]}
