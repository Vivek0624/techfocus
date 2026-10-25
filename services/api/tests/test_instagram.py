from datetime import UTC, datetime, timedelta

import httpx
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.instagram import client as ig
from app.instagram import service as igs
from app.models import ApprovalRequest, CalendarItem, ExternalWriteAudit, InstagramAccount
from app.security import get_cipher


def _connect(fake):
    with SessionLocal() as db:
        tok = {
            "access_token": "IGQ-live-token",
            "expires_at": datetime.now(UTC) + timedelta(days=60),
            "user_id": "1784",
            "permissions": [
                "instagram_business_basic",
                "instagram_business_manage_insights",
                "instagram_business_content_publish",
            ],
        }
        acct = igs.store_connection(db, get_cipher(), tok, fake.get_profile())
        db.commit()
        return acct.id


def _disconnect():
    with SessionLocal() as db:
        for a in db.scalars(select(InstagramAccount).where(InstagramAccount.is_demo.is_(False))):
            db.delete(a)
        db.commit()


def test_connect_start_requires_config_and_returns_state(client):
    r = client.get("/api/instagram/connect")
    assert r.status_code == 200
    url = r.json()["authorize_url"]
    assert url.startswith("https://www.instagram.com/oauth/authorize?")
    assert "state=" in url and "instagram_business_basic" in url


def test_callback_rejects_bad_state(client):
    r = client.get("/api/instagram/callback?code=abc&state=forged", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "invalid_state" in r.headers["location"]


def test_exchange_code_with_mock_transport():
    def handler(req: httpx.Request):
        if req.url.host == "api.instagram.com":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"access_token": "short", "user_id": 99, "permissions": "instagram_business_basic"}
                    ]
                },
            )
        assert req.url.params["grant_type"] == "ig_exchange_token"
        return httpx.Response(200, json={"access_token": "long", "expires_in": 5183944})

    out = ig.exchange_code(get_settings(), "code123", httpx.Client(transport=httpx.MockTransport(handler)))
    assert out["access_token"] == "long" and out["permissions"] == ["instagram_business_basic"]


def test_client_rate_limit_retry_and_pagination():
    calls = {"n": 0}

    def handler(req: httpx.Request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(400, json={"error": {"message": "rate", "code": 4}})
        if "after" in str(req.url):
            return httpx.Response(200, json={"data": [{"id": "2"}]})
        return httpx.Response(
            200,
            json={
                "data": [{"id": "1"}],
                "paging": {"next": "https://graph.instagram.com/v23.0/me/media?after=x"},
            },
        )

    c = ig.InstagramClient(get_settings(), "t", http=httpx.Client(transport=httpx.MockTransport(handler)))
    import app.instagram.client as mod

    orig = mod.time.sleep
    mod.time.sleep = lambda s: None
    try:
        ids = [m["id"] for m in c.iter_media(10)]
    finally:
        mod.time.sleep = orig
    assert ids == ["1", "2"]


def test_token_stored_encrypted_and_sync(client, fake_ig):
    try:
        acct_id = _connect(fake_ig)
        with SessionLocal() as db:
            acct = db.get(InstagramAccount, acct_id)
            assert "IGQ-live-token" not in acct.token.ciphertext
        st = client.get("/api/instagram/status").json()
        assert st["connected"] and st["token"]["state"] == "valid"
        r = client.post("/api/instagram/sync")
        assert r.status_code == 200, r.text
        assert r.json()["media_synced"] == 3
        client.post("/api/instagram/sync")  # idempotent
        d = client.get("/api/dashboard").json()
        assert d["mode"] == "live" and d["account"]["followers"] == 339
        assert d["metrics"]["likes"] is None  # unavailable stays None, not 0
        assert client.get("/api/instagram/media").json()["connected"] is True
    finally:
        _disconnect()


def test_personal_account_rejected(client, fake_ig):
    fake_ig.get_profile = lambda: {
        "user_id": "1",
        "username": "p",
        "account_type": "PERSONAL",
        "followers_count": 5,
    }
    try:
        _connect(fake_ig)
        r = client.post("/api/instagram/sync")
        assert r.status_code == 409 and "professional" in r.json()["error"]
    finally:
        _disconnect()


def test_publish_requires_approval_and_valid_asset(client, fake_ig):
    try:
        _connect(fake_ig)
        assert client.put("/api/settings", json={"prefer_real_data": True}).status_code == 200
        item = client.post(
            "/api/calendar",
            json={
                "title": "UPI",
                "scheduled_at": "2026-11-01T19:00:00",
                "caption": "cap",
                "asset_ref": "/Users/me/video.mp4",
            },
        ).json()
        r = client.post(f"/api/calendar/{item['id']}/request-publish")
        assert r.status_code == 422 and "public https" in str(r.json())
        client.patch(
            f"/api/calendar/{item['id']}", json={"asset_ref": "https://bucket.s3.amazonaws.com/v.mp4"}
        )
        ap = client.post(f"/api/calendar/{item['id']}/request-publish").json()
        # executing before approval is refused by the backend
        assert client.post(f"/api/approvals/{ap['approval_id']}/execute").status_code == 403
        assert fake_ig.published == []
        client.post(f"/api/approvals/{ap['approval_id']}/decision?approve=true")
        r = client.post(f"/api/approvals/{ap['approval_id']}/execute")
        assert r.status_code == 200 and r.json()["media_id"] == "media-999"
        # no duplicate publish
        assert client.post(f"/api/approvals/{ap['approval_id']}/execute").status_code == 409
        with SessionLocal() as db:
            assert db.scalar(
                select(ExternalWriteAudit).where(ExternalWriteAudit.approval_id == ap["approval_id"])
            )
    finally:
        _disconnect()
        client.put("/api/settings", json={"prefer_real_data": False})


def test_execute_publish_service_guard(db, fake_ig):
    item = CalendarItem(title="x", scheduled_at=datetime.now(UTC), caption="c", asset_ref="https://x/v.mp4")
    db.add(item)
    db.flush()
    ap = ApprovalRequest(
        action="publish_media", target_type="calendar_item", target_id=item.id, summary="s", status="rejected"
    )
    db.add(ap)
    db.flush()
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException):
        igs.execute_publish(db, ap, fake_ig)
    assert fake_ig.published == []


def test_demo_item_cannot_publish():
    item = CalendarItem(
        title="x", scheduled_at=datetime.now(UTC), caption="c", asset_ref="https://x/v.mp4", is_demo=True
    )
    assert "demo items cannot be published" in igs.validate_for_publish(item)


def test_online_followers_pacific_hours_become_ist():
    from app.instagram.client import pacific_hours_to_ist

    # 7 AM Pacific in October (PDT, UTC-7) is 7:30 PM IST, keyed as hour 19.
    assert pacific_hours_to_ist({"7": 10, "8": 4}, "2026-10-20T07:00:00+0000") == {"19": 10, "20": 4}
    # In January (PST, UTC-8) 7 AM Pacific is 8:30 PM IST.
    assert pacific_hours_to_ist({"7": 10}, "2026-01-20T08:00:00+0000") == {"20": 10}
