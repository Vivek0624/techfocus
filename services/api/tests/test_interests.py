import io
import zipfile
from pathlib import Path

from sqlalchemy import delete, select

from app.models import InterestItem
from app.services import interests as ints
from app.services import recommend

FX = Path(__file__).parent / "fixtures" / "ig_export"


def _raw(name: str) -> bytes:
    return (FX / name).read_bytes()


def test_parse_saved_posts_old_shape():
    kind, items = ints.parse_file(
        "your_instagram_activity/saved/saved_posts.json", _raw("saved_posts_v1.json")
    )
    assert kind == "saved" and len(items) == 2
    assert items[0]["creator"] == "aiexplained" and items[0]["url"].endswith("AAA111/")
    assert items[0]["happened_at"].year == 2024


def test_parse_collections_assigns_collection_and_fixes_mojibake():
    kind, items = ints.parse_file("saved/saved_collections.json", _raw("saved_collections_v1.json"))
    assert kind == "saved" and len(items) == 3
    assert [i["collection"] for i in items][:2] == ["AI tools", "AI tools"]
    assert items[0]["creator"] == "promptcraft"
    assert items[2]["collection"] == "Interview prep 💼"


def test_parse_liked_both_shapes():
    _, v1 = ints.parse_file("likes/liked_posts.json", _raw("liked_posts_v1.json"))
    _, v2 = ints.parse_file("likes/liked_posts.json", _raw("liked_posts_v2.json"))
    assert {i["creator"] for i in v1} == {"devmemes", "aiexplained"}
    assert v2[0]["creator"] == "cloudsimple" and v2[0]["url"].endswith("HHH888/")


def test_parse_following_and_topics_and_skip_unknown():
    _, fol = ints.parse_file("connections/followers_and_following/following.json", _raw("following.json"))
    assert {i["creator"] for i in fol} == {"aiexplained", "careercoach"}
    kind, topics = ints.parse_file(
        "ads_information/instagram_ads_and_businesses/ads_interests.json", _raw("ads_interests.json")
    )
    assert kind == "topic" and [t["collection"] for t in topics] == ["Technology", "Artificial intelligence"]
    assert ints.parse_file("personal_information/personal_information.json", b"{}") == (None, [])


def test_bad_json_reported_not_raised(db):
    res = ints.import_files(db, [("likes/liked_posts.json", b"{not json")], demo=True)
    assert res["added_total"] == 0 and res["errors"]
    db.rollback()


def _zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("your_instagram_activity/saved/saved_posts.json", _raw("saved_posts_v1.json"))
        z.writestr("your_instagram_activity/saved/saved_collections.json", _raw("saved_collections_v1.json"))
        z.writestr("your_instagram_activity/likes/liked_posts.json", _raw("liked_posts_v1.json"))
        z.writestr("connections/followers_and_following/following.json", _raw("following.json"))
        z.writestr(
            "ads_information/instagram_ads_and_businesses/ads_interests.json", _raw("ads_interests.json")
        )
        z.writestr("personal_information/personal_information/personal_information.json", b"{}")
        z.writestr("media/photo.jpg", b"\xff\xd8")
    return buf.getvalue()


def test_zip_import_into_demo_partition_is_idempotent(client, db):
    db.execute(delete(InterestItem).where(InterestItem.origin == "import", InterestItem.is_demo.is_(True)))
    db.commit()
    files = {"files": ("instagram-export.zip", _zip(), "application/zip")}
    r = client.post("/api/interests/import?partition=demo", files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["partition"] == "demo"
    assert body["added"] == {"saved": 5, "liked": 2, "following": 2, "topic": 2}
    assert body["files_skipped"] == 0  # unknown files are never even opened
    again = client.post("/api/interests/import?partition=demo", files=files).json()
    assert again["added_total"] == 0
    live = db.scalars(
        select(InterestItem).where(InterestItem.is_demo.is_(False), InterestItem.origin == "import")
    )
    assert list(live) == []  # nothing leaked into the live partition


def test_html_export_gets_hint(client):
    r = client.post(
        "/api/interests/import?partition=demo", files={"files": ("liked_posts.html", b"<html>", "text/html")}
    ).json()
    assert r["added_total"] == 0 and "JSON" in r["hint"]


def test_profile_infers_categories_with_labels(db):
    ints.import_files(db, [("x.zip", _zip())], demo=True)
    p = ints.profile(db, True)
    assert p["counts"]["saved"] >= 5
    assert "aiexplained" in [c["creator"] for c in p["top_creators"][:5]]
    cats = {c["category"]: c for c in p["categories"]}
    assert "ai" in cats and any("AI tools" in e for e in cats["ai"]["evidence"])
    assert "guessed" in p["inferred_note"]
    db.rollback()


def test_categorise_keywords():
    assert ints.categorise("ChatGPT prompts")[0] == "ai"
    assert ints.categorise("interview prep")[0] == "career"
    assert ints.categorise("zzz") == (None, [])


def test_manual_interest_rejects_non_instagram_url(client):
    bad = client.post("/api/interests/manual", json={"url": "https://evil.example/x", "note": "nice"})
    assert bad.status_code == 422
    ok = client.post(
        "/api/interests/manual",
        json={"url": "https://www.instagram.com/aiexplained/reel/XYZ/", "note": "great AI hook"},
    )
    assert ok.status_code == 201 and ok.json()["creator"] == "aiexplained"


def _post(i, pillar, views, shares, reach=1000):
    return {
        "id": i,
        "title": f"post {i}",
        "caption": "",
        "pillar": pillar,
        "views": views,
        "reach": reach,
        "shares": shares,
        "saved": 5,
        "published_at": None,
        "hook_text": None,
    }


def test_recommend_cites_sources_and_downranks_rejected():
    posts = [
        _post(1, "career", 1000, 30),
        _post(2, "career", 1100, 28),
        _post(3, "ai", 900, 5),
        _post(4, "ai", 1000, 6),
        _post(5, "skills", 950, 8),
    ]
    prof = {
        "categories": [
            {
                "category": "career",
                "label": "Jobs",
                "share": 60,
                "matches": 12,
                "evidence": ["collection “Interview prep”"],
                "confidence": "medium",
            }
        ],
        "notes": [],
        "total": 12,
    }
    res = recommend.recommend(posts, prof, [], {"gaps": []}, {}, {}, [], 3)
    top = res["items"][0]
    assert top["category"] == "career"
    srcs = {r["source"] for r in top["reasons"]}
    assert {"reels", "interests"} <= srcs
    assert "shares" in next(r["text"] for r in top["reasons"] if r["source"] == "reels")
    assert top["best_time"]["confidence"] == "none" and top["hook"]["text"]
    hist = [{"topic": "x", "category": "career", "feedback": "not_for_me", "feedback_at": None}] * 3
    res2 = recommend.recommend(posts, prof, [], {"gaps": []}, {}, {}, hist, 3)
    assert res2["items"][0]["category"] != "career"


def test_recommendation_feedback_and_save(client):
    r = client.get("/api/recommendations/next").json()
    assert r["items"] and all(i["reasons"] for i in r["items"])
    again = client.get("/api/recommendations/next").json()
    assert again["items"][0]["id"] == r["items"][0]["id"]  # reloads reuse today's row
    rid = r["items"][0]["id"]
    fb = client.post(f"/api/recommendations/{rid}/feedback", json={"verdict": "not_for_me"}).json()
    assert fb["feedback"] == "not_for_me"
    after = client.get("/api/recommendations/next").json()
    assert r["items"][0]["topic"] not in [i["topic"] for i in after["items"]]
    hist = client.get("/api/recommendations/history").json()
    assert any(h["id"] == rid and h["feedback"] == "not_for_me" for h in hist)
    for item in after["items"]:
        saved = client.post(f"/api/recommendations/{item['id']}/save")
        assert saved.status_code == 201
        idea = client.get(f"/api/content/{saved.json()['idea_id']}").json()
        if saved.json()["created"]:
            assert idea["notes"].startswith("Why this was suggested") and idea["title"] == item["topic"]
        else:
            assert idea["id"] == item["idea_id"]


def test_ai_enhance_keeps_data_reasons_and_rejects_invented_numbers(monkeypatch):
    from app.services import creator, recommend

    items = [
        {"topic": "UPI refunds", "category": "tech_concepts", "category_label": "Tech concepts",
         "reasons": [{"text": "Your tech reels get 2.3x shares (n=5)", "source": "reels"}], "flags": []},
        {"topic": "AI tools", "category": "ai", "category_label": "AI",
         "reasons": [{"text": "You save AI reels", "source": "saves"}], "flags": []},
    ]

    def fake(kind, payload, schema, fallback):
        return schema(picks=[
            {"index": 0, "topic": "Why UPI refunds take 3 days", "angle": "Settlement explained",
             "hook": "Most beginners think UPI refunds are instant.", "why": "Your tech reels get 2.3x shares."},
            {"index": 1, "topic": "AI tools that 90% of students miss", "angle": "x",
             "hook": "Most students skip this.", "why": "You like AI."},
        ]), "openai"

    monkeypatch.setattr(creator, "generate_with_model", fake)
    out, src = recommend.ai_enhance(items, [], {})
    assert src == "openai"
    # "3 days" is not in the evidence -> pick 0 keeps its data version; "90%" invented -> pick 1 too
    assert out[0]["topic"] == "UPI refunds" and "written_by" not in out[0]
    assert out[1]["topic"] == "AI tools"


def test_ai_enhance_accepts_grounded_rewrite(monkeypatch):
    from app.services import creator, recommend

    items = [{"topic": "UPI refunds", "category": "tech_concepts", "category_label": "Tech concepts",
              "reasons": [{"text": "Your tech reels get 2.3x shares (n=5)", "source": "reels"}], "flags": []}]
    monkeypatch.setattr(creator, "generate_with_model", lambda *a: (recommend._AIPicks(picks=[
        {"index": 0, "topic": "Where your UPI refund money waits", "angle": "Follow the money",
         "hook": "Most beginners never see where a refund goes.", "why": "Tech explainers get 2.3x your usual shares."},
    ]), "openai"))
    out, _ = recommend.ai_enhance(items, [], {})
    assert out[0]["topic"] == "Where your UPI refund money waits"
    assert out[0]["data_topic"] == "UPI refunds"
    assert out[0]["reasons"] == items[0]["reasons"]  # data reasons untouched
    assert out[0]["hook"]["score"] is not None


def test_ai_enhance_falls_back_when_model_unavailable(monkeypatch):
    from app.services import creator, recommend

    monkeypatch.setattr(creator, "generate_with_model", lambda k, p, s, fb: (fb(), "template"))
    items = [{"topic": "x topic", "category": "ai", "reasons": [], "flags": []}]
    assert recommend.ai_enhance(items, [], {}) == (items, "data")
