"""Reel Planner: schema validation, the two generate endpoints, and the saved-plan CRUD.

AGENT_MODE is "mock" in tests (conftest), so these exercise the template path: no network, no key.
"""

import pytest
from pydantic import ValidationError

from app.agents import schemas as S
from app.services import reel_prompts, reelplanner, trends

# ---------------- schema validation ----------------


def test_reel_plan_schema_rejects_bad_shapes():
    base = reelplanner._template_plan({"title": "APIs"}, "APIs", "instagram_reels", 30).model_dump()
    S.ReelPlanOut.model_validate(base)  # the template itself must always validate

    with pytest.raises(ValidationError):  # hooks must be exactly 3
        S.ReelPlanOut.model_validate({**base, "hooks": base["hooks"][:2]})
    with pytest.raises(ValidationError):  # reels are 15-45s
        S.ReelPlanOut.model_validate({**base, "total_duration_seconds": 90})
    with pytest.raises(ValidationError):  # 5-8 hashtags
        S.ReelPlanOut.model_validate({**base, "hashtags": ["#one", "#two"]})
    with pytest.raises(ValidationError):  # unknown script section
        bad = [dict(base["script"][0], section="outro")] + base["script"][1:]
        S.ReelPlanOut.model_validate({**base, "script": bad})


def test_trend_report_schema_and_template_is_labelled_not_live():
    r = reelplanner._template_trends("AI tools for developers", "instagram_reels", 9)
    S.TrendReport.model_validate(r.model_dump())
    assert r.live_research_performed is False
    assert r.disclosure.lower().startswith("model knowledge only")
    assert all(t.sources == [] for t in r.topics)  # no invented sources, ever
    assert len({t.title for t in r.topics}) == 9  # no duplicate topics

    with pytest.raises(ValidationError):
        S.TrendReport.model_validate({**r.model_dump(), "platform": "facebook"})


def test_invalid_model_output_retries_once_then_falls_back(monkeypatch):
    """_generate must retry on an output that does not validate, then use the template."""
    from app.services import creator

    calls = []
    monkeypatch.setattr(reelplanner, "get_settings", lambda: type("S", (), {"agent_mode": "openai"})())
    monkeypatch.setattr("app.agents.providers.model_config_error", lambda s: None)

    class Bad:
        def model_dump(self):
            return {"topic": "only this field"}  # fails ReelPlanOut validation

    def fake(kind, payload, schema, fallback):
        calls.append(payload.get("_correction"))
        return Bad(), "openai"

    monkeypatch.setattr(creator, "generate_with_model", fake)
    out, src = reelplanner._generate(
        "p",
        {"niche": "x"},
        S.ReelPlanOut,
        lambda: reelplanner._template_plan({"title": "x"}, "x", "instagram_reels", 30),
    )
    assert len(calls) == 2 and calls[0] is None and calls[1]  # tried once, retried with a correction
    assert src == "template (model output invalid)"
    assert isinstance(out, S.ReelPlanOut)


def test_no_search_provider_without_config():
    s = type("S", (), {"research_api_url": None, "research_api_key": None})()
    p = trends.get_provider(s)
    assert p.live is False and p.search("x", "Instagram Reels") == []

    s2 = type("S", (), {"research_api_url": "https://example.test/search", "research_api_key": None})()
    assert trends.get_provider(s2).live is True


def test_live_hits_are_never_cited_by_template_topics(monkeypatch, db):
    """Search can succeed while no model is configured. The template must not borrow those URLs."""
    hits = [{"title": "real page", "url": "https://example.test/a", "snippet": "x"}] * 3
    monkeypatch.setattr(
        trends,
        "get_provider",
        lambda s: type("P", (), {"name": "live_search", "live": True, "search": lambda self, n, p: hits})(),
    )
    out = reelplanner.find_trends(db, "APIs")
    assert out["search_results_found"] == 3
    assert out["source"] == "template"
    assert out["live_research_performed"] is False  # a template answer is never "live"
    assert all(t["sources"] == [] for t in out["topics"])
    assert "no AI model is configured" in out["disclosure"]


def test_prompts_carry_the_craft_and_honesty_rules():
    p = reel_prompts.trends("AI tools", "instagram_reels", 9)
    assert "Model knowledge only, not live" in p  # fallback must self-label
    assert "NO SEARCH RESULTS" in p
    assert "ONE idea per reel" in p and "Never invent" in p
    live = reel_prompts.trends("AI tools", "instagram_reels", 9, results=[{"title": "t", "url": "u"}])
    assert "live_research_performed = true" in live
    plan = reel_prompts.reel_plan({"title": "APIs"}, "APIs", "youtube_shorts", 30)
    assert "YouTube Shorts" in plan and "pattern interrupt" in plan


# ---------------- endpoints ----------------


def test_meta_and_trends_endpoint(client):
    meta = client.get("/api/reels/meta").json()
    assert meta["live_research_available"] is False  # no provider configured in tests
    assert meta["video_autoedit_available"] is False
    assert [p["value"] for p in meta["platforms"]] == list(reel_prompts.PLATFORMS)

    r = client.post("/api/reels/trends", json={"niche": "AI tools for developers"})
    assert r.status_code == 200
    body = r.json()
    assert 8 <= len(body["topics"]) <= 10
    assert body["live_research_performed"] is False
    assert "not live" in body["disclosure"].lower()
    assert all(t["sources"] == [] for t in body["topics"])
    assert body["topics"][0]["engagement_potential"] in ("high", "medium", "low")

    assert client.post("/api/reels/trends", json={"niche": "x"}).status_code == 422  # min_length 2
    assert client.post("/api/reels/trends", json={"niche": "ok", "platform": "snapchat"}).status_code == 422


def test_plan_save_reopen_regenerate_delete(client):
    topic = client.post("/api/reels/trends", json={"niche": "APIs for beginners"}).json()["topics"][0]

    r = client.post(
        "/api/reels/plan",
        json={"niche": "APIs for beginners", "platform": "instagram_reels", "topic": topic, "duration": 30},
    )
    assert r.status_code == 200, r.text
    plan = r.json()
    pkg = plan["package"]
    assert plan["saved"] is True and plan["id"]
    assert len(pkg["hooks"]) == 3 and len(pkg["script"]) >= 4 and len(pkg["shots"]) >= 3
    assert 15 <= pkg["total_duration_seconds"] <= 45
    assert 5 <= len(pkg["hashtags"]) <= 8
    assert pkg["cta_primary"] and pkg["cta_alternative"] != pkg["cta_primary"]
    assert [s["section"] for s in pkg["script"]][0] == "hook"

    pid = plan["id"]
    assert any(p["id"] == pid for p in client.get("/api/reels/plans").json()["items"])
    assert client.get(f"/api/reels/plans/{pid}").json()["package"]["topic"] == pkg["topic"]

    rg = client.post(f"/api/reels/plans/{pid}/regenerate", json={"section": "hooks"})
    assert rg.status_code == 200 and len(rg.json()["package"]["hooks"]) == 3
    assert client.post(f"/api/reels/plans/{pid}/regenerate", json={"section": "nope"}).status_code == 422

    assert client.delete(f"/api/reels/plans/{pid}").status_code == 204
    assert client.get(f"/api/reels/plans/{pid}").status_code == 404
    assert client.post(f"/api/reels/plans/{pid}/regenerate", json={"section": "hooks"}).status_code == 404


def test_plan_needs_a_topic(client):
    r = client.post("/api/reels/plan", json={"niche": "APIs", "topic": {}})
    assert r.status_code == 422


def test_niche_is_remembered_for_prefill(client):
    client.post("/api/reels/trends", json={"niche": "system design interviews"})
    assert client.get("/api/reels/meta").json()["niche"] == "system design interviews"


def test_video_editor_is_a_stub():
    with pytest.raises(NotImplementedError):
        reelplanner.NotImplementedVideoEditor().edit("clip.mp4", {})
    assert reelplanner.NotImplementedVideoEditor.available is False
