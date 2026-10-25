"""Account connection, token lifecycle, sync and approval-gated publishing."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..models import (
    SOURCE_API,
    AccountSnapshot,
    ApprovalRequest,
    CalendarItem,
    ExternalWriteAudit,
    InstagramAccount,
    InstagramToken,
    Media,
    MediaSnapshot,
    PublishingJob,
    utcnow,
)
from ..security import TokenCipher
from . import client as ig

log = logging.getLogger(__name__)

ClientFactory = Callable[[str, str], ig.InstagramClientProto]


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def live_account(db: Session) -> InstagramAccount | None:
    """The connected real account that holds an OAuth token (manual-only accounts have none)."""
    return db.scalar(
        select(InstagramAccount)
        .join(InstagramToken)
        .where(InstagramAccount.is_demo.is_(False), InstagramAccount.connected.is_(True))
    )


def store_connection(db: Session, cipher: TokenCipher, token: dict, profile: dict) -> InstagramAccount:
    uid = str(profile.get("user_id") or profile.get("id") or token["user_id"])
    acct = db.scalar(select(InstagramAccount).where(InstagramAccount.ig_user_id == uid))
    if acct is None:
        acct = InstagramAccount(ig_user_id=uid, username=profile.get("username", ""), is_demo=False)
        db.add(acct)
    acct.username = profile.get("username", acct.username)
    acct.account_type = profile.get("account_type")
    acct.connected = True
    acct.granted_scopes = list(token.get("permissions") or [])
    acct.last_error = None
    db.flush()
    enc = cipher.encrypt(token["access_token"])
    if acct.token is None:
        acct.token = InstagramToken(ciphertext=enc, expires_at=token["expires_at"])
    else:
        acct.token.ciphertext, acct.token.expires_at, acct.token.issued_at = (
            enc,
            token["expires_at"],
            utcnow(),
        )
    db.flush()
    return acct


def disconnect(db: Session, acct: InstagramAccount) -> None:
    acct.connected = False
    if acct.token is not None:
        db.delete(acct.token)
    db.flush()


def token_status(acct: InstagramAccount | None) -> dict:
    if acct is None or acct.token is None:
        return {"state": "missing"}
    exp = _aware(acct.token.expires_at)
    now = datetime.now(UTC)
    if exp and exp <= now:
        return {"state": "expired", "expires_at": exp}
    issued = _aware(acct.token.issued_at) or now
    refreshable = now - issued >= timedelta(hours=24)
    soon = bool(exp and exp - now < timedelta(days=10))
    return {"state": "expiring_soon" if soon else "valid", "expires_at": exp, "refreshable": refreshable}


def maybe_refresh(db: Session, s: Settings, cipher: TokenCipher, acct: InstagramAccount) -> None:
    st = token_status(acct)
    if st["state"] == "expiring_soon" and st.get("refreshable") and acct.token:
        new = ig.refresh_token(s, cipher.decrypt(acct.token.ciphertext))
        acct.token.ciphertext = cipher.encrypt(new["access_token"])
        acct.token.expires_at, acct.token.issued_at = new["expires_at"], utcnow()
        db.flush()


REQUIRED_SCOPES = {
    "instagram_business_basic": "profile and media list",
    "instagram_business_manage_insights": "account and media insights",
    "instagram_business_content_publish": "approved publishing",
    "instagram_business_manage_comments": "reading comments for audience questions",
}


def permission_diagnostics(acct: InstagramAccount | None) -> list[dict]:
    granted = set(acct.granted_scopes if acct else [])
    return [{"scope": k, "purpose": v, "granted": k in granted} for k, v in REQUIRED_SCOPES.items()]


def sync_account(
    db: Session,
    acct: InstagramAccount,
    c: ig.InstagramClientProto,
    media_limit: int = 50,
    today: date | None = None,
) -> dict:
    """Idempotent: one snapshot per account per day, one per media per day."""
    today = today or date.today()
    prof = c.get_profile()
    acct.username = prof.get("username", acct.username)
    acct.account_type = prof.get("account_type", acct.account_type)
    if acct.account_type and acct.account_type.upper() not in ("BUSINESS", "MEDIA_CREATOR", "CREATOR"):
        raise HTTPException(
            409,
            "This Instagram account is personal. Switch it to a Creator or Business "
            "(professional) account in the Instagram app, then reconnect.",
        )
    until = datetime.combine(today, datetime.min.time(), tzinfo=UTC)
    since = until - timedelta(days=1)
    try:
        ins = c.account_insights(since, until)
    except ig.InstagramAPIError as e:
        log.warning("account insights unavailable: %s", e)
        ins = {}
    fu = c.follows_and_unfollows(since, until)
    snap = db.scalar(
        select(AccountSnapshot).where(
            AccountSnapshot.account_id == acct.id,
            AccountSnapshot.snapshot_date == today,
            AccountSnapshot.source == SOURCE_API,
        )
    )
    if snap is None:
        snap = AccountSnapshot(account_id=acct.id, snapshot_date=today, source=SOURCE_API)
        db.add(snap)
    snap.followers = prof.get("followers_count")
    snap.follows, snap.unfollows = fu.get("follows"), fu.get("unfollows")
    for k in (
        "reach",
        "views",
        "accounts_engaged",
        "total_interactions",
        "likes",
        "comments",
        "shares",
        "saves",
        "profile_links_taps",
    ):
        setattr(snap, k, ins.get(k))
    snap.fetched_at = utcnow()

    n_media = 0
    for m in c.iter_media(media_limit):
        row = db.scalar(select(Media).where(Media.ig_media_id == m["id"]))
        if row is None:
            row = Media(account_id=acct.id, ig_media_id=m["id"], source=SOURCE_API)
            db.add(row)
        row.caption = m.get("caption")
        row.media_type = m.get("media_type")
        row.media_product_type = m.get("media_product_type")
        row.permalink = m.get("permalink")
        if m.get("timestamp"):
            row.published_at = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        db.flush()
        try:
            mi = c.media_insights(m["id"], m.get("media_product_type"))
        except ig.InstagramAPIError as e:
            log.warning("media insights unavailable for %s: %s", m["id"], e)
            mi = {}
        ms = db.scalar(
            select(MediaSnapshot).where(
                MediaSnapshot.media_id == row.id, MediaSnapshot.snapshot_date == today
            )
        )
        if ms is None:
            ms = MediaSnapshot(media_id=row.id, snapshot_date=today, source=SOURCE_API)
            db.add(ms)
        for k in (
            "views",
            "reach",
            "likes",
            "comments",
            "shares",
            "saved",
            "total_interactions",
            "follows",
            "profile_visits",
            "profile_activity",
            "reposts",
        ):
            setattr(ms, k, mi.get(k))
        ms.avg_watch_time_ms = mi.get("ig_reels_avg_watch_time")
        ms.total_watch_time_ms = mi.get("ig_reels_video_view_total_time")
        ms.fetched_at = utcnow()
        n_media += 1
    acct.last_sync_at = utcnow()
    acct.last_error = None
    db.flush()
    return {"followers": snap.followers, "media_synced": n_media, "snapshot_date": today.isoformat()}


# ---------------- publishing ----------------


def request_publish_approval(db: Session, item: CalendarItem) -> ApprovalRequest:
    problems = validate_for_publish(item)
    if problems:
        raise HTTPException(422, {"message": "Not ready to publish", "problems": problems})
    existing = db.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.target_type == "calendar_item",
            ApprovalRequest.target_id == item.id,
            ApprovalRequest.status == "pending",
        )
    )
    if existing:
        return existing
    ap = ApprovalRequest(
        action="publish_media",
        target_type="calendar_item",
        target_id=item.id,
        summary=f"Publish {publish_kind(item)} '{item.title}' at {item.scheduled_at.isoformat()}",
        payload={"caption": item.caption, "video_url": item.asset_ref, "kind": publish_kind(item)},
    )
    db.add(ap)
    db.flush()
    return ap


IMAGE_EXT = (".jpg", ".jpeg")
VIDEO_EXT = (".mp4", ".mov")


def publish_kind(item: CalendarItem) -> str:
    """reel | image | carousel. Carousels are calendar items with format 'carousel' and 2-10 URLs."""
    if item.format == "carousel":
        return "carousel"
    urls = asset_urls(item)
    if item.format == "image" or (len(urls) == 1 and _path(urls[0]).endswith(IMAGE_EXT)):
        return "image"
    return "reel"


def asset_urls(item: CalendarItem) -> list[str]:
    raw = (item.asset_ref or "").replace(",", "\n")
    return [u.strip() for u in raw.splitlines() if u.strip()]


def _path(url: str) -> str:
    return url.split("?", 1)[0].lower()


def validate_for_publish(item: CalendarItem) -> list[str]:
    p = []
    if not item.caption or not item.caption.strip():
        p.append("caption is empty")
    elif len(item.caption) > 2200:
        p.append("caption exceeds 2,200 characters")
    elif item.caption.count("#") > 30:
        p.append("more than 30 hashtags")
    kind = publish_kind(item)
    urls = asset_urls(item)
    if not urls:
        p.append("no media attached" if kind != "reel" else "no video asset attached")
    elif any(not u.startswith("https://") for u in urls):
        p.append(
            "media must be at a public https URL (Instagram downloads it from there). Local files cannot be "
            "published; upload to S3 or another public host first."
        )
    elif kind == "carousel":
        if not 2 <= len(urls) <= 10:
            p.append("a carousel needs 2 to 10 images or videos (one URL per line)")
        bad = [u for u in urls if not _path(u).endswith(IMAGE_EXT + VIDEO_EXT)]
        if bad:
            p.append("carousel items must be .jpg/.jpeg images or .mp4/.mov videos")
    elif kind == "image" and not _path(urls[0]).endswith(IMAGE_EXT):
        p.append("Instagram only accepts JPEG images for image posts (.jpg/.jpeg)")
    elif kind == "reel" and len(urls) > 1:
        p.append("a reel takes one video URL; set the format to carousel for several items")
    if item.is_demo:
        p.append("demo items cannot be published")
    return p


def execute_publish(
    db: Session,
    approval: ApprovalRequest,
    c: ig.InstagramClientProto,
    poll: Callable[[], None] = lambda: None,
    max_polls: int = 5,
) -> PublishingJob:
    """The approval check lives here, in the backend, not in any prompt."""
    if approval.action != "publish_media" or approval.status != "approved":
        raise HTTPException(403, "publishing requires an approved approval request")
    item = db.get(CalendarItem, approval.target_id)
    if item is None:
        raise HTTPException(404, "calendar item not found")
    if db.scalar(select(PublishingJob).where(PublishingJob.calendar_item_id == item.id)):
        raise HTTPException(409, "this item already has a publishing job")
    problems = validate_for_publish(item)
    if problems:
        raise HTTPException(422, {"message": "Not ready to publish", "problems": problems})
    job = PublishingJob(calendar_item_id=item.id, approval_id=approval.id, status="creating")
    db.add(job)
    db.flush()
    try:
        assert item.asset_ref and item.caption
        kind, urls = publish_kind(item), asset_urls(item)
        if kind == "image":
            job.container_id = c.create_image_container(urls[0], item.caption)
        elif kind == "carousel":
            children = [
                c.create_image_container(u, None, carousel_item=True)
                if _path(u).endswith(IMAGE_EXT)
                else c.create_video_item_container(u)
                for u in urls
            ]
            job.container_id = c.create_carousel_container(children, item.caption)
        else:
            job.container_id = c.create_reel_container(urls[0], item.caption)
        status = "IN_PROGRESS"
        for _ in range(max_polls):
            status = c.container_status(job.container_id)
            if status in ("FINISHED", "ERROR", "EXPIRED"):
                break
            poll()
        if status != "FINISHED":
            raise ig.InstagramAPIError(f"container status {status}")
        job.media_id = c.publish_container(job.container_id)
        job.status = "published"
        item.publishing_status, item.published_media_id, item.published_at = (
            "published",
            job.media_id,
            utcnow(),
        )
        ok, err = True, None
    except (ig.InstagramAPIError, AssertionError) as e:
        job.status, job.error = "failed", str(e)
        item.publishing_status = "failed"
        ok, err = False, str(e)
    db.add(
        ExternalWriteAudit(
            action="publish_media",
            approval_id=approval.id,
            ok=ok,
            detail={
                "calendar_item_id": item.id,
                "container_id": job.container_id,
                "media_id": job.media_id,
                "error": err,
            },
        )
    )
    db.flush()
    return job
