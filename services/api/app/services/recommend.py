"""Next-reel recommendations. Combines three things, each cited with its source and sample size:

(a) what performs for this audience  - the user's own reel stats (shares/saves per 1k reached), coach patterns,
    comment questions, audience active hours;
(b) what the user is into             - saves, likes, collections and notes from their own data download;
(c) content memory                    - what was already posted, what underperformed, near-duplicates, and
    the user's own "made it / not for me" feedback.

Nothing here predicts views or followers."""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter
from collections.abc import Sequence
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field

from ..models import CATEGORIES, utcnow
from . import coach, creator, growth
from .interests import CATEGORY_LABEL, categorise

SOURCE_LABEL = {
    "reels": "Your reels",
    "comments": "Your comments",
    "interests": "Your saves & likes",
    "ideas": "Your ideas",
    "audience": "Instagram audience data",
    "memory": "What you already posted",
    "feedback": "Your feedback",
}

CATEGORY_NOUN = {
    "ai": "AI",
    "tech_concepts": "tech-explainer",
    "career": "career",
    "skills": "skills",
    "relatable_learning": "relatable student-life",
}

STARTERS = {
    "ai": "One AI tool that saves you an hour a day",
    "tech_concepts": "How UPI moves money in 2 seconds",
    "career": "The interview question freshers get wrong",
    "skills": "One habit that makes you sound confident",
    "relatable_learning": "Things every engineering student pretends to understand",
}


def with_category(posts: Sequence[dict]) -> list[dict]:
    """Untagged synced posts get a category guessed from the caption (marked as inferred)."""
    out = []
    for p in posts:
        q = dict(p)
        if not q.get("pillar"):
            cat, hits = categorise(
                f"{q.get('title') or ''} {q.get('caption') or ''} {q.get('hook_text') or ''}"
            )
            q["pillar"], q["pillar_inferred"] = cat, bool(cat)
        out.append(q)
    return out


def _reason(text: str, source: str, confidence: str, sample: int | None = None) -> dict[str, Any]:
    return {
        "text": text,
        "source": source,
        "source_label": SOURCE_LABEL[source],
        "confidence": confidence,
        "sample": sample,
    }


def performance_by_category(posts: Sequence[dict]) -> dict[str, dict[str, Any]]:
    enriched = [p for p in coach.enrich(posts) if (p.get("multiple") or 0) < 3]
    out: dict[str, dict[str, Any]] = {}
    for metric in ("shares_per_1k", "saves_per_1k", "multiple"):
        allv = [p[metric] for p in enriched if p.get(metric) is not None]
        overall = statistics.median(allv) if allv else None
        for r in coach.group_stats(enriched, "pillar", metric):
            d = out.setdefault(r["group"], {"n": r["n"]})
            d[metric] = r["median"]
            d[f"{metric}_ratio"] = round(r["median"] / overall, 1) if overall else None
            inferred = sum(1 for p in enriched if p.get("pillar") == r["group"] and p.get("pillar_inferred"))
            d["inferred"] = inferred
    return out


def _hook(topic: str) -> dict:
    hooks = creator.generate_hooks(topic, "beginner", "third", 6)
    best = max(hooks, key=lambda h: creator.score_hook(h.text, "third")["score"])
    sc = creator.score_hook(best.text, "third")
    return {
        "text": best.text,
        "formula": best.formula,
        "on_screen": best.on_screen,
        "score": sc["score"],
        "verdict": sc["verdict"],
    }


def best_time(schedule: dict, audience: dict) -> dict:
    bt = (audience or {}).get("best_times") or []
    if bt:
        return {
            "label": f"Post around {bt[0]['label']} IST",
            "why": "That's when most of your followers are on Instagram.",
            "source": "audience",
            "source_label": SOURCE_LABEL["audience"],
            "confidence": "medium",
        }
    best = (schedule or {}).get("best")
    if best:
        return {
            "label": f"Post in the {best['label']} (IST)",
            "why": f"Your reels posted then got {best['median_multiple']}x your usual plays (n={best['n']}).",
            "source": "reels",
            "source_label": SOURCE_LABEL["reels"],
            "confidence": best["confidence"],
        }
    return {
        "label": "Try 7-9 PM IST",
        "why": "Not enough data yet. Evenings are a common starting point; post at two different times to compare.",
        "source": "reels",
        "source_label": SOURCE_LABEL["reels"],
        "confidence": "none",
    }


def recommend(
    posts_raw: Sequence[dict],
    interest_profile: dict,
    ideas: Sequence[dict],
    gaps: dict,
    schedule: dict,
    audience: dict,
    history: Sequence[dict],
    k: int = 3,
) -> dict:
    posts = with_category(posts_raw)
    perf = performance_by_category(posts)
    memory = growth.content_memory(posts)["underperformed"]
    published = [("post", f"{p.get('title') or ''} || {p.get('hook_text') or ''}", p["id"]) for p in posts]
    interest = {c["category"]: c for c in interest_profile.get("categories", [])}
    recent = utcnow() - timedelta(days=45)
    rejected_topics = {h["topic"].lower() for h in history if h.get("feedback") == "not_for_me"}
    made_topics = {h["topic"].lower() for h in history if h.get("feedback") == "made_it"}
    rejected_cats = Counter(
        h["category"]
        for h in history
        if h.get("feedback") == "not_for_me"
        and h.get("category")
        and (h.get("feedback_at") is None or h["feedback_at"] >= recent)
    )
    timing = best_time(schedule, audience)

    # Topic candidates per category: comment questions > inbox ideas > interest collections/notes > starter.
    cands: list[dict[str, Any]] = []
    for g in gaps.get("gaps", [])[:5]:
        cat, _ = categorise(g["suggested_title"] + " " + g["theme"])
        cands.append({"topic": g["suggested_title"], "category": cat, "kind": "comments", "gap": g})
    for i in ideas:
        if i.get("status") in ("published", "archived"):
            continue
        cat = i.get("pillar") or categorise(i["title"])[0]
        cands.append({"topic": i["title"], "category": cat, "kind": "ideas", "idea": i})
    for note in interest_profile.get("notes", [])[:5]:
        if note.get("note"):
            cat, _ = categorise(note["note"])
            cands.append({"topic": note["note"][:120], "category": cat, "kind": "note", "note": note})
    for cat_ in CATEGORIES:
        cands.append({"topic": STARTERS[cat_], "category": cat_, "kind": "starter"})

    scored: list[dict[str, Any]] = []
    for c in cands:
        t = c["topic"]
        if t.lower() in rejected_topics or t.lower() in made_topics:
            continue
        cat = c["category"]
        reasons: list[dict[str, Any]] = []
        flags: list[str] = []
        score = {"comments": 30, "ideas": 20, "note": 18, "starter": 0}[c["kind"]]
        if c["kind"] == "ideas" and c["idea"].get("status") in ("script", "recording", "editing", "ready"):
            score += 10
            reasons.append(
                _reason(f"Already at the {c['idea']['status']} stage in your Ideas.", "ideas", "high")
            )
        elif c["kind"] == "ideas":
            reasons.append(_reason("It's in your idea inbox.", "ideas", "high"))
        if c["kind"] == "comments":
            g = c["gap"]
            reasons.append(
                _reason(
                    f"{g['count']} comment{'s' if g['count'] != 1 else ''} on your reels asked about this "
                    f"(“{(g['comments'][0]['text'] or '')[:60]}”).",
                    "comments",
                    "medium" if g["count"] > 1 else "low",
                    g["count"],
                )
            )
        if c["kind"] == "note":
            reasons.append(_reason(f"You noted: “{c['note']['note'][:70]}”.", "interests", "high"))
        pf = perf.get(cat or "")
        if pf:
            r = pf.get("shares_per_1k_ratio")
            conf = coach._confidence(pf["n"]) if pf["n"] >= coach.MIN_N else "low"
            inf = " (topic guessed from captions)" if pf.get("inferred") else ""
            if r and r >= 1.2:
                score += min(25, int((r - 1) * 20))
                reasons.append(
                    _reason(
                        f"Your {CATEGORY_NOUN[cat]} reels get {r}x your usual shares per 1,000 people "
                        f"reached (n={pf['n']}){inf}.",
                        "reels",
                        conf,
                        pf["n"],
                    )
                )
            elif pf.get("multiple_ratio") and pf["multiple_ratio"] >= 1.2:
                score += min(20, int((pf["multiple_ratio"] - 1) * 15))
                reasons.append(
                    _reason(
                        f"Your {CATEGORY_NOUN[cat]} reels get {pf['multiple_ratio']}x your usual plays "
                        f"(n={pf['n']}){inf}.",
                        "reels",
                        conf,
                        pf["n"],
                    )
                )
        it = interest.get(cat or "")
        if it and it["share"] >= 15:
            score += min(20, it["share"] // 4)
            ev = it["evidence"][0] if it["evidence"] else ""
            reasons.append(
                _reason(
                    f"It matches what you're into: {it['share']}% of your saves/likes/notes point to "
                    f"{CATEGORY_NOUN[cat]} ({ev}). Inferred.",
                    "interests",
                    it["confidence"],
                    it["matches"],
                )
            )
        if cat and cat in memory:
            w = memory[cat]
            score -= 15
            flags.append(
                f"Your {w['label']} reels usually get {w['median']}x your usual plays (n={w['n']}). "
                "Try a fresh angle."
            )
        if rejected_cats.get(cat or "", 0):
            score -= min(60, 20 * rejected_cats[cat])
            reasons.append(
                _reason(
                    f"You said 'not for me' to {rejected_cats[cat]} recent {CATEGORY_LABEL.get(cat or '', 'similar')} "
                    "suggestion(s), so this is ranked lower.",
                    "feedback",
                    "high",
                )
            )
        dup = creator.similar(t, published, 0.45)
        if dup:
            score -= 25
            flags.append(f"Close to a reel you already posted: “{dup[0]['text'][:70]}”. Make it a part 2.")
            reasons.append(_reason("You've posted something similar before.", "memory", "high"))
        if c["kind"] == "starter" and not any(r["source"] in ("reels", "interests") for r in reasons):
            reasons.append(
                _reason(
                    "A starter topic for this category. Add ideas or import your saves for better picks.",
                    "ideas",
                    "none",
                )
            )
        confs = [r["confidence"] for r in reasons if r["source"] in ("reels", "comments", "interests")]
        overall = (
            "high"
            if "high" in confs and len(confs) >= 2
            else "medium"
            if confs and "none" not in confs
            else "low"
        )
        aud = growth.infer_audience(t, cat)
        scored.append(
            {
                "topic": t,
                "category": cat,
                "category_label": CATEGORY_LABEL.get(cat or "", "General"),
                "idea_id": c["idea"]["id"] if c["kind"] == "ideas" else None,
                "kind": c["kind"],
                "for_who": {
                    "segment": aud["audience"],
                    "label": growth.SEGMENT_LABEL.get(aud["audience"], aud["audience"]),
                    "inferred": True,
                },
                "reasons": reasons,
                "flags": flags,
                "confidence": overall,
                "rank_score": score,
            }
        )
    scored.sort(key=lambda s: -s["rank_score"])
    picked: list[dict[str, Any]] = []
    seen_cat: Counter[str] = Counter()
    for s in scored:
        if any(creator.similar(s["topic"], [("x", p["topic"], 0)], 0.6) for p in picked):
            continue
        if seen_cat[s["category"]] >= 2:
            continue
        seen_cat[s["category"]] += 1
        s["hook"] = (
            s.get("idea_id")
            and next(
                (
                    i.get("recommended_hook")
                    for i in ideas
                    if i["id"] == s["idea_id"] and i.get("recommended_hook")
                ),
                None,
            )
        ) or None
        s["hook"] = (
            {
                "text": s["hook"],
                "formula": None,
                "on_screen": None,
                "score": creator.score_hook(s["hook"], "third")["score"],
                "verdict": None,
            }
            if s["hook"]
            else _hook(s["topic"])
        )
        s["best_time"] = timing
        picked.append(s)
        if len(picked) >= k:
            break
    return {
        "items": picked,
        "inputs": {
            "reels_with_numbers": sum(1 for p in posts if p.get("views") is not None),
            "interest_items": interest_profile.get("total", 0),
            "comment_questions": gaps.get("questions_considered", 0),
            "ideas": len([i for i in ideas if i.get("status") not in ("published", "archived")]),
            "feedback": len([h for h in history if h.get("feedback")]),
        },
        "note": "Ranked from your own reels, comments, saves/likes and feedback. Not a prediction of views.",
    }


# ---------- AI writing layer ----------
# The data above decides WHAT to suggest and WHY (every number comes from the user's own records). The model only
# rewrites each pick into a sharper reel: topic, angle, hook and a plain-language summary of the given reasons.
# It never sees a chance to add numbers: anything it returns is checked, and the data's reasons are kept as-is.


class _AIPick(BaseModel):
    index: int = Field(description="Index of the pick in the input list")
    topic: str = Field(description="Specific reel topic, max 90 chars, plain English")
    angle: str = Field(description="One sentence: the take or story that makes it worth watching")
    hook: str = Field(description="Opening line, third person (e.g. 'Most beginners...'), under 14 words")
    why: str = Field(description="One sentence restating the given reasons simply; no new numbers")


class _AIPicks(BaseModel):
    picks: list[_AIPick]


_DIGITS = re.compile(r"\d+(?:\.\d+)?")


def _numbers_ok(text: str, allowed: str) -> bool:
    """The model may only repeat numbers that already appear in the evidence it was given."""
    have = set(_DIGITS.findall(allowed))
    return all(n in have for n in _DIGITS.findall(text))


def ai_enhance(items: list[dict], top_posts: Sequence[dict], interests: dict) -> tuple[list[dict], str]:
    """Rewrite data-ranked picks with the configured model. Returns (items, source). On any failure the original
    items come back unchanged with source 'data'."""
    if not items:
        return items, "data"
    evidence = [
        {
            "index": i,
            "topic": it["topic"],
            "topic_area": it.get("category_label"),
            "for_who": (it.get("for_who") or {}).get("label"),
            "reasons": [r["text"] for r in it.get("reasons", [])],
            "warnings": [f.get("text", f) if isinstance(f, dict) else f for f in it.get("flags", [])],
        }
        for i, it in enumerate(items)
    ]
    payload = {
        "creator": "@vivek_techfocus, Indian tech creator: AI, tech concepts, careers, skills for beginners",
        "picks": evidence,
        "their_best_reels": [
            {"caption_start": (p.get("caption") or p.get("title") or "")[:120], "views": p.get("views")}
            for p in top_posts
        ],
        "what_they_like": [c.get("label") for c in (interests.get("categories") or [])[:4]],
    }
    res, src = creator.generate_with_model(
        "For each pick, keep its subject but turn it into one specific, timely reel a beginner would share. "
        "Return one entry per pick with the same index. Use ONLY facts in the input: never invent numbers, "
        "stats, dates or trends. Hooks in third person, no hype words, no em dashes, Indian everyday examples.",
        payload,
        _AIPicks,
        lambda: None,
    )
    if res is None or not isinstance(res, _AIPicks):
        return items, "data"
    allowed = json.dumps(payload, ensure_ascii=False)
    by_index = {p.index: p for p in res.picks}
    out = []
    for i, it in enumerate(items):
        p = by_index.get(i)
        if p is None or not p.topic.strip() or not all(
            _numbers_ok(t, allowed) for t in (p.topic, p.angle, p.hook, p.why)
        ):
            out.append(it)  # keep the data version of this pick
            continue
        sc = creator.score_hook(p.hook, "third")
        out.append(
            {
                **it,
                "data_topic": it["topic"],
                "topic": p.topic.strip()[:200],
                "angle": p.angle.strip(),
                "ai_why": p.why.strip(),
                "hook": {
                    "text": p.hook.strip(),
                    "formula": None,
                    "on_screen": None,
                    "score": sc["score"],
                    "verdict": sc["verdict"],
                },
                "written_by": src,
            }
        )
    return out, src
