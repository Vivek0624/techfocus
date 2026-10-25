from app.services import activity as act


def test_classifier():
    assert act.classify("How do I start with AWS?") == "question"
    assert act.classify("kaise start karu bhai") == "question"
    assert act.classify("Please make a video on Kafka") == "request"
    assert act.classify("DM us for promotion") == "spam"
    assert act.classify("This is so helpful 🔥") == "praise"
    assert act.classify("This is misleading") == "feedback"
    assert act.draft_reply("spam", "spam") is None


def test_demo_inbox_reply_is_simulated_and_never_posts(client, fake_ig):
    r = client.get("/api/comments").json()
    assert r["available"] and r["counts"]["needs_reply"] > 0
    assert all(c["intent"] in ("question", "request", "feedback") for c in r["items"])
    c = r["items"][0]
    assert c["draft_reply"]
    s = client.post(f"/api/comments/{c['id']}/reply", json={"text": "Thanks!"}).json()
    assert s["simulated"] is True and fake_ig.replies == []
    assert client.post(f"/api/comments/{c['id']}/reply", json={"text": "again"}).status_code == 409


def test_comment_to_idea_and_hide(client):
    items = client.get("/api/comments?filter=all").json()["items"]
    q = next(i for i in items if i["intent"] == "question")
    idea = client.post(f"/api/comments/{q['id']}/to-idea").json()
    again = client.post(f"/api/comments/{q['id']}/to-idea").json()
    assert again["existing"] and again["id"] == idea["id"]
    spam = next(i for i in items if i["intent"] == "spam")
    assert client.post(f"/api/comments/{spam['id']}/hide", json={"hide": True}).json()["hidden"]
    assert any(i["id"] == spam["id"] for i in client.get("/api/comments?filter=hidden").json()["items"])


def test_audience_demo_and_best_time(client):
    a = client.get("/api/audience").json()
    assert a["available"] and a["age"] and a["cities"] and len(a["most_active_hours"]) == 24
    assert a["best_times"] and "followers are online" in a["recommendation"]


def test_mentions(client):
    assert client.get("/api/mentions").json()["items"]


def test_live_sync_pulls_comments_mentions_and_tolerates_missing_audience(client, fake_ig):
    from tests.test_instagram import _connect, _disconnect

    try:
        _connect(fake_ig)
        r = client.post("/api/instagram/sync").json()
        assert r["activity"]["comments"] == 6 and r["activity"]["mentions"] == 1
        assert r["activity"]["audience"] == []  # <100 followers: unavailable, not an error
        # comment scope not granted in _connect -> live reply refused with a clear message
        live = client.get("/api/comments?filter=all").json()["items"]
        resp = client.post(f"/api/comments/{live[0]['id']}/reply", json={"text": "hi"})
        assert resp.status_code == 403 and "instagram_business_manage_comments" in resp.json()["error"]
        assert fake_ig.replies == []
        assert client.get("/api/audience").json()["available"] is False
    finally:
        _disconnect()
