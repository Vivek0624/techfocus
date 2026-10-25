"""Analytics Coach + Content Learning Engine.

Compares the user's own posts with each other. Never predicts virality. Every finding states its sample size,
and nothing is called a pattern unless each side has at least MIN_N posts and the gap is at least GAP."""

from __future__ import annotations

import hashlib
import json
import re
import statistics
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import date

from pydantic import BaseModel, Field

MIN_N = 2
GAP = 1.3  # a group must beat the rest by 30% to be called out

LABELS = {
    "pillar": "topic",
    "hook_style": "hook",
    "format_style": "format",
    "length_bucket": "length",
}
PRETTY = {
    "ai": "AI",
    "tech_concepts": "tech concepts",
    "career": "career",
    "skills": "skills",
    "relatable_learning": "relatable learning",
    "talking_head": "talking-head",
    "motion_graphics": "motion-graphic",
    "screen_recording": "screen-recording",
    "carousel": "carousel",
}


def _p(x: str | None) -> str:
    return PRETTY.get(x or "", (x or "").replace("_", " "))


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def length_bucket(sec: int | None) -> str | None:
    if sec is None:
        return None
    return "under 20s" if sec < 20 else "20-40s" if sec < 40 else "40-60s" if sec < 60 else "over 60s"


def _per_1k(n: int | None, reach: int | None) -> float | None:
    return round(n / reach * 1000, 1) if n is not None and reach else None


def enrich(posts: Sequence[dict]) -> list[dict]:
    views = [p["views"] for p in posts if p.get("views") is not None]
    med = statistics.median(views) if views else None
    out = []
    for p in posts:
        q = dict(p)
        q["multiple"] = round(p["views"] / med, 2) if med and p.get("views") is not None else None
        q["shares_per_1k"] = _per_1k(p.get("shares"), p.get("reach"))
        q["saves_per_1k"] = _per_1k(p.get("saved"), p.get("reach"))
        q["length_bucket"] = length_bucket(p.get("length_seconds"))
        out.append(q)
    return out


def _confidence(n_min: int) -> str:
    return "high" if n_min >= 6 else "medium" if n_min >= 3 else "low"


def group_stats(posts: Sequence[dict], key: str, metric: str) -> list[dict]:
    g: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        if p.get(key) and p.get(metric) is not None:
            g[p[key]].append(p[metric])
    rows = [
        {"group": k, "label": _p(k), "n": len(v), "median": round(statistics.median(v), 2)}
        for k, v in g.items()
    ]
    return sorted(rows, key=lambda r: -r["median"])


def _winner(posts: Sequence[dict], key: str, metric: str) -> dict | None:
    """Best group vs worst group, both with >= MIN_N posts. Outliers (>=3x views) are left out:
    they get their own insight and would otherwise make one lucky post look like a pattern."""
    pool = [p for p in posts if (p.get("multiple") or 0) < 3]
    rows = [r for r in group_stats(pool, key, metric) if r["n"] >= MIN_N]
    if len(rows) < 2:
        return None
    best, worst = rows[0], rows[-1]
    if worst["median"] <= 0:
        if best["median"] <= 0:
            return None
        ratio = None
    else:
        ratio = round(best["median"] / worst["median"], 1)
        if ratio < GAP:
            return None
    return {**best, "worst": worst, "ratio": ratio, "confidence": _confidence(min(best["n"], worst["n"]))}


METRIC_WORDS: dict[str, tuple[str, Callable[[float], str]]] = {
    "multiple": ("views", lambda v: f"{v}x your usual views"),
    "shares_per_1k": ("shares", lambda v: f"{v} shares per 1,000 reached"),
    "saves_per_1k": ("saves", lambda v: f"{v} saves per 1,000 reached"),
}

ACTIONS = {
    "pillar": "Make your next post about {label} again, with a different angle.",
    "hook_style": "Open your next reel with a {label} hook.",
    "format_style": "Shoot the next one as a {label} reel.",
    "length_bucket": "Keep the next reel {label}.",
}


def analyse(posts_raw: Sequence[dict]) -> dict:
    posts = enrich(posts_raw)
    with_views = [p for p in posts if p.get("views") is not None]
    n = len(with_views)
    tagged = [p for p in posts if p.get("pillar") or p.get("hook_style") or p.get("format_style")]
    insights: list[dict] = []

    # 1. Outliers: the strongest evidence a small account has.
    for p in sorted([p for p in with_views if (p["multiple"] or 0) >= 3], key=lambda p: -p["multiple"])[:2]:
        what = ", ".join(
            x
            for x in (
                _p(p.get("pillar")),
                p.get("hook_style") and f"{p['hook_style']} hook",
                _p(p.get("format_style")),
            )
            if x
        )
        insights.append(
            {
                "kind": "outlier",
                "headline": f"“{(p.get('title') or p.get('caption') or 'A post')[:60]}” ran {p['multiple']}x your usual views.",
                "detail": f"That's one post, so it's a lead, not a rule.{' It was ' + what + '.' if what else ''}",
                "action": "Make a follow-up on the same topic within a week, and pin the original to your profile.",
                "confidence": "low",
                "evidence": {"post_id": p.get("id"), "views": p["views"], "multiple": p["multiple"]},
            }
        )

    # 2. Patterns by topic / hook / format / length, on views, shares and saves.
    patterns = []
    for key in ("pillar", "hook_style", "format_style", "length_bucket"):
        for metric in ("multiple", "shares_per_1k", "saves_per_1k"):
            w = _winner(posts, key, metric)
            if not w:
                continue
            noun, fmt = METRIC_WORDS[metric]
            wl = w["worst"]
            times = f"{w['ratio']}x more {noun}" if w["ratio"] else f"more {noun}"
            patterns.append(
                {
                    "kind": "pattern",
                    "dimension": LABELS[key],
                    "metric": noun,
                    "headline": f"Your {w['label']} posts get {times} than your {wl['label']} posts.",
                    "detail": f"{_cap(w['label'])}: median {fmt(w['median'])} (n={w['n']}). "
                    f"{_cap(wl['label'])}: {fmt(wl['median'])} (n={wl['n']}). One-off hits left out.",
                    "action": ACTIONS[key].format(label=w["label"]),
                    "confidence": w["confidence"],
                    "group": w["group"],
                    "worst_group": wl["group"],
                    "key": key,
                    "evidence": {
                        "n": w["n"],
                        "median": w["median"],
                        "worst_median": wl["median"],
                        "n_worst": wl["n"],
                    },
                }
            )
    # Keep the strongest per dimension so the coach doesn't repeat itself.
    best_per_dim: dict[tuple[str, str], dict] = {}
    rank = {"high": 3, "medium": 2, "low": 1}
    for pat in patterns:
        slot = (pat["dimension"], "views" if pat["metric"] == "views" else "engagement")
        cur = best_per_dim.get(slot)
        if cur is None or (rank[pat["confidence"]], pat["evidence"]["median"]) > (
            rank[cur["confidence"]],
            cur["evidence"]["median"],
        ):
            best_per_dim[slot] = pat
    ordered = sorted(
        best_per_dim.values(), key=lambda p: (-rank[p["confidence"]], -(p["evidence"]["median"] or 0))
    )
    insights += ordered[:5]

    # 3. Data gaps, said plainly.
    if n < 5:
        insights.append(
            {
                "kind": "data",
                "headline": f"Only {n} post{'s' if n != 1 else ''} with numbers so far.",
                "detail": "Patterns need at least 5 posts, ideally 10+. Until then, treat everything here as a hunch.",
                "action": "Post 3 more reels this week and log their results.",
                "confidence": "none",
                "evidence": {},
            }
        )
    untagged = n - len([p for p in with_views if p in tagged])
    if untagged >= 2:
        insights.append(
            {
                "kind": "data",
                "headline": f"{untagged} posts have no topic, hook or format tag.",
                "detail": "The learning engine can only compare what's tagged.",
                "action": "Tag them on the Insights page (takes a minute).",
                "confidence": "none",
                "evidence": {"untagged": untagged},
            }
        )

    # 4. Repeat / improve / stop.
    repeat = [
        f"{p['dimension'].capitalize()}: {_p(p['group'])} ({p['headline'].split(' get ')[1].rstrip('.')})"
        for p in ordered[:4]
    ]
    stop, improve = [], []
    typical = [p for p in posts if (p.get("multiple") or 0) < 3]
    for key in ("pillar", "hook_style", "format_style"):
        for r in group_stats(typical, key, "multiple"):
            if r["n"] >= MIN_N and r["median"] < 0.75:
                stop.append(
                    f"{LABELS[key].capitalize()}: {r['label']} (median {r['median']}x your usual views, n={r['n']})"
                )
    for p in with_views:
        if (p["multiple"] or 0) >= 1.5 and p.get("shares_per_1k") is not None and p["shares_per_1k"] < 3:
            improve.append(
                f"“{(p.get('title') or p.get('caption') or '')[:50]}” got views but few shares. "
                "Add a 'send this to a friend who...' moment."
            )

    hooks = group_stats(posts, "hook_style", "multiple")
    return {
        "sample_size": n,
        "tagged": len(tagged),
        "summary": {
            "median_views": statistics.median([p["views"] for p in with_views]) if with_views else None,
            "median_shares_per_1k": _med(posts, "shares_per_1k"),
            "median_saves_per_1k": _med(posts, "saves_per_1k"),
            "median_watch_seconds": round(m / 1000, 1) if (m := _med(posts, "avg_watch_time_ms")) else None,
        },
        "insights": insights,
        "answers": {
            "best_hooks": hooks,
            "topics_by_shares": group_stats(posts, "pillar", "shares_per_1k"),
            "formats": group_stats(posts, "format_style", "multiple"),
            "lengths": group_stats(posts, "length_bucket", "multiple"),
            "repeat": repeat or ["Not enough tagged posts yet to say."],
            "improve": improve[:3] or ["Nothing stands out yet."],
            "stop": stop or ["Nothing to stop yet. Nothing has consistently underperformed."],
        },
        "posts": posts,
        "note": "Compared against your own posts only. This shows what has worked for you, not what will go viral.",
    }


def _med(posts: Sequence[dict], k: str) -> float | None:
    v = [p[k] for p in posts if p.get(k) is not None]
    return round(statistics.median(v), 1) if v else None


# ---------- AI coach write-up ----------
# analyse() decides what is true. The model only turns that into a short, plain-language brief. Every line it writes
# is checked: a line with a number that isn't in the evidence is dropped. Cached per day per evidence, so reloading
# Insights doesn't spend the free model quota.


class _Brief(BaseModel):
    headline: str = Field(description="One sentence: the single most important thing about this account right now")
    working: list[str] = Field(description="Up to 3 short lines: what is working, citing the evidence")
    fix: list[str] = Field(description="Up to 3 short lines: what to fix or stop")
    this_week: list[str] = Field(description="Exactly 3 concrete actions for this week, each starting with a verb")


_brief_cache: dict[str, dict] = {}
_NUM = re.compile(r"\d+(?:\.\d+)?")


def _grounded(line: str, evidence: str) -> bool:
    have = set(_NUM.findall(evidence))
    return all(n in have for n in _NUM.findall(line))


def ai_brief(res: dict) -> dict:
    """Plain-language coach brief written by the configured model from analyse() output. Never raises."""
    from .creator import generate_with_model

    posts = [p for p in res.get("posts", []) if p.get("views") is not None]
    by_views = sorted(posts, key=lambda p: -(p.get("views") or 0))

    def row(p: dict) -> dict:
        return {
            "reel": (p.get("title") or p.get("caption") or "")[:80],
            "views": p.get("views"),
            "x_usual_views": p.get("multiple"),
            "shares_per_1k_reached": p.get("shares_per_1k"),
            "saves_per_1k_reached": p.get("saves_per_1k"),
            "avg_seconds_watched": round(p["avg_watch_time_ms"] / 1000, 1) if p.get("avg_watch_time_ms") else None,
        }

    evidence = {
        "posts_with_numbers": res.get("sample_size"),
        "posts_tagged": res.get("tagged"),
        "typical": res.get("summary"),
        "patterns_found": [
            {k: i.get(k) for k in ("headline", "detail", "action", "confidence")} for i in res.get("insights", [])
        ],
        "repeat": res.get("answers", {}).get("repeat"),
        "improve": res.get("answers", {}).get("improve"),
        "stop": res.get("answers", {}).get("stop"),
        "best_reels": [row(p) for p in by_views[:5]],
        "weakest_reels": [row(p) for p in by_views[-3:]] if len(by_views) > 5 else [],
    }
    text = json.dumps(evidence, ensure_ascii=False, default=str)
    key = f"{date.today()}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    if key in _brief_cache:
        return _brief_cache[key]
    out, src = generate_with_model(
        "You are a friendly Instagram coach for a beginner tech creator. Using ONLY this evidence, write a short "
        "brief in plain words (no jargon; say 'people reached' not 'reach'). Never invent numbers, trends or "
        "predictions; only repeat numbers that appear in the evidence. Mention when a pattern rests on few posts. "
        "One viral outlier is luck, not a rule. No em dashes, no hype.",
        evidence,
        _Brief,
        lambda: None,
    )
    if not isinstance(out, _Brief):
        return {"available": False, "source": "data"}

    def keep(lines: list[str], n: int) -> list[str]:
        return [ln.strip() for ln in lines if ln.strip() and _grounded(ln, text)][:n]

    brief = {
        "available": True,
        "source": src,
        "headline": out.headline.strip() if _grounded(out.headline, text) else None,
        "working": keep(out.working, 3),
        "fix": keep(out.fix, 3),
        "this_week": keep(out.this_week, 3),
        "note": "Written by AI from your own numbers. Lines with numbers not found in your data are removed.",
    }
    _brief_cache.clear()  # keep only the latest
    _brief_cache[key] = brief
    return brief
