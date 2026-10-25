"""Growth helpers computed only from the account's own data (synced, manual or demo).

Audience segments, shareability estimate, content fatigue, comment gaps, voice lint, reel scripts, posting
windows and the daily shortlist. Nothing here predicts followers or virality, nothing reads other accounts,
and every number that comes from posts carries its sample size and a confidence label."""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel

from ..models import AUDIENCE_SEGMENTS
from . import coach, creator
from .analytics import IST

# ---------------- audience segments ----------------

SEGMENT_LABEL = {
    "beginners": "Beginners",
    "developers": "Developers",
    "ai_enthusiasts": "AI enthusiasts",
    "students": "Students",
    "career": "Career switchers & job seekers",
}

SEGMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "career": (
        "interview",
        "resume",
        "cv",
        "job",
        "jobs",
        "career",
        "salary",
        "hiring",
        "hr",
        "placement",
        "fresher",
        "freshers",
        "degree",
        "role",
        "linkedin",
        "offer",
        "promotion",
        "cover letter",
        "manager",
    ),
    "students": (
        "student",
        "students",
        "college",
        "exam",
        "semester",
        "btech",
        "b.tech",
        "campus",
        "marks",
        "internship",
        "final year",
        "assignment",
    ),
    "developers": (
        "developer",
        "engineer",
        "software",
        "api",
        "apis",
        "rest",
        "graphql",
        "backend",
        "frontend",
        "database",
        "sql",
        "docker",
        "kubernetes",
        "aws",
        "cloud",
        "git",
        "vs code",
        "coders",
        "coding",
        "production",
        "latency",
        "system design",
        "devops",
        "deploy",
        "shortcuts",
        "debug",
    ),
    "ai_enthusiasts": (
        "ai",
        "chatgpt",
        "gpt",
        "llm",
        "prompt",
        "prompts",
        "claude",
        "gemini",
        "copilot",
        "agent",
        "agents",
        "machine learning",
        "genai",
    ),
    "beginners": (
        "beginner",
        "beginners",
        "basics",
        "explained",
        "simple",
        "what is",
        "chai",
        "non-tech",
        "non-cs",
        "never coded",
        "everyday",
        "₹",
        "upi",
    ),
}
CATEGORY_DEFAULT = {
    "ai": "ai_enthusiasts",
    "career": "career",
    "tech_concepts": "beginners",
    "skills": "career",
    "relatable_learning": "students",
}


def _hits(text: str, words: Sequence[str]) -> list[str]:
    t = f" {text.lower()} "
    out = []
    for w in words:
        if w == "₹":
            if "₹" in t:
                out.append(w)
        elif re.search(rf"(?<![a-z0-9]){re.escape(w)}s?(?![a-z0-9])", t):
            out.append(w)
    return out


def infer_audience(text: str | None, category: str | None = None) -> dict:
    """Keyword vote, with the topic category as a tie-breaker. The user can always override it."""
    text = text or ""
    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for seg, words in SEGMENT_KEYWORDS.items():
        h = _hits(text, words)
        matched[seg] = h
        scores[seg] = len(h)
    default = CATEGORY_DEFAULT.get(category or "")
    if default:
        scores[default] += 0.5
    best = max(AUDIENCE_SEGMENTS, key=lambda s: (scores[s], s == default))
    if scores[best] == 0:
        best = default or "beginners"
        reason = f"default for {coach._p(category)} posts" if default else "no strong signal, defaulted"
    elif matched[best]:
        reason = "mentions " + ", ".join(f"“{w}”" for w in matched[best][:3])
    else:
        reason = f"default for {coach._p(category)} posts"
    return {"audience": best, "label": SEGMENT_LABEL[best], "inferred": True, "reason": reason}


def audience_of(item: dict) -> dict:
    """Stored tag if the user set one, otherwise the inferred default."""
    if item.get("audience") in SEGMENT_LABEL:
        a = item["audience"]
        return {"audience": a, "label": SEGMENT_LABEL[a], "inferred": False, "reason": "set by you"}
    text = " ".join(str(item.get(k) or "") for k in ("title", "hook_text", "caption", "recommended_hook"))
    return infer_audience(text, item.get("pillar") or item.get("category"))


def _views_per_1k(p: dict) -> float | None:
    return round(p["views"] / p["reach"] * 1000, 1) if p.get("views") is not None and p.get("reach") else None


def segment_performance(posts_raw: Sequence[dict]) -> dict:
    posts = coach.enrich(posts_raw)
    for p in posts:
        a = audience_of(p)
        p["segment"], p["segment_inferred"] = a["audience"], a["inferred"]
        p["views_per_1k_reach"] = _views_per_1k(p)
    rows: list[dict[str, Any]] = []
    for seg in AUDIENCE_SEGMENTS:
        grp = [p for p in posts if p["segment"] == seg]
        if not grp:
            continue
        n = len([p for p in grp if p.get("reach")])

        def med(k: str, g: list[dict] = grp) -> float | None:
            v = [p[k] for p in g if p.get(k) is not None]
            return round(statistics.median(v), 1) if v else None

        rows.append(
            {
                "segment": seg,
                "label": SEGMENT_LABEL[seg],
                "n": n,
                "posts": len(grp),
                "inferred": sum(1 for p in grp if p["segment_inferred"]),
                "shares_per_1k": med("shares_per_1k"),
                "saves_per_1k": med("saves_per_1k"),
                "views_per_1k_reach": med("views_per_1k_reach"),
                "confidence": coach._confidence(n) if n >= coach.MIN_N else "too early",
            }
        )
    rows.sort(key=lambda r: -(r["shares_per_1k"] or 0))
    solid = [r for r in rows if r["n"] >= coach.MIN_N and r["shares_per_1k"] is not None]
    headline = None
    if len(solid) >= 2 and solid[-1]["shares_per_1k"]:
        b, w = solid[0], solid[-1]
        headline = (
            f"Posts for {b['label'].lower()} get {b['shares_per_1k']} shares per 1K reached (n={b['n']}), "
            f"vs {w['shares_per_1k']} for {w['label'].lower()} (n={w['n']})."
        )
    return {
        "segments": rows,
        "headline": headline,
        "note": "Segments are tags on your own posts (inferred from topic and wording unless you set them). "
        "This is not follower demographics.",
    }


# ---------------- shareability ----------------

_FEATURES: dict[str, list[tuple[str, str, int]]] = {
    # (regex, reason, points)
    "relatability": [
        (r"\b(you|your|you're)\b", "talks to the viewer", 15),
        (r"\b(most|every|all of us|we all|everyone)\b", "names a group people see themselves in", 15),
        (
            r"\b(freeze|fail|failed|stuck|confus\w*|overthink\w*|scared|struggl\w*|mistake\w*|panic|hate)\b",
            "names a feeling or struggle",
            25,
        ),
        (
            r"(₹|\bchai\b|\bupi\b|\bcollege\b|\binterview\w*\b|\bboss\b|\bjob\b|\bexam\b)",
            "everyday Indian context",
            20,
        ),
        (r"\b(i|my|me)\b", "personal story", 10),
    ],
    "usefulness": [
        (r"\b\d+\b", "a concrete number", 15),
        (
            r"\b(how|steps?|tips?|shortcuts?|tools?|template|checklist|roadmap|prompts?|guide)\b",
            "practical how-to",
            25,
        ),
        (r"\b(explain\w*|in \d+ seconds|simple|basics)\b", "promises a clear explanation", 15),
        (r"\b(save|use|fix|avoid|answer)\b", "something to act on", 15),
        (
            r"\b(api|aws|sql|git|vs code|chatgpt|ai|graphql|rest|cloud|python)\b",
            "names a real skill or tool",
            10,
        ),
    ],
    "curiosity": [
        (r"\?", "asks a question", 20),
        (r"\b(why|what if|secret|actually|nobody|no one|real reason|truth)\b", "opens a loop", 25),
        (r"\b(doesn't|don't|isn't|not|never|stop|wrong)\b", "contradicts an assumption", 20),
        (r"\b(vs|versus|before|after|same task)\b", "sets up a comparison", 15),
    ],
    "share_trigger": [
        (r"\b(send|tag|share|friend|someone who|your team|batchmate)\b", "built-in reason to send it", 30),
        (
            r"\b(every|most) (student|developer|engineer|fresher|beginner|coder)s?\b",
            "identity people share",
            25,
        ),
        (r"\b(degree|salary|job|interview|career|placement)\b", "career stakes people talk about", 20),
        (r"\b(doesn't|isn't|not|myth|wrong|stop)\b", "a take people want to discuss", 15),
    ],
}
SUB_LABEL = {
    "relatability": "Relatable",
    "usefulness": "Useful",
    "curiosity": "Curiosity",
    "share_trigger": "Reason to send",
}
_TIPS = {
    "relatability": "Name who it's for or the struggle (“Most freshers freeze when…”).",
    "usefulness": "Promise one concrete takeaway (a number, a step, a tool).",
    "curiosity": "Open a loop: a why-question or a common belief you'll flip.",
    "share_trigger": "Give a reason to send it: “send this to the friend who…”.",
}


def shareability(
    text: str, category: str | None = None, fmt: str | None = None, posts: Sequence[dict] = ()
) -> dict:
    """Heuristic 0-100 from wording, then a reality check against the account's own shares per 1K reach."""
    t = text.strip()
    subs: dict[str, dict] = {}
    for key, feats in _FEATURES.items():
        score, reasons = 20, []
        for rx, reason, pts in feats:
            if re.search(rx, t, re.I):
                score += pts
                reasons.append(reason)
        subs[key] = {"label": SUB_LABEL[key], "score": min(100, score), "reasons": reasons}
    overall = round(sum(s["score"] for s in subs.values()) / len(subs))
    weakest = min(subs, key=lambda k: subs[k]["score"])
    calib = calibrate(category, fmt, posts)
    return {
        "score": overall,
        "band": "high" if overall >= 65 else "medium" if overall >= 45 else "low",
        "subscores": subs,
        "tip": _TIPS[weakest] if subs[weakest]["score"] < 60 else None,
        "calibration": calib,
        "note": "An estimate from the wording only. It is not a prediction of shares, views or followers.",
    }


def calibrate(category: str | None, fmt: str | None, posts: Sequence[dict]) -> dict | None:
    """'Your similar posts averaged X shares/1k', only when n >= 3 for that group."""
    if not posts:
        return None
    enriched = coach.enrich(posts)
    overall = coach._med(enriched, "shares_per_1k")
    out = []
    for key, val, word in (("pillar", category, coach._p(category)), ("format_style", fmt, coach._p(fmt))):
        if not val:
            continue
        v = [p["shares_per_1k"] for p in enriched if p.get(key) == val and p.get("shares_per_1k") is not None]
        if len(v) >= 3:
            m = round(statistics.median(v), 1)
            out.append(
                {
                    "by": "topic" if key == "pillar" else "format",
                    "group": val,
                    "label": word,
                    "n": len(v),
                    "median_shares_per_1k": m,
                    "account_median": overall,
                    "confidence": coach._confidence(len(v)),
                    "text": f"Your {word} posts averaged {m} shares per 1K reached (n={len(v)})"
                    + (f", vs {overall} across all your posts." if overall is not None else "."),
                }
            )
    return {"groups": out, "account_median": overall} if out else None


# ---------------- content fatigue ----------------


def _ts(p: dict) -> datetime:
    v = p.get("published_at")
    if isinstance(v, str):
        v = datetime.fromisoformat(v)
    if not isinstance(v, datetime):
        return datetime.min.replace(tzinfo=UTC)
    return v if v.tzinfo else v.replace(tzinfo=UTC)


FATIGUE_TIPS = {
    "pillar": "Mix in a different topic next, or come at {label} from a new angle (story, myth, comparison).",
    "format_style": "Try one post in another format next ({alt}).",
    "hook_style": "Open the next one with a different hook formula.",
    "segment": "Make one post for a different audience segment this week.",
}


def fatigue(posts_raw: Sequence[dict], window: int = 6) -> dict:
    posts = coach.enrich(posts_raw)
    for p in posts:
        p["segment"] = audience_of(p)["audience"]
    ordered = sorted(posts, key=_ts, reverse=True)
    recent = ordered[:window]
    repetitive: list[dict] = []
    if len(recent) >= 4:
        need = max(3, (len(recent) + 1) // 2)
        for key, dim in (
            ("pillar", "topic"),
            ("format_style", "format"),
            ("hook_style", "hook"),
            ("segment", "audience"),
        ):
            c = Counter(p.get(key) for p in recent if p.get(key))
            if not c:
                continue
            grp, cnt = c.most_common(1)[0]
            if cnt >= need:
                label = SEGMENT_LABEL.get(str(grp), coach._p(grp)) if key == "segment" else coach._p(grp)
                alt = ", ".join(
                    coach._p(f) for f in ("talking_head", "motion_graphics", "carousel") if f != grp
                )
                repetitive.append(
                    {
                        "dimension": dim,
                        "group": grp,
                        "label": label,
                        "count": cnt,
                        "of": len(recent),
                        "headline": f"{cnt} of your last {len(recent)} posts used the same {dim}: {label}.",
                        "suggestion": FATIGUE_TIPS[key].format(label=label, alt=alt),
                    }
                )
    # Near-duplicate hooks/titles among recent posts.
    dupes = []
    for i, p in enumerate(recent):
        cands = [
            ("post", f"{q.get('title') or ''} {q.get('hook_text') or ''}", q["id"])
            for q in recent[i + 1 :]
            if q.get("id") is not None
        ]
        for s in creator.similar(f"{p.get('title') or ''} {p.get('hook_text') or ''}", cands, 0.45):
            dupes.append({"post_id": p.get("id"), "title": p.get("title"), "similar_to": s})
    # Topics/formats trending down vs their own earlier median (one-off hits left out).
    declining: list[dict] = []
    typical = [p for p in sorted(posts, key=_ts) if (p.get("multiple") or 0) < 3]
    for key, dim in (("pillar", "topic"), ("format_style", "format")):
        groups: dict[str, list[dict]] = defaultdict(list)
        for p in typical:
            if p.get(key):
                groups[p[key]].append(p)
        for grp, ps in groups.items():
            for metric, noun in (("multiple", "views"), ("shares_per_1k", "shares per 1K")):
                vals = [p[metric] for p in ps if p.get(metric) is not None]
                if len(vals) < 4:
                    continue
                early, late = vals[:-2], vals[-2:]
                em, lm = statistics.median(early), statistics.median(late)
                if em > 0 and lm < 0.75 * em:
                    declining.append(
                        {
                            "dimension": dim,
                            "group": grp,
                            "label": coach._p(grp),
                            "metric": noun,
                            "earlier_median": round(em, 2),
                            "recent_median": round(lm, 2),
                            "n": len(vals),
                            "confidence": coach._confidence(len(early)) if len(early) >= 2 else "low",
                            "headline": f"Your last 2 {coach._p(grp)} posts are down on {noun}: "
                            f"{round(lm, 2)} vs {round(em, 2)} before (n={len(vals)}).",
                            "suggestion": "Give it a rest for a week, or change the angle/hook before the next one.",
                        }
                    )
                    break
    return {
        "window": len(recent),
        "repetitive": repetitive,
        "near_duplicates": dupes[:5],
        "declining": declining,
        "ok": not (repetitive or dupes or declining),
        "note": f"Looks at your last {len(recent)} posts and compares each topic/format with its own earlier posts.",
    }


# ---------------- opportunity gaps (own comments only) ----------------

_GENERIC = set(
    """make video reel post explain explained please plz pls can could you also too like this that part
    how why what when where which who should would do does did kya ye ke liye bhi hai karega kaise kare bhai
    sir bro thanks thank much really very good great nice amazing helpful one more next about on in
    then sometimes always mine took day days actually first start get got say know answer from want need
    there their them they here have has had will just some any it's i'm don't best long be alway fresher kaam work""".split()
)


def _kw(text: str) -> set[str]:
    return {
        w
        for w in creator._tokens(text)
        if (w not in _GENERIC and len(w) >= 3) or w in ("ai", "cs", "hr", "cv")
    }


def _joins(kw: set[str], terms: set[str]) -> bool:
    shared = kw & terms
    return len(shared) >= 2 or (bool(shared) and len(shared) / len(kw) >= 0.3)


def opportunity_gaps(comments: Sequence[dict], covered_by: Sequence[tuple[str, str, int]]) -> dict:
    """Cluster question/request comments by shared keywords, mark which a post or idea already covers."""
    qs = [c for c in comments if c.get("intent") in ("question", "request")]
    clusters: list[dict] = []
    for c in sorted(qs, key=lambda c: -(c.get("like_count") or 0)):
        kw = _kw(c.get("text") or "")
        if not kw:
            continue
        home = next((cl for cl in clusters if _joins(kw, set(cl["terms"]))), None)
        if home is None:
            home = {"terms": Counter(), "comments": []}
            clusters.append(home)
        home["terms"].update(kw)
        home["comments"].append(c)
    cand_kw = [(kind, text, ident, _kw(text.replace(" || ", " "))) for kind, text, ident in covered_by]
    out: list[dict[str, Any]] = []
    for cl in clusters:
        terms: Counter = cl["terms"]
        top = [t for t, _ in terms.most_common(4)]
        cov = None
        for kind, text, ident, k in cand_kw:
            shared = k & set(terms)
            # Covered when a post/idea shares the theme's main word, or two of its words.
            if len(shared) >= 2 or (top and top[0] in shared):
                cov = {
                    "kind": kind,
                    "id": ident,
                    "text": text.split(" || ")[0][:120],
                    "shared": sorted(shared),
                }
                break
        idea_ids = [c["idea_id"] for c in cl["comments"] if c.get("idea_id")]
        if cov is None and idea_ids:
            cov = {"kind": "idea", "id": idea_ids[0], "text": "Saved from these comments", "shared": []}
        likes = sum(c.get("like_count") or 0 for c in cl["comments"])
        lead = cl["comments"][0]
        out.append(
            {
                "theme": " · ".join(top[:3]),
                "count": len(cl["comments"]),
                "likes": likes,
                "score": len(cl["comments"]) * 10 + likes,
                "covered": cov is not None,
                "covered_by": cov,
                "suggested_title": _idea_title(lead.get("text") or ""),
                "comments": [
                    {
                        "id": c.get("id"),
                        "username": c.get("username"),
                        "text": c.get("text"),
                        "like_count": c.get("like_count"),
                    }
                    for c in cl["comments"][:5]
                ],
            }
        )
    out.sort(key=lambda g: (g["covered"], -g["score"]))
    return {
        "gaps": [g for g in out if not g["covered"]],
        "covered": [g for g in out if g["covered"]],
        "questions_considered": len(qs),
        "note": "Built only from comments on your own posts (questions and requests). No other accounts are read.",
    }


def _idea_title(text: str) -> str:
    from .activity import idea_title_from

    return idea_title_from(text)


# ---------------- brand voice ----------------

DEFAULT_VOICE: dict[str, Any] = {
    "tone_words": ["simple", "friendly", "practical"],
    "banned_words": ["game-changer", "revolutionary", "unlock", "delve", "mind-blowing"],
    "preferred_cta": "Save this for later",
    "signature_hashtags": ["#techindia", "#techexplained"],
    "emoji_level": "low",
}
EMOJI_LIMIT = {"none": 0, "low": 2, "medium": 5, "high": 10}
_EMOJI = re.compile("[\U0001f300-\U0001faff☀-➿⭐✅]")
_CLAIMS = re.compile(
    r"\b(always|never|100%|guaranteed?|zero bugs|the only way|everyone knows|instantly|works every time)\b|100%",
    re.I,
)


def voice_profile(stored: dict | None) -> dict:
    return {**DEFAULT_VOICE, **(stored or {})}


def lint_voice(text: str, profile: dict) -> dict:
    p = voice_profile(profile)
    issues: list[dict] = []
    low = text.lower()
    for w in p.get("banned_words") or []:
        if w and re.search(rf"(?<![a-z]){re.escape(w.lower())}(?![a-z])", low):
            issues.append(
                {
                    "kind": "banned_word",
                    "severity": "high",
                    "message": f"Uses “{w}”, which is on your banned list.",
                }
            )
    seen: set[str] = set()
    for m in _CLAIMS.finditer(text):
        word = m.group(0).lower()
        if word in seen:
            continue
        seen.add(word)
        issues.append(
            {
                "kind": "claim",
                "severity": "medium",
                "message": f"“{m.group(0)}” is an absolute claim. Tech has exceptions; say “usually” or show proof.",
            }
        )
    if "—" in text:
        issues.append(
            {
                "kind": "style",
                "severity": "low",
                "message": "Em dash found. It reads machine-written; use a full stop or comma.",
            }
        )
    emojis = len(_EMOJI.findall(text))
    limit = EMOJI_LIMIT.get(str(p.get("emoji_level")), 2)
    if emojis > limit:
        issues.append(
            {
                "kind": "emoji",
                "severity": "low",
                "message": f"{emojis} emojis; your voice allows about {limit}.",
            }
        )
    cta = (p.get("preferred_cta") or "").strip()
    if cta and cta.lower() not in low:
        issues.append({"kind": "cta", "severity": "low", "message": f"Your usual ask is missing: “{cta}”."})
    tags = re.findall(r"#\w+", text)
    sig = [t.lower() for t in (p.get("signature_hashtags") or [])]
    missing = [t for t in sig if t not in {x.lower() for x in tags}]
    if missing:
        issues.append(
            {
                "kind": "hashtags",
                "severity": "low",
                "message": "Missing your signature hashtags: " + " ".join(missing),
            }
        )
    if len(tags) > 5:
        issues.append(
            {
                "kind": "hashtags",
                "severity": "low",
                "message": f"{len(tags)} hashtags. 3-5 relevant ones is plenty.",
            }
        )
    weight = {"high": 25, "medium": 12, "low": 5}
    score = max(0, 100 - sum(weight[i["severity"]] for i in issues))
    return {
        "score": score,
        "ok": not any(i["severity"] != "low" for i in issues),
        "issues": issues,
        "profile": p,
    }


# ---------------- reel script ----------------


class ScriptBeat(BaseModel):
    start: int
    end: int
    label: str
    voiceover: str
    on_screen: str
    visual: str


class ReelScript(BaseModel):
    topic: str
    audience: str
    duration_seconds: int
    hook: str
    beats: list[ScriptBeat]
    caption: str
    shot_list: list[str]


def reel_script(
    topic: str,
    audience: creator.Audience = "beginner",
    hook: str | None = None,
    duration: int = 30,
    category: str = "tech_concepts",
) -> ReelScript:
    base = creator.repurpose(topic, audience, hook)
    t = topic.strip().rstrip(".?!")
    hook_text = base.reel_30s[0]["say"]
    k = duration / 30
    marks = [0, 3, round(8 * k), round(18 * k), round(25 * k), duration]
    beats_src = [
        (
            "Hook",
            hook_text,
            creator._on_screen(hook_text),
            "Face to camera, tight framing, start mid-sentence. No intro.",
        ),
        (
            "Problem",
            f"Here's where most {'people' if audience == 'beginner' else 'developers'} get stuck with {t}.",
            "THE CONFUSING PART",
            "Quick cut to a screen recording or a whiteboard scribble of the confusing bit.",
        ),
        (
            "Explain",
            base.reel_30s[1]["say"],
            base.reel_30s[1]["screen"],
            "B-roll of the everyday example (chai stall, phone, laptop) with a simple arrow graphic.",
        ),
        (
            "Example",
            base.reel_30s[2]["say"],
            base.reel_30s[2]["screen"],
            "Screen recording or motion graphic showing the real example step by step.",
        ),
        (
            "Payoff + ask",
            base.reel_30s[3]["say"],
            base.reel_30s[3]["screen"],
            "Back to face cam, point to the save button; end on the takeaway line.",
        ),
    ]
    beats = [
        ScriptBeat(start=marks[i], end=marks[i + 1], label=lab, voiceover=say, on_screen=scr, visual=vis)
        for i, (lab, say, scr, vis) in enumerate(beats_src)
    ]
    cap = creator.generate_caption(t, hook_text, category, audience).full
    shots = [
        "A-roll: face cam, eye level, window light",
        "Screen recording or whiteboard close-up for the problem",
        f"B-roll: everyday example for {t}",
        "Text overlays: one line per beat, max 5 words",
    ]
    return ReelScript(
        topic=t,
        audience=audience,
        duration_seconds=duration,
        hook=hook_text,
        beats=beats,
        caption=cap,
        shot_list=shots,
    )


# ---------------- posting windows ----------------

WINDOWS = [
    ("late night (12-6 AM)", 0, 6),
    ("morning (6-11 AM)", 6, 11),
    ("midday (11 AM-3 PM)", 11, 15),
    ("afternoon (3-6 PM)", 15, 18),
    ("evening (6-9 PM)", 18, 21),
    ("night (9 PM-12 AM)", 21, 24),
]
CONF_WORD = {"high": "strong", "medium": "likely", "low": "early hunch"}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _window(h: int) -> str:
    return next(lab for lab, a, b in WINDOWS if a <= h < b)


def posting_windows(posts_raw: Sequence[dict], online: dict[str, int] | None = None) -> dict:
    posts = coach.enrich(posts_raw)
    rows: list[dict[str, Any]] = []
    for p in posts:
        if p.get("published_at") is None or p.get("multiple") is None:
            continue
        local = _ts(p).astimezone(IST)
        rows.append({**p, "window": _window(local.hour), "weekday": DAYS[local.weekday()]})
    typical = [r for r in rows if r["multiple"] < 3]

    def table(key: str, order: list[str]) -> list[dict]:
        out: list[dict[str, Any]] = []
        for g in order:
            grp = [r for r in typical if r[key] == g]
            if not grp:
                continue
            sh = [r["shares_per_1k"] for r in grp if r.get("shares_per_1k") is not None]
            out.append(
                {
                    "label": g,
                    "n": len(grp),
                    "median_multiple": round(statistics.median([r["multiple"] for r in grp]), 2),
                    "median_shares_per_1k": round(statistics.median(sh), 1) if sh else None,
                    "confidence": coach._confidence(len(grp)) if len(grp) >= coach.MIN_N else "too early",
                }
            )
        return out

    windows = table("window", [w[0] for w in WINDOWS])
    days = table("weekday", DAYS)
    from .activity import best_hours_ist

    online_best = best_hours_ist(online or {}, 0)
    solid = sorted([w for w in windows if w["n"] >= coach.MIN_N], key=lambda w: -w["median_multiple"])
    rec = None
    if solid:
        b = solid[0]
        rec = (
            f"Your {b['label']} posts usually get {b['median_multiple']}x your usual views "
            f"(n={b['n']}, {CONF_WORD.get(b['confidence'], b['confidence'])})."
        )
    if online_best:
        rec = (
            rec + " " if rec else ""
        ) + f"Your followers are most online around {online_best[0]['label']} IST."
    return {
        "windows": windows,
        "weekdays": days,
        "online_peaks": online_best,
        "best": solid[0] if solid else None,
        "recommendation": rec or "Not enough posts yet. Post at two different times this week to compare.",
        "sample_size": len(typical),
        "note": "From your own post history (one-off hits left out) and Instagram's online_followers when "
        "available. Publishing still needs your approval.",
    }


# ---------------- daily shortlist (strategist + content memory) ----------------

STAGE_BONUS = {"ready": 15, "editing": 12, "recording": 10, "script": 6, "idea": 0}


def content_memory(posts_raw: Sequence[dict]) -> dict:
    posts = [p for p in coach.enrich(posts_raw) if (p.get("multiple") or 0) < 3]
    weak: dict[str, dict] = {}
    for key in ("pillar", "format_style"):
        for r in coach.group_stats(posts, key, "multiple"):
            if r["n"] >= coach.MIN_N and r["median"] < 0.75:
                weak[r["group"]] = {
                    "key": key,
                    "label": r["label"],
                    "median": r["median"],
                    "n": r["n"],
                    "confidence": coach._confidence(r["n"]),
                }
    return {"underperformed": weak}


def shortlist(ideas: Sequence[dict], posts: Sequence[dict], k: int = 3) -> dict:
    analysis = coach.analyse(posts)
    med = analysis["summary"]["median_shares_per_1k"]
    memory = content_memory(posts)
    weak = memory["underperformed"]
    published = [("post", f"{p.get('title') or ''} || {p.get('hook_text') or ''}", p["id"]) for p in posts]
    scored = []
    for i in ideas:
        if i.get("status") in ("published", "archived"):
            continue
        text = i.get("recommended_hook") or i["title"]
        sh = shareability(text, i.get("pillar"), i.get("format"), posts)
        aud = audience_of(i)
        flags: list[dict[str, Any]] = []
        why: list[str] = []
        score = sh["score"] + STAGE_BONUS.get(i.get("status") or "idea", 0)
        for key in ("pillar", "format"):
            g = i.get(key)
            if g and g in weak:
                w = weak[g]
                flags.append(
                    {
                        "kind": "underperformed",
                        "message": f"Your {w['label']} posts usually get {w['median']}x your usual views (n={w['n']}). "
                        "Change the angle or format before posting.",
                    }
                )
                score -= 15
        dup = creator.similar(f"{i['title']} {i.get('recommended_hook') or ''}", published, 0.4)
        if dup:
            flags.append(
                {
                    "kind": "near_duplicate",
                    "message": f"Very close to a post you already published: “{dup[0]['text']}”. "
                    "Make it a part 2 or a new angle.",
                    "similar": dup[0],
                }
            )
            score -= 20
        if i.get("status") in ("ready", "editing", "recording"):
            why.append(f"Already at the {i['status']} stage, so it's the fastest to ship.")
        if sh["calibration"]:
            why.append(sh["calibration"]["groups"][0]["text"])
        top_sub = max(sh["subscores"].values(), key=lambda s: s["score"])
        if top_sub["reasons"]:
            why.append(f"{top_sub['label']}: {top_sub['reasons'][0]}.")
        watch = (
            {
                "metric": "shares_per_1k",
                "target": med,
                "text": f"Shares per 1K reached above your median {med}",
            }
            if med is not None
            else {
                "metric": "shares_per_1k",
                "target": None,
                "text": "Shares per 1K reached (log a few posts to get a baseline)",
            }
        )
        scored.append(
            {
                "idea_id": i["id"],
                "title": i["title"],
                "status": i.get("status"),
                "category": i.get("pillar"),
                "hook": i.get("recommended_hook"),
                "audience": aud,
                "shareability": {"score": sh["score"], "band": sh["band"], "tip": sh["tip"]},
                "why": why or ["From your idea inbox."],
                "flags": flags,
                "watch": watch,
                "rank_score": score,
            }
        )
    scored.sort(key=lambda s: -s["rank_score"])
    return {
        "items": scored[:k],
        "memory": {
            "avoid": [{"group": g, **w} for g, w in sorted(weak.items(), key=lambda kv: kv[1]["median"])],
            "baseline_shares_per_1k": med,
            "sample_size": analysis["sample_size"],
        },
        "note": "Ranked by stage, wording (shareability estimate) and what has worked on your own posts. "
        "No follower predictions.",
    }


# ---------------- attribution ----------------


def attribution(p: dict) -> dict:
    is_reel = (p.get("media_product_type") or "").upper() == "REELS"
    vals = {k: p.get(k) for k in ("follows", "profile_visits", "profile_activity", "reposts")}
    if is_reel:
        return {
            "available": False,
            "reposts": vals["reposts"],
            "note": "Instagram doesn't report follows or profile visits for Reels.",
        }
    have = any(vals[k] is not None for k in ("follows", "profile_visits", "profile_activity"))
    return {
        "available": have,
        **vals,
        "note": None if have else "Instagram hasn't reported follows/profile visits for this post yet.",
    }
