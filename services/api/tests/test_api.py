from sqlalchemy import inspect

from app.db import engine


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["data_mode"] == "demo"


def test_migrations_created_all_tables():
    tables = set(inspect(engine).get_table_names())
    for t in (
        "content_ideas",
        "instagram_tokens",
        "agent_runs",
        "tool_call_audit",
        "publishing_jobs",
        "approval_requests",
        "experiments",
        "learning_records",
        "alembic_version",
    ):
        assert t in tables


def test_dashboard_demo_labelled(client):
    d = client.get("/api/dashboard?days=7").json()
    assert d["mode"] == "demo"
    assert d["account"]["source"] == "demo"
    assert "SYNTHETIC" in d["account"]["username"]
    assert d["range"]["days"] == 7


def test_dashboard_custom_range_validation(client):
    r = client.get("/api/dashboard?start=2026-10-10&end=2026-10-01")
    assert r.status_code == 422


def test_content_crud_and_clone(client):
    r = client.post(
        "/api/content",
        json={
            "title": "Chai teaches APIs",
            "pillar": "tech_explained",
            "hashtags": ["api", "#tech"],
            "status": "idea",
        },
    )
    assert r.status_code == 201
    idea = r.json()
    assert idea["hashtags"] == ["#api", "#tech"]
    r = client.patch(f"/api/content/{idea['id']}", json={"status": "script", "script": "hello"})
    assert r.json()["status"] == "script"
    lst = client.get("/api/content?search=Chai").json()
    assert lst["total"] >= 1
    c = client.post(f"/api/content/{idea['id']}/clone").json()
    assert c["title"].endswith("(copy)") and c["status"] == "idea"
    assert client.delete(f"/api/content/{c['id']}").status_code == 204
    assert client.get(f"/api/content/{c['id']}").status_code == 404
    csv = client.get("/api/content/export?fmt=csv")
    assert "Chai teaches APIs" in csv.text


def test_content_validation(client):
    assert client.post("/api/content", json={"title": ""}).status_code == 422
    assert client.post("/api/content", json={"title": "x", "status": "viral"}).status_code == 422
    assert client.post("/api/content", json={"title": "x", "caption": "a" * 2201}).status_code == 422
    body = client.post("/api/content", json={"title": ""}).json()
    assert body["error"] == "validation failed"


def test_calendar_crud(client):
    r = client.post("/api/calendar", json={"title": "UPI reel", "scheduled_at": "2026-11-01T19:00:00"})
    assert r.status_code == 201
    item = r.json()
    assert item["timezone"] == "Asia/Kolkata"
    assert (
        "+05:30" in item["scheduled_at"]
        or item["scheduled_at"].endswith("Z")
        or "T13:30" in item["scheduled_at"]
    )
    r = client.patch(f"/api/calendar/{item['id']}", json={"caption": "hi"})
    assert r.json()["caption"] == "hi"
    assert client.get(f"/api/calendar/{item['id']}/manual-checklist").status_code == 200
    assert client.delete(f"/api/calendar/{item['id']}").status_code == 204


def test_growth_target(client):
    r = client.put(
        "/api/growth/target",
        json={"target": 10000, "days": 30, "start_followers": 339, "start_date": "2026-10-07"},
    )
    d = r.json()
    assert d["configured"] and d["remaining"] == 10000 - d["current"]
    assert "not predictions" in d["scenario_note"]


def test_experiments_flow(client):
    e = client.post(
        "/api/experiments",
        json={"name": "t", "hypothesis": "h", "variable": "hook_style", "control": "a", "variant": "b"},
    ).json()
    assert e["result"]["status"] == "insufficient_data"
    for arm, v in [
        ("control", 100),
        ("control", 120),
        ("control", 110),
        ("variant", 300),
        ("variant", 280),
        ("variant", 320),
    ]:
        e = client.post(f"/api/experiments/{e['id']}/observations", json={"arm": arm, "value": v}).json()
    assert e["status"] == "running"
    assert e["result"]["status"] == "ok" and e["result"]["lift_pct"] > 0
    assert (
        client.post(
            "/api/experiments",
            json={"name": "t", "hypothesis": "h", "variable": "astrology", "control": "a", "variant": "b"},
        ).status_code
        == 422
    )


def test_daily_plan_toggle(client):
    t = client.post("/api/growth/daily-plan", json={"title": "Record reel"}).json()
    r = client.patch(f"/api/growth/daily-plan/{t['id']}?done=true")
    assert r.json()["done"] is True


def test_settings_do_not_leak_secrets(client):
    s = client.get("/api/settings").json()
    flat = str(s)
    assert "test-secret" not in flat and "x2bUj3z" not in flat
    assert s["token_encryption_key_set"] is True
    assert client.put("/api/settings", json={"meta_app_secret": "x"}).status_code == 422


def test_demo_reset_keeps_real_records(client):
    client.post("/api/growth/manual-snapshot", json={"snapshot_date": "2026-10-20", "followers": 339})
    r = client.post("/api/demo/reset")
    assert r.status_code == 200
    from app.db import SessionLocal
    from app.models import AccountSnapshot

    with SessionLocal() as db:
        assert db.query(AccountSnapshot).filter_by(source="manual").count() == 1
    # restore demo mode for other tests
    client.put("/api/settings", json={"prefer_real_data": False})


def test_unknown_route_and_errors_hide_internals(client):
    r = client.get("/api/content/999999")
    assert r.status_code == 404 and r.json() == {"error": "content idea not found"}


def test_calendar_timezone_roundtrip(client):
    item = client.post("/api/calendar", json={"title": "tz", "scheduled_at": "2026-11-02T19:00:00"}).json()
    listed = [c for c in client.get("/api/calendar").json() if c["id"] == item["id"]][0]
    patched = client.patch(f"/api/calendar/{item['id']}", json={"caption": "x"}).json()
    from datetime import datetime

    t = {datetime.fromisoformat(x["scheduled_at"].replace("Z", "+00:00")) for x in (item, listed, patched)}
    assert len(t) == 1 and next(iter(t)).tzinfo is not None
    client.delete(f"/api/calendar/{item['id']}")


def test_cors_allows_localhost_and_127(client):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        r = client.options(
            "/api/settings", headers={"Origin": origin, "Access-Control-Request-Method": "GET"}
        )
        assert r.status_code == 200, origin


def test_dashboard_and_analytics_agree_on_multiples(client):
    d = {p["ig_media_id"]: p["multiple"] for p in client.get("/api/dashboard?days=30").json()["recent_posts"]}
    a = {p["ig_media_id"]: p["multiple"] for p in client.get("/api/analytics?days=30").json()["posts"]}
    assert all(a[k] == v for k, v in d.items() if k in a)


def test_dict_endpoints_emit_timezone_aware_timestamps(client):
    d = client.get("/api/dashboard").json()
    stamps = [p["published_at"] for p in d["recent_posts"]] + [u["scheduled_at"] for u in d["upcoming"]]
    assert stamps and all(s.endswith("+00:00") for s in stamps)
