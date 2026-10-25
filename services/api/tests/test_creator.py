from app.services import coach, creator


def test_hooks_third_person_and_scored(client):
    r = client.post("/api/create/hooks", json={"topic": "APIs", "perspective": "third"}).json()
    assert r["source"] == "template" and len(r["hooks"]) == 6
    assert all(not h["text"].lower().startswith(("you ", "i ")) for h in r["hooks"])
    assert [h["score"] for h in r["hooks"]] == sorted((h["score"] for h in r["hooks"]), reverse=True)
    assert "can't predict" in r["note"]


def test_score_hook_flags_weak_opener(client):
    weak = client.post(
        "/api/create/score-hook", json={"text": "Hey guys, welcome back to my channel, today we will talk"}
    ).json()
    strong = client.post(
        "/api/create/score-hook", json={"text": "Your ₹20 chai order already explains APIs."}
    ).json()
    assert weak["score"] < strong["score"] and weak["verdict"] != "STRONG"


def test_caption_fits_preview_and_limits(client):
    r = client.post(
        "/api/create/caption",
        json={"topic": "UPI", "hook": "Crores pay on UPI at 8pm.", "category": "tech_concepts"},
    ).json()
    assert len(r["first_line"]) <= 125 and r["length"] <= 2200
    assert 3 <= len(r["hashtags"]) <= 5 and r["preview_cut"].endswith("... more")


def test_repurpose_audiences_differ(client):
    b = client.post("/api/create/repurpose", json={"topic": "APIs", "audience": "beginner"}).json()
    d = client.post("/api/create/repurpose", json={"topic": "APIs", "audience": "developer"}).json()
    assert (
        len(b["carousel"]) == 5
        and b["linkedin_post"]
        and b["youtube_short"]
        and b["text_post"]
        and b["reel_30s"]
    )
    assert b["carousel"][1]["text"] != d["carousel"][1]["text"]


def test_quick_idea_duplicate_guard(client):
    r = client.post(
        "/api/ideas/quick", json={"title": "How a bank loan EMI is calculated", "category": "skills"}
    )
    assert r.status_code == 201
    dup = client.post("/api/ideas/quick", json={"title": "How bank loan EMI is calculated"})
    assert dup.status_code == 409 and dup.json()["error"]["similar"]
    forced = client.post("/api/ideas/quick", json={"title": "How bank loan EMI is calculated", "force": True})
    assert forced.status_code == 201


def test_board_plan_week_and_save(client):
    b = client.get("/api/board").json()
    assert [c["status"] for c in b["columns"]] == [
        "idea",
        "script",
        "recording",
        "editing",
        "ready",
        "published",
    ]
    idea_id = b["columns"][0]["items"][0]["id"]
    p = client.post(f"/api/ideas/{idea_id}/plan", json={"when": "2026-10-28T19:00:00"}).json()
    assert p["scheduled_at"].startswith("2026-10-28T13:30")
    p2 = client.post(f"/api/ideas/{idea_id}/plan", json={"when": "2026-10-29T19:00:00"}).json()
    assert p2["calendar_id"] == p["calendar_id"]  # re-plan moves, no duplicate slot
    wk = client.get("/api/week?start=2026-10-26").json()
    assert any(i["idea_id"] == idea_id for i in wk["items"])
    s = client.post(
        "/api/create/save", json={"idea_id": idea_id, "hook": "Most beginners skip this.", "hashtags": ["#a"]}
    ).json()
    assert s["status"] == "script"


def test_today_has_one_clear_suggestion(client):
    t = client.get("/api/today").json()
    assert t["suggestion"]["step"] and t["suggestion"]["hook"] and t["suggestion"]["caption"]
    assert "goal" in t and "week" in t


def test_insights_find_demo_patterns(client):
    r = client.get("/api/insights").json()
    assert r["sample_size"] >= 10
    kinds = {i["kind"] for i in r["insights"]}
    assert "outlier" in kinds and "pattern" in kinds
    assert all(i["confidence"] in ("none", "low", "medium", "high") for i in r["insights"])
    assert r["answers"]["best_hooks"] and r["answers"]["formats"]


def test_manual_post_and_csv_switch_to_real_data(client):
    csv_text = (
        "date,title,views,reach,likes,comments,shares,saves,avg_watch_seconds,category,format,length_seconds,hook\n"
        "2026-10-02,Speak confidently,405000,300000,8848,39,1200,2100,6.5,skills,talking_head,45,Most people freeze\n"
        "2026-10-05,AI tools list,1500,1100,40,2,1,3,4,ai,screen_recording,50,\n"
        "bad-date,x,1,1,1,1,1,1,1,ai,,,\n"
    )
    try:
        r = client.post("/api/posts/import-csv", json={"csv_text": csv_text}).json()
        assert r["added"] == 2 and len(r["errors"]) == 1
        posts = client.get("/api/posts").json()
        assert {p["source"] for p in posts} == {"manual"}
        assert client.get("/api/today").json()["mode"] == "manual"
        pid = posts[0]["id"]
        t = client.patch(
            f"/api/posts/{pid}", json={"hook_text": "Nobody tells you this about interviews"}
        ).json()
        assert t["hook_style"] == "Nobody Tells You"
    finally:
        from app.db import SessionLocal
        from app.models import InstagramAccount

        with SessionLocal() as db:
            for a in db.query(InstagramAccount).filter_by(is_demo=False):
                db.delete(a)
            db.commit()
        client.put("/api/settings", json={"prefer_real_data": False})


def test_coach_refuses_patterns_on_tiny_samples():
    posts = [
        {"id": 1, "views": 100, "reach": 80, "shares": 1, "pillar": "ai"},
        {"id": 2, "views": 5000, "reach": 4000, "shares": 50, "pillar": "career"},
    ]
    r = coach.analyse(posts)
    assert not [i for i in r["insights"] if i["kind"] == "pattern"]  # n=1 per group: no "pattern"
    assert any(i["kind"] == "data" for i in r["insights"])


def test_classifier_matches_skill_formulas():
    assert (
        creator.classify_hook("Nobody tells you your first 30 reels are supposed to flop")
        == "Nobody Tells You"
    )


def test_statement_titles_are_framed_not_used_as_a_noun():
    hooks = creator.generate_hooks("Your degree doesn't decide your tech career", "beginner", "third")
    assert not any(" about Your " in h.text or "explains Your" in h.text for h in hooks)
    assert any(h.text.startswith("Nobody tells most beginners this: your degree") for h in hooks)
    cap = creator.generate_caption("Your degree doesn't decide your tech career", None, "career")
    assert "Here's what I mean, even if you're just starting out." in cap.body


def test_coach_ai_brief_drops_lines_with_invented_numbers(monkeypatch):
    from app.services import coach, creator

    coach._brief_cache.clear()
    res = {"sample_size": 7, "tagged": 2, "summary": {"median_views": 1200}, "insights": [],
           "answers": {"repeat": [], "improve": [], "stop": []}, "posts": []}

    def fake(kind, payload, schema, fallback):
        return schema(headline="Your typical reel gets 1200 views.",
                      working=["Career reels travel further.", "Expect 50000 views next week."],
                      fix=["Tag 5 more posts."], this_week=["Post 2 reels.", "Reply to comments.", "Tag posts."]), "openai"

    monkeypatch.setattr(creator, "generate_with_model", fake)
    b = coach.ai_brief(res)
    assert b["available"] and b["headline"] == "Your typical reel gets 1200 views."
    assert b["working"] == ["Career reels travel further."]  # 50000 not in evidence
    assert b["this_week"] == ["Reply to comments."] or "Post 2 reels." in b["this_week"]


def test_coach_ai_brief_unavailable_without_model(monkeypatch):
    from app.services import coach, creator

    coach._brief_cache.clear()
    monkeypatch.setattr(creator, "generate_with_model", lambda k, p, s, fb: (fb(), "template"))
    assert coach.ai_brief({"posts": [], "answers": {}})["available"] is False
