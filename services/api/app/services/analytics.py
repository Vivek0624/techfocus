"""Derived metrics. Each returns None (unavailable) when its source fields are missing.
Formulas and denominators are documented in docs/metrics.md and exposed via METRIC_DEFINITIONS."""

from __future__ import annotations

import random
import statistics
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

METRIC_DEFINITIONS = {
    "net_follower_growth": "followers(end) - followers(start). Requires a follower snapshot on both dates.",
    "pct_follower_growth": "net_follower_growth / followers(start) x 100.",
    "reach_per_post": "sum(media.reach) / count(media with reach). Reach = unique accounts, not views.",
    "engagement_rate_by_reach": "median over posts of (likes+comments+shares+saved) / reach x 100.",
    "follows_per_1k_reach": "sum(daily follows) / sum(daily account reach) x 1000. Account-level; "
    "the API does not attribute follows to individual posts.",
    "outlier_multiple": "post views / median views of the account's other posts in the window.",
    "required_daily_net_growth": "(target - current followers) / days remaining (min 1).",
}

WINDOWS = [("06-10", 6, 10), ("10-14", 10, 14), ("14-18", 14, 18), ("18-22", 18, 22), ("22-06", 22, 30)]


def _ok(*vals) -> bool:
    return all(v is not None for v in vals)


def net_growth(start: int | None, end: int | None) -> int | None:
    return end - start if _ok(start, end) else None  # type: ignore[operator]


def pct_growth(start: int | None, end: int | None) -> float | None:
    if not _ok(start, end) or not start:
        return None
    return round((end - start) / start * 100, 2)  # type: ignore[operator]


def reach_per_post(reaches: Iterable[int | None]) -> float | None:
    vals = [r for r in reaches if r is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def engagement_rate_by_reach(posts: Iterable[dict]) -> float | None:
    rates = []
    for p in posts:
        parts = [p.get(k) for k in ("likes", "comments", "shares", "saved")]
        reach = p.get("reach")
        if reach and all(x is not None for x in parts):
            rates.append(sum(parts) / reach * 100)  # type: ignore[arg-type]
    return round(statistics.median(rates), 2) if rates else None


def follows_per_1k_reach(days: Iterable[dict]) -> float | None:
    f = r = 0
    seen = False
    for d in days:
        if d.get("follows") is not None and d.get("reach"):
            f += d["follows"]
            r += d["reach"]
            seen = True
    return round(f / r * 1000, 2) if seen and r else None


def outlier_multiples(posts: Sequence[dict]) -> list[dict]:
    """Views relative to the median of the *other* posts (so a breakout does not raise its own baseline)."""
    out = []
    views = [p.get("views") for p in posts]
    for i, p in enumerate(posts):
        v = views[i]
        others = [x for j, x in enumerate(views) if j != i and x is not None]
        if v is None or len(others) < 3:
            out.append({**p, "multiple": None})
            continue
        med = statistics.median(others)
        out.append({**p, "multiple": round(v / med, 2) if med else None})
    return out


def compare_groups(posts: Sequence[dict], key: str, metric: str = "views", min_n: int = 3) -> list[dict]:
    groups: dict[str, list[float]] = defaultdict(list)
    for p in posts:
        g, v = p.get(key), p.get(metric)
        if g and v is not None:
            groups[g].append(v)
    rows = []
    for g, vals in groups.items():
        rows.append(
            {
                "group": g,
                "n": len(vals),
                "median": statistics.median(vals),
                "enough_data": len(vals) >= min_n,
            }
        )
    return sorted(rows, key=lambda r: (-r["enough_data"], -r["median"]))


def window_of(ts: datetime) -> str:
    h = ts.astimezone(IST).hour
    for name, lo, hi in WINDOWS:
        if lo <= h < hi or lo <= h + 24 < hi:
            return name
    return "22-06"


def best_time_analysis(posts: Sequence[dict], min_n: int = 3) -> dict:
    """Compares IST windows by median outlier multiple (normalises for content quality drift)."""
    enriched = [
        {**p, "window": window_of(p["published_at"])}
        for p in outlier_multiples(posts)
        if p.get("published_at") and p.get("multiple") is not None
    ]
    rows = compare_groups(enriched, "window", "multiple", min_n)
    enough = [r for r in rows if r["enough_data"]]
    if len(enough) < 2:
        return {
            "status": "insufficient_data",
            "windows": rows,
            "recommendation": "Not enough posts per time window to compare. Run a controlled test: post the same "
            "pillar and format in two windows (e.g. 13:00 and 20:00 IST), at least "
            f"{min_n} posts each, and compare outlier multiples.",
        }
    best = enough[0]
    return {
        "status": "ok",
        "windows": rows,
        "recommendation": f"Your posts in the {best['group']} IST window have the highest median multiple "
        f"({best['median']:.2f}x, n={best['n']}). This is correlation from your own history, "
        "not a universal best time; confirm with a controlled test.",
    }


# ---------- growth target ----------


@dataclass
class TargetProgress:
    start_followers: int
    target: int
    current: int | None
    start_date: date
    end_date: date
    days_total: int
    days_elapsed: int
    days_remaining: int
    remaining: int | None
    required_per_day: float | None
    actual_per_day: float | None
    on_pace: bool | None


def target_progress(
    start_followers: int, target: int, start_date: date, days: int, current: int | None, today: date
) -> TargetProgress:
    end = start_date + timedelta(days=days)
    elapsed = max(0, min(days, (today - start_date).days))
    remaining_days = max(1, (end - today).days)
    remaining = target - current if current is not None else None
    req = round(max(0, remaining) / remaining_days, 1) if remaining is not None else None
    actual = round((current - start_followers) / elapsed, 1) if current is not None and elapsed > 0 else None
    on_pace = (actual >= (target - start_followers) / days) if actual is not None else None
    return TargetProgress(
        start_followers,
        target,
        current,
        start_date,
        end,
        days,
        elapsed,
        remaining_days,
        remaining,
        req,
        actual,
        on_pace,
    )


def scenarios(current: int, days_remaining: int, rates: Sequence[float]) -> list[dict]:
    """Illustrative arithmetic only. Not predictions."""
    return [{"daily_net": r, "projected_followers": int(current + r * days_remaining)} for r in rates]


# ---------- experiments ----------


def _perm_p(a: list[float], b: list[float], iters: int = 4000, seed: int = 7) -> float:
    obs = statistics.median(b) - statistics.median(a)
    pool = a + b
    rng = random.Random(seed)
    hits = 0
    for _ in range(iters):
        rng.shuffle(pool)
        diff = statistics.median(pool[len(a) :]) - statistics.median(pool[: len(a)])
        if abs(diff) >= abs(obs):
            hits += 1
    return (hits + 1) / (iters + 1)


def evaluate_experiment(control: list[float], variant: list[float], min_n: int) -> dict:
    res: dict = {"n_control": len(control), "n_variant": len(variant)}
    if len(control) < min_n or len(variant) < min_n:
        res.update(
            status="insufficient_data",
            confidence="none",
            note=f"Need at least {min_n} observations per arm before reading this.",
        )
        return res
    mc, mv = statistics.median(control), statistics.median(variant)
    lift = (mv - mc) / mc * 100 if mc else None
    p = _perm_p(control, variant)
    conf = "medium" if p < 0.05 and min(len(control), len(variant)) >= 5 else ("low" if p < 0.2 else "none")
    res.update(
        status="ok",
        median_control=mc,
        median_variant=mv,
        lift_pct=round(lift, 1) if lift is not None else None,
        p_value=round(p, 3),
        confidence=conf,
        note="Permutation test on medians. Posts differ in topic and timing, so treat as evidence, not proof.",
    )
    return res
