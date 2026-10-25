from datetime import UTC, datetime, timedelta

import httpx

from app.config import get_settings
from app.instagram import client as ig
from app.services import growth


def _post(i, **kw):
    base = {
        "id": i,
        "title": f"post {i}",
        "views": 1000,
        "reach": 800,
        "shares": 4,
        "saved": 8,
        "published_at": datetime(2026, 10, 1, 14, 0, tzinfo=UTC) + timedelta(days=i),
        "media_product_type": "REELS",
    }
    return {**base, **kw}


# ---------- attribution / client ----------


def test_feed_metrics_include_attribution_and_reposts():
    assert {"follows", "profile_visits", "profile_activity", "reposts"} <= set(ig.FEED_METRICS)
    assert "follows" not in ig.REEL_METRICS and "reposts" in ig.REEL_METRICS


def test_media_insights_retries_without_optional_metrics_and_keeps_none():
    seen = []

    def handler(req):
        metric = req.url.params["metric"]
        seen.append(metric)
        if "reposts" in metric:
            return httpx.Response(400, json={"error": {"message": "invalid metric", "code": 100}})
        return httpx.Response(200, json={"data": [{"name": "views", "values": [{"value": 50}]}]})

    c = ig.InstagramClient(get_settings(), "t", http=httpx.Client(transport=httpx.MockTransport(handler)))
    out = c.media_insights("m1", "FEED")
    assert len(seen) == 2 and "follows" not in seen[1]
    assert out["views"] == 50 and out["follows"] is None and out["reposts"] is None  # missing = None, not 0


def test_media_insights_reads_total_value():
    def handler(req):
        return httpx.Response(
            200,
            json={
                "data": [
                    {"name": "profile_activity", "total_value": {"value": 7}},
                    {"name": "follows", "values": [{"value": 3}]},
                ]
            },
        )

    c = ig.InstagramClient(get_settings(), "t", http=httpx.Client(transport=httpx.MockTransport(handler)))
    out = c.media_insights("m1", "FEED")
    assert out["profile_activity"] == 7 and out["follows"] == 3 and out["profile_visits"] is None


def test_attribution_reels_vs_feed():
    reel = growth.attribution({"media_product_type": "REELS", "follows": None, "reposts": 2})
    assert reel["available"] is False and "Reels" in reel["note"] and reel["reposts"] == 2
    feed = growth.attribution({"media_product_type": "FEED", "follows": 4, "profile_visits": 20})
    assert feed["available"] and feed["follows"] == 4
    empty = growth.attribution({"media_product_type": "FEED"})
    assert empty["available"] is False and empty["follows"] is None


def test_insights_posts_carry_attribution(client):
    posts = client.get("/api/insights").json()["posts"]
    feed = [p for p in posts if p["media_product_type"] == "FEED"]
    reels = [p for p in posts if p["media_product_type"] == "REELS"]
    assert feed and all(
        p["attribution"]["available"] and p["attribution"]["follows"] is not None for p in feed
    )
    assert all(not p["attribution"]["available"] for p in reels)
    assert any(p["reposts"] is None for p in posts)  # not reported stays None


# ---------- audience segments ----------


def test_infer_audience_keywords_and_default():
    assert growth.infer_audience("5 ChatGPT prompts for coders", "ai")["audience"] == "ai_enthusiasts"
    assert growth.infer_audience("How to crack your first interview", None)["audience"] == "career"
    assert growth.infer_audience("REST vs GraphQL in production", "tech_concepts")["audience"] == "developers"
    d = growth.infer_audience("hello there", "relatable_learning")
    assert d["audience"] == "students" and d["inferred"]


def test_audience_of_prefers_user_tag():
    a = growth.audience_of({"audience": "students", "title": "AWS in production"})
    assert a["audience"] == "students" and not a["inferred"]


def test_segment_performance_has_n_and_confidence():
    posts = [_post(i, title="interview tips", shares=10) for i in range(3)] + [
        _post(10 + i, title="docker basics for backend", shares=2) for i in range(3)
    ]
    r = growth.segment_performance(posts)
    rows = {s["segment"]: s for s in r["segments"]}
    assert rows["career"]["n"] == 3 and rows["career"]["shares_per_1k"] == 12.5
    assert rows["career"]["confidence"] == "medium"
    assert r["headline"] and "n=3" in r["headline"]


def test_segments_endpoint_and_tagging(client):
    r = client.get("/api/growth/segments").json()
    assert r["segments"] and all("n" in s and "confidence" in s for s in r["segments"])
    pid = client.get("/api/posts").json()[0]["id"]
    assert client.patch(f"/api/posts/{pid}", json={"audience": "students"}).status_code == 200
    assert client.patch(f"/api/posts/{pid}", json={"audience": "aliens"}).status_code == 422


# ---------- shareability ----------


def test_shareability_subscores_and_reasons():
    weak = growth.shareability("Some thoughts on cloud")
    strong = growth.shareability(
        "Most freshers freeze in interviews. 3 steps to fix it. Send this to a friend who needs it?"
    )
    assert strong["score"] > weak["score"]
    assert set(strong["subscores"]) == {"relatability", "usefulness", "curiosity", "share_trigger"}
    assert strong["subscores"]["share_trigger"]["reasons"]
    assert "not a prediction" in strong["note"]


def test_shareability_calibrates_only_with_n3():
    two = [_post(i, pillar="career", shares=10) for i in range(2)]
    assert growth.shareability("x", "career", None, two)["calibration"] is None
    three = two + [_post(3, pillar="career", shares=10)]
    cal = growth.shareability("x", "career", None, three)["calibration"]
    assert cal["groups"][0]["n"] == 3 and cal["groups"][0]["median_shares_per_1k"] == 12.5


def test_shareability_endpoint_and_board(client):
    r = client.post(
        "/api/create/shareability",
        json={"text": "Your degree doesn't decide your career", "category": "career"},
    )
    assert r.status_code == 200 and 0 <= r.json()["score"] <= 100 and r.json()["audience"]["audience"]
    cards = [i for c in client.get("/api/board").json()["columns"] for i in c["items"]]
    assert cards and all(0 <= c["shareability"] <= 100 and c["audience"] for c in cards)


# ---------- fatigue ----------


def test_fatigue_flags_repetition_and_decline():
    posts = [_post(i, pillar="ai", format_style="screen_recording", views=1000) for i in range(4)]
    posts += [_post(4 + i, pillar="ai", format_style="screen_recording", views=400) for i in range(2)]
    posts += [_post(10 + i, pillar="career", format_style="talking_head", views=1000) for i in range(4)]
    for p in posts[10 - 4 :]:
        p["published_at"] -= timedelta(days=60)  # career posts are older
    r = growth.fatigue(posts, 6)
    assert any(x["dimension"] == "topic" and x["group"] == "ai" for x in r["repetitive"])
    assert any(d["group"] == "ai" and d["metric"] == "views" for d in r["declining"])
    assert not r["ok"]


def test_fatigue_ok_when_varied():
    cats = ["ai", "career", "skills", "tech_concepts"]
    posts = [
        _post(
            i,
            pillar=cats[i % 4],
            format_style=["talking_head", "carousel", "motion_graphics"][i % 3],
            audience=["beginners", "developers", "students"][i % 3],
        )
        for i in range(6)
    ]
    r = growth.fatigue(posts, 6)
    assert r["repetitive"] == [] and r["declining"] == []


def test_fatigue_endpoint(client):
    r = client.get("/api/growth/fatigue").json()
    assert r["window"] == 6 and "repetitive" in r and "declining" in r


# ---------- opportunity gaps ----------


def test_gaps_cluster_and_coverage():
    comments = [
        {"id": 1, "text": "How do UPI refunds work?", "intent": "question", "like_count": 5},
        {"id": 2, "text": "Please explain refunds on PhonePe", "intent": "request", "like_count": 3},
        {"id": 3, "text": "Can you explain REST vs GraphQL?", "intent": "request", "like_count": 1},
        {"id": 4, "text": "Great video", "intent": "praise", "like_count": 9},
    ]
    covered = [("post", "REST vs GraphQL in 30 seconds || ", 7)]
    r = growth.opportunity_gaps(comments, covered)
    assert r["questions_considered"] == 3
    assert len(r["gaps"]) == 1 and r["gaps"][0]["count"] == 2 and "refund" in r["gaps"][0]["theme"]
    assert r["covered"][0]["covered_by"]["id"] == 7
    assert "own posts" in r["note"]


def test_gaps_endpoint_and_to_idea(client):
    r = client.get("/api/growth/gaps").json()
    assert r["gaps"], "demo data should surface at least one uncovered question"
    g = r["gaps"][0]
    made = client.post(
        "/api/growth/gaps/to-idea",
        json={"title": g["suggested_title"], "comment_ids": [c["id"] for c in g["comments"]]},
    )
    assert made.status_code == 201
    idea = client.get(f"/api/content/{made.json()['id']}").json()
    assert idea["status"] == "idea" and idea["evidence"]


# ---------- brand voice ----------


def test_lint_voice_flags():
    p = {
        "banned_words": ["game-changer"],
        "preferred_cta": "Save this",
        "signature_hashtags": ["#techindia"],
        "emoji_level": "none",
    }
    r = growth.lint_voice("This always works, 100% — a game-changer 🔥", p)
    kinds = [i["kind"] for i in r["issues"]]
    assert {"banned_word", "claim", "style", "emoji", "cta", "hashtags"} <= set(kinds)
    assert kinds.count("claim") == 2 and not r["ok"]
    clean = growth.lint_voice("APIs, simply. Save this. #techindia", p)
    assert clean["ok"] and clean["score"] == 100


def test_voice_profile_roundtrip(client):
    assert client.get("/api/voice").json()["emoji_level"]
    bad = client.put("/api/voice", json={"signature_hashtags": ["a", "b", "c", "d", "e", "f"]})
    assert bad.status_code == 422
    r = client.put(
        "/api/voice",
        json={"signature_hashtags": ["techfocus"], "banned_words": ["hack"], "emoji_level": "none"},
    )
    assert r.json()["signature_hashtags"] == ["#techfocus"]
    lint = client.post("/api/create/voice-check", json={"text": "Quick hack for APIs"}).json()
    assert any(i["kind"] == "banned_word" for i in lint["issues"])


# ---------- reel script ----------


def test_reel_script_covers_duration():
    s = growth.reel_script("APIs", "beginner", None, 45)
    assert s.beats[0].start == 0 and s.beats[-1].end == 45
    assert all(b.voiceover and b.on_screen and b.visual for b in s.beats)
    assert all(a.end == b.start for a, b in zip(s.beats, s.beats[1:], strict=False))
    assert s.caption and s.hook == s.beats[0].voiceover


def test_reel_script_endpoint(client):
    r = client.post(
        "/api/create/reel-script", json={"topic": "UPI", "duration": 30, "hook": "Crores pay on UPI at 8pm."}
    )
    assert r.status_code == 200 and r.json()["source"] == "template"
    assert r.json()["hook"] == "Crores pay on UPI at 8pm." and r.json()["beats"][-1]["end"] == 30


# ---------- posting windows ----------


def test_posting_windows_groups_by_ist_window():
    # 14:00 UTC = 19:30 IST (evening); 07:00 UTC = 12:30 IST (midday)
    posts = [_post(i, views=2000) for i in range(3)]
    posts += [
        _post(10 + i, views=1000, published_at=datetime(2026, 10, 1 + i, 7, 0, tzinfo=UTC)) for i in range(3)
    ]
    r = growth.posting_windows(posts, {"20": 50, "13": 10})
    rows = {w["label"]: w for w in r["windows"]}
    assert rows["evening (6-9 PM)"]["n"] == 3 and rows["midday (11 AM-3 PM)"]["n"] == 3
    assert r["best"]["label"] == "evening (6-9 PM)" and r["best"]["confidence"] == "medium"
    assert r["online_peaks"][0]["hour"] == 20 and "approval" in r["note"]


def test_posting_windows_empty():
    r = growth.posting_windows([], None)
    assert r["best"] is None and "Not enough" in r["recommendation"]


def test_schedule_endpoint(client):
    r = client.get("/api/growth/schedule").json()
    assert r["windows"] and r["online_peaks"] and r["sample_size"] > 0


# ---------- shortlist / content memory ----------


def test_shortlist_flags_memory_and_duplicates():
    posts = [
        _post(i, title="Why doesn't UPI crash at 8pm", format_style="screen_recording", views=300)
        for i in range(2)
    ]
    posts += [
        _post(5 + i, format_style="talking_head", views=1500, title=f"career story {i}") for i in range(4)
    ]
    ideas = [
        {"id": 1, "title": "Why doesn't UPI crash at 8pm?", "status": "ready", "format": "screen_recording"},
        {"id": 2, "title": "Most freshers freeze in interviews", "status": "idea", "format": "talking_head"},
        {"id": 3, "title": "Old", "status": "published"},
    ]
    r = growth.shortlist(ideas, posts)
    by = {i["idea_id"]: i for i in r["items"]}
    assert 3 not in by and len(r["items"]) == 2
    kinds = {f["kind"] for f in by[1]["flags"]}
    assert {"near_duplicate", "underperformed"} <= kinds
    assert by[2]["watch"]["target"] is not None and "median" in by[2]["watch"]["text"]
    assert by[2]["audience"]["audience"] and 0 <= by[2]["shareability"]["score"] <= 100
    assert r["memory"]["avoid"][0]["group"] == "screen_recording"


def test_today_has_shortlist(client):
    t = client.get("/api/today").json()
    assert 1 <= len(t["shortlist"]) <= 3
    s = t["shortlist"][0]
    assert s["why"] and s["audience"]["label"] and "shares" in s["watch"]["text"].lower()
    assert client.get("/api/growth/briefing").json()["items"]
