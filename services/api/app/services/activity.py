"""Activity: comment inbox, mentions, audience. Reading is automatic; replying or hiding happens only when
the user clicks Send/Hide (that click is the approval), and every such write is audited."""

from __future__ import annotations

import logging
import re
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..instagram.client import InstagramAPIError, InstagramClientProto
from ..models import (
    SOURCE_API,
    AudienceSnapshot,
    Comment,
    InstagramAccount,
    Media,
    Mention,
)
from .analytics import IST

log = logging.getLogger(__name__)

_Q = re.compile(
    r"\?|^(how|what|why|when|where|which|who|can|could|should|is|are|do|does|kya|kaise|kaun|kab)\b", re.I
)
_REQ = re.compile(
    r"\b(make|do|please|plz|pls)\b.{0,30}\b(video|reel|post|part 2|on|about)\b|\bpart\s*2\b|"
    r"\b(explain|cover|topic)\b",
    re.I,
)
_SPAM = re.compile(
    r"https?://|\bdm (me|us)\b|\bpromo(te|tion)?\b|\bcollab\b.*\b(price|paid)\b|\bfollow back\b|"
    r"\bcheck (my|our) (page|profile)\b|\bearn \$|\bcrypto\b",
    re.I,
)
_PRAISE = re.compile(
    r"\b(great|awesome|amazing|love|helpful|thanks|thank you|superb|nice|best|🔥|❤️|👏|op)\b", re.I
)
_NEG = re.compile(r"\b(wrong|incorrect|misleading|bad|cringe|useless|not true)\b", re.I)


def classify(text: str) -> str:
    t = text.strip()
    if _SPAM.search(t):
        return "spam"
    if _REQ.search(t):
        return "request"
    if _Q.search(t):
        return "question"
    if _NEG.search(t):
        return "feedback"
    if _PRAISE.search(t):
        return "praise"
    return "other"


def draft_reply(text: str, intent: str, username: str | None = None) -> str | None:
    """Short, human, no emojis spam. The user edits before sending."""
    name = f"@{username} " if username else ""
    t = text.strip().rstrip("?!. ")
    if intent == "question":
        return f"{name}Good question. Short answer: [your answer]. I'll do a full reel on this soon, follow so you don't miss it."
    if intent == "request":
        return f"{name}Noted! Adding this to my list. Which part should I focus on first?"
    if intent == "praise":
        return f"{name}Thank you, glad it helped! What should I explain next?"
    if intent == "feedback":
        return f"{name}Thanks for pointing that out. Which part felt off? I'll correct it in a follow-up."
    if intent == "other" and len(t) > 3:
        return f"{name}Thanks for watching!"
    return None  # spam: hide, don't reply


def idea_title_from(text: str) -> str:
    t = re.sub(r"\s+", " ", text).strip()
    t = re.sub(r"^(bro|sir|bhai|hey|hi|hello)[ ,]+", "", t, flags=re.I)
    return (t[:1].upper() + t[1:])[:120].rstrip("?") + (" (from comments)" if len(t) < 100 else "")


def _upsert_comment(db: Session, raw: dict, media_id: int, parent: str | None, owner: str) -> Comment | None:
    if not raw.get("id"):
        return None
    row = db.scalar(select(Comment).where(Comment.ig_comment_id == raw["id"]))
    from_owner = bool(owner) and (raw.get("username") or "").lower() == owner
    if row is None:
        intent = "other" if from_owner else classify(raw.get("text", ""))
        row = Comment(
            ig_comment_id=raw["id"],
            media_id=media_id,
            username=raw.get("username"),
            text=raw.get("text", ""),
            intent=intent,
            source=SOURCE_API,
            parent_ig_id=parent,
            from_owner=from_owner,
            done=from_owner,
            draft_reply=None if from_owner else draft_reply(raw.get("text", ""), intent, raw.get("username")),
        )
        db.add(row)
    row.like_count = raw.get("like_count")
    if raw.get("hidden") is not None:
        row.hidden = bool(raw["hidden"])
    if raw.get("timestamp"):
        row.commented_at = datetime.strptime(raw["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
    return row


def sync_activity(
    db: Session, acct: InstagramAccount, c: InstagramClientProto, media_limit: int = 15
) -> dict:
    """Pull comments on recent media, mentions and audience. Each part fails independently."""
    res: dict = {"comments": 0, "mentions": 0, "audience": []}
    medias = db.scalars(
        select(Media)
        .where(Media.account_id == acct.id)
        .order_by(Media.published_at.desc())
        .limit(media_limit)
    ).all()
    owner = (acct.username or "").lower()
    res["replies"] = 0
    for m in medias:
        try:
            for raw in c.iter_comments(m.ig_media_id, 100):
                row = _upsert_comment(db, raw, m.id, None, owner)
                if row is None:
                    continue
                if row.id is None:
                    res["comments"] += 1
                db.flush()
                replies = getattr(c, "iter_replies", None)
                if replies is None:
                    continue
                try:
                    for rr in replies(raw["id"], 50):
                        child = _upsert_comment(db, rr, m.id, raw["id"], owner)
                        if child is not None and child.id is None:
                            res["replies"] += 1
                        if child is not None and child.from_owner:
                            row.replied = True
                            row.reply_text = row.reply_text or child.text
                except InstagramAPIError as e:
                    log.info("replies unavailable for %s: %s", raw["id"], e)
        except InstagramAPIError as e:
            log.warning("comments unavailable for %s: %s", m.ig_media_id, e)
            break  # usually a missing permission; stop hammering
    try:
        for t in c.iter_tags(50):
            if not db.scalar(select(Mention).where(Mention.ig_media_id == t["id"])):
                db.add(
                    Mention(
                        ig_media_id=t["id"],
                        username=t.get("username"),
                        caption=t.get("caption"),
                        permalink=t.get("permalink"),
                        source=SOURCE_API,
                        posted_at=datetime.strptime(t["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
                        if t.get("timestamp")
                        else None,
                    )
                )
                res["mentions"] += 1
    except InstagramAPIError as e:
        log.warning("mentions unavailable: %s", e)
    today = date.today()
    parts: list[tuple[str, object]] = [
        (f"followers_{b}", lambda b=b: c.demographics(b)) for b in ("age", "gender", "city", "country")
    ]
    parts.append(("online_hours", c.online_followers))
    for kind, fn in parts:
        try:
            data = fn()  # type: ignore[operator]
        except InstagramAPIError as e:
            log.info("audience %s unavailable: %s", kind, e)
            continue
        if not data:
            continue
        snap = db.scalar(
            select(AudienceSnapshot).where(
                AudienceSnapshot.account_id == acct.id,
                AudienceSnapshot.snapshot_date == today,
                AudienceSnapshot.kind == kind,
            )
        )
        if snap is None:
            snap = AudienceSnapshot(
                account_id=acct.id, snapshot_date=today, kind=kind, data=data, source=SOURCE_API
            )
            db.add(snap)
        snap.data = data
        res["audience"].append(kind)
    db.flush()
    return res


def best_hours_ist(online: dict[str, int], tz_offset_hours: float = 5.5, top: int = 3) -> list[dict]:
    """online_followers hours are in the account's time zone; Indian accounts are IST already. tz_offset is kept
    for clarity: pass 0 if the data is already IST."""
    if not online:
        return []
    total = max(sum(online.values()), 1)
    ranked = sorted(((int(h), v) for h, v in online.items()), key=lambda x: -x[1])[:top]
    return [
        {
            "hour": h,
            "label": datetime(2000, 1, 1, h).strftime("%-I %p"),
            "followers_online": v,
            "share": round(v / total * 100, 1),
        }
        for h, v in ranked
    ]


def audience_view(db: Session, account_id: int | None) -> dict:
    if account_id is None:
        return {"available": False}
    latest: dict[str, AudienceSnapshot] = {}
    for row in db.scalars(
        select(AudienceSnapshot)
        .where(AudienceSnapshot.account_id == account_id)
        .order_by(AudienceSnapshot.snapshot_date)
    ):
        latest[row.kind] = row

    def top(kind: str, n: int = 6) -> list[dict]:
        d = latest[kind].data if kind in latest else {}
        tot = max(sum(d.values()), 1)
        return [
            {"label": k, "value": v, "share": round(v / tot * 100, 1)}
            for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]
        ]

    online = latest["online_hours"].data if "online_hours" in latest else {}
    hours = [{"hour": h, "value": int(online.get(str(h), 0))} for h in range(24)] if online else []
    best = best_hours_ist(online, 0)
    any_row = next(iter(latest.values()), None)
    return {
        "available": bool(latest),
        "source": any_row.source if any_row else None,
        "fetched_at": any_row.fetched_at.replace(tzinfo=UTC).isoformat() if any_row else None,
        "age": top("followers_age", 7),
        "gender": top("followers_gender", 3),
        "cities": top("followers_city"),
        "countries": top("followers_country"),
        "most_active_hours": hours,
        "best_times": best,
        "recommendation": (
            f"Most of your followers are online around {best[0]['label']}. Post 30-60 minutes "
            "before that so the Reel is fresh when they open the app."
            if best
            else "Instagram shares this once you have 100+ followers. Until then, test 1 PM vs 8 PM IST."
        ),
        "note": "Instagram returns audience data only for accounts with 100+ followers, and only the top groups.",
    }


def _now_ist() -> datetime:
    return datetime.now(IST)
