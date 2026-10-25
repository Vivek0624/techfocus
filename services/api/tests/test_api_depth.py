from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.instagram import service as igs
from app.models import ApprovalRequest, CalendarItem, Comment, InstagramAccount, MediaSnapshot
from app.scheduler import auto_sync
from tests.test_instagram import _connect, _disconnect


def _item(**kw):
    base = dict(title="x", scheduled_at=datetime.now(UTC), caption="c")
    return CalendarItem(**{**base, **kw})


def test_publish_kinds_and_validation():
    assert igs.publish_kind(_item(asset_ref="https://h/v.mp4")) == "reel"
    assert igs.publish_kind(_item(asset_ref="https://h/p.jpg?x=1")) == "image"
    car = _item(format="carousel", asset_ref="https://h/1.jpg\nhttps://h/2.mp4")
    assert igs.publish_kind(car) == "carousel" and igs.validate_for_publish(car) == []
    one = _item(format="carousel", asset_ref="https://h/1.jpg")
    assert any("2 to 10" in p for p in igs.validate_for_publish(one))
    png = _item(format="image", asset_ref="https://h/p.png")
    assert any("JPEG" in p for p in igs.validate_for_publish(png))
    local = _item(format="carousel", asset_ref="/tmp/a.jpg\n/tmp/b.jpg")
    assert any("public https" in p for p in igs.validate_for_publish(local))


def test_carousel_publish_goes_through_approval(db, fake_ig):
    item = _item(format="carousel", asset_ref="https://h/1.jpg, https://h/2.jpg, https://h/3.mp4")
    db.add(item)
    db.flush()
    ap = ApprovalRequest(
        action="publish_media", target_type="calendar_item", target_id=item.id, summary="s", status="approved"
    )
    db.add(ap)
    db.flush()
    job = igs.execute_publish(db, ap, fake_ig)
    assert job.status == "published" and job.container_id == "carousel-1"
    assert [c[0] for c in fake_ig.containers] == ["image", "image", "video"]
    assert all(c[2] for c in fake_ig.containers)  # every child flagged as carousel item
    db.rollback()


def test_sync_stores_total_watch_time_and_reply_threads(client, fake_ig):
    try:
        _connect(fake_ig)
        r = client.post("/api/instagram/sync").json()
        assert r["activity"]["replies"] == 3
        with SessionLocal() as db:
            snap = db.scalar(select(MediaSnapshot).where(MediaSnapshot.total_watch_time_ms.is_not(None)))
            assert snap is not None and snap.total_watch_time_ms > 0
            reply = db.scalar(select(Comment).where(Comment.parent_ig_id.is_not(None)))
            assert reply.from_owner and reply.done
            parent = db.scalar(select(Comment).where(Comment.ig_comment_id == reply.parent_ig_id))
            assert parent.replied  # answered on Instagram already -> leaves the "needs reply" list
        items = client.get("/api/comments?filter=all").json()["items"]
        assert all(i["parent_ig_id"] is None for i in items)
        assert any(i["replies"] and i["replies"][0]["from_owner"] for i in items)
    finally:
        _disconnect()


def test_auto_sync_skips_recent_and_runs_when_stale(fake_ig):
    try:
        acct_id = _connect(fake_ig)
        with SessionLocal() as db:
            db.get(InstagramAccount, acct_id).last_sync_at = datetime.now(UTC) - timedelta(hours=2)
            db.commit()
        assert auto_sync(SessionLocal, lambda tok, uid: fake_ig) == {"skipped": "synced recently"}
        with SessionLocal() as db:
            db.get(InstagramAccount, acct_id).last_sync_at = datetime.now(UTC) - timedelta(days=2)
            db.commit()
        res = auto_sync(SessionLocal, lambda tok, uid: fake_ig)
        assert res["media_synced"] == 3
        assert fake_ig.published == [] and fake_ig.replies == []  # read-only
    finally:
        _disconnect()
    assert auto_sync(SessionLocal, lambda tok, uid: fake_ig) == {"skipped": "not connected"}


def test_capabilities_and_status(client):
    caps = client.get("/api/instagram/capabilities").json()
    st = {c["status"] for c in caps}
    assert {"used", "needs_server", "not_possible"} <= st
    assert any("saved" in c["what"].lower() and c["status"] == "not_possible" for c in caps)
    assert "auto_sync" in client.get("/api/instagram/status").json()
