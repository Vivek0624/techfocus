"""Activity (comments inbox, mentions) and Audience."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..instagram import service as igs
from ..instagram.client import InstagramAPIError
from ..models import Comment, ContentIdea, ExternalWriteAudit, Media, Mention, iso_utc
from ..security import get_cipher
from ..services import activity as act
from ..services import queries as q

router = APIRouter()

Filter = Literal["needs_reply", "questions", "requests", "all", "hidden"]


def _scope(db: Session):
    """Comments belong to the current data partition via their media's account."""
    demo = q.use_demo(db)
    acct = q.account(db, demo)
    return demo, acct


def _comment_out(c: Comment, title: str | None) -> dict:
    return {
        "id": c.id,
        "username": c.username,
        "text": c.text,
        "intent": c.intent,
        "draft_reply": c.draft_reply,
        "replied": c.replied,
        "reply_text": c.reply_text,
        "hidden": c.hidden,
        "done": c.done,
        "like_count": c.like_count,
        "commented_at": iso_utc(c.commented_at),
        "media_id": c.media_id,
        "post_title": title,
        "idea_id": c.idea_id,
        "source": c.source,
        "parent_ig_id": c.parent_ig_id,
        "from_owner": c.from_owner,
    }


@router.get("/comments")
def list_comments(filter: Filter = "needs_reply", db: Session = Depends(get_db)):
    demo, acct = _scope(db)
    if acct is None:
        return {"items": [], "counts": {}, "available": False}
    base = (
        select(Comment, Media.caption)
        .join(Media, Comment.media_id == Media.id)
        .where(Media.account_id == acct.id, Comment.is_demo.is_(demo))
    )
    stmt = base
    if filter == "needs_reply":
        stmt = stmt.where(
            Comment.replied.is_(False),
            Comment.done.is_(False),
            Comment.hidden.is_(False),
            Comment.intent.in_(["question", "request", "feedback"]),
        )
    elif filter == "questions":
        stmt = stmt.where(Comment.intent == "question", Comment.hidden.is_(False))
    elif filter == "requests":
        stmt = stmt.where(Comment.intent == "request", Comment.hidden.is_(False))
    elif filter == "hidden":
        stmt = stmt.where(Comment.hidden.is_(True))
    if filter != "hidden":
        stmt = stmt.where(Comment.parent_ig_id.is_(None))  # replies are shown inside their thread
    rows = db.execute(stmt.order_by(Comment.commented_at.desc()).limit(200)).all()
    parents = [c.ig_comment_id for c, _ in rows]
    thread: dict[str, list[dict]] = {}
    if parents:
        for r in db.scalars(
            select(Comment).where(Comment.parent_ig_id.in_(parents)).order_by(Comment.commented_at)
        ):
            thread.setdefault(r.parent_ig_id or "", []).append(_comment_out(r, None))
    counts = dict(
        db.execute(
            select(Comment.intent, func.count())
            .join(Media, Comment.media_id == Media.id)
            .where(Media.account_id == acct.id, Comment.is_demo.is_(demo), Comment.hidden.is_(False))
            .group_by(Comment.intent)
        ).all()
    )
    needs = db.scalar(
        select(func.count())
        .select_from(Comment)
        .join(Media, Comment.media_id == Media.id)
        .where(
            Media.account_id == acct.id,
            Comment.is_demo.is_(demo),
            Comment.replied.is_(False),
            Comment.done.is_(False),
            Comment.hidden.is_(False),
            Comment.intent.in_(["question", "request", "feedback"]),
        )
    )
    return {
        "available": True,
        "items": [
            {**_comment_out(c, (cap or "").split("\n")[0][:80]), "replies": thread.get(c.ig_comment_id, [])}
            for c, cap in rows
        ],
        "counts": {**counts, "needs_reply": needs or 0},
        "note": "Replies are sent only when you press Send. Nothing is posted automatically.",
    }


def _get(db: Session, cid: int) -> Comment:
    c = db.get(Comment, cid)
    if c is None or c.is_demo != q.use_demo(db):
        raise HTTPException(404, "comment not found")
    return c


def _live_client(request: Request, db: Session):
    acct = igs.live_account(db)
    if acct is None or acct.token is None:
        raise HTTPException(409, "Instagram is not connected")
    if "instagram_business_manage_comments" not in (acct.granted_scopes or []):
        raise HTTPException(
            403,
            "Comment permission (instagram_business_manage_comments) was not granted. "
            "Reconnect and allow it.",
        )
    tok = get_cipher().decrypt(acct.token.ciphertext)
    return request.app.state.instagram_client_factory(tok, acct.ig_user_id)


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=2200)


@router.post("/comments/{cid}/reply")
def reply(cid: int, body: ReplyIn, request: Request, db: Session = Depends(get_db)):
    """User-initiated: the click on Send is the approval. Audited."""
    c = _get(db, cid)
    if c.replied:
        raise HTTPException(409, "already replied")
    if c.is_demo:
        c.replied, c.reply_text = True, body.text
        return {
            "ok": True,
            "simulated": True,
            "note": "Demo comment: reply saved locally, nothing was posted.",
        }
    client = _live_client(request, db)
    try:
        reply_id = client.reply_to_comment(c.ig_comment_id, body.text)
        ok, err = True, None
    except InstagramAPIError as e:
        reply_id, ok, err = None, False, str(e)
    db.add(
        ExternalWriteAudit(
            action="reply_comment",
            ok=ok,
            detail={"comment_id": c.ig_comment_id, "reply_id": reply_id, "error": err},
        )
    )
    if not ok:
        db.commit()
        raise HTTPException(502, f"Instagram refused the reply: {err}")
    c.replied, c.reply_text = True, body.text
    return {"ok": True, "reply_id": reply_id}


class HideIn(BaseModel):
    hide: bool = True


@router.post("/comments/{cid}/hide")
def hide(cid: int, body: HideIn, request: Request, db: Session = Depends(get_db)):
    c = _get(db, cid)
    if not c.is_demo:
        client = _live_client(request, db)
        try:
            client.hide_comment(c.ig_comment_id, body.hide)
        except InstagramAPIError as e:
            raise HTTPException(502, f"Instagram refused: {e}") from e
        db.add(
            ExternalWriteAudit(
                action="hide_comment" if body.hide else "unhide_comment",
                ok=True,
                detail={"comment_id": c.ig_comment_id},
            )
        )
    c.hidden = body.hide
    return {"ok": True, "hidden": c.hidden, "simulated": c.is_demo}


@router.post("/comments/{cid}/done")
def mark_done(cid: int, db: Session = Depends(get_db)):
    c = _get(db, cid)
    c.done = True
    return {"ok": True}


@router.post("/comments/{cid}/to-idea", status_code=201)
def to_idea(cid: int, db: Session = Depends(get_db)):
    """Audience questions are the best idea source a small account has."""
    c = _get(db, cid)
    if c.idea_id:
        return {"id": c.idea_id, "existing": True}
    idea = ContentIdea(
        title=act.idea_title_from(c.text),
        status="idea",
        is_demo=c.is_demo,
        hook_options=[],
        evidence=[f"Comment by @{c.username}: {c.text}"],
        hypothesis="Someone asked for this directly, so at least one viewer wants it.",
    )
    db.add(idea)
    db.flush()
    c.idea_id = idea.id
    return {"id": idea.id, "existing": False}


@router.get("/mentions")
def mentions(db: Session = Depends(get_db)):
    demo = q.use_demo(db)
    rows = db.scalars(
        select(Mention).where(Mention.is_demo.is_(demo)).order_by(Mention.posted_at.desc()).limit(50)
    )
    return {
        "items": [
            {
                "id": m.id,
                "username": m.username,
                "caption": m.caption,
                "permalink": m.permalink,
                "posted_at": iso_utc(m.posted_at),
                "source": m.source,
            }
            for m in rows
        ]
    }


@router.get("/audience")
def audience(db: Session = Depends(get_db)):
    acct = q.account(db, q.use_demo(db))
    return act.audience_view(db, acct.id if acct else None)


@router.post("/activity/sync")
def sync(request: Request, db: Session = Depends(get_db)):
    acct = igs.live_account(db)
    if acct is None or acct.token is None:
        raise HTTPException(409, "Instagram is not connected")
    tok = get_cipher().decrypt(acct.token.ciphertext)
    client = request.app.state.instagram_client_factory(tok, acct.ig_user_id)
    return act.sync_activity(db, acct, client)
