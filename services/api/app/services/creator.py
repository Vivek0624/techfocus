"""Hooks, captions, hashtags, repurposing and duplicate detection.

Templates run offline and are deterministic. When AGENT_MODE=bedrock the same request goes to the model
(see generate_with_model) and falls back to the template on any error, so the app never blocks on AWS.
Hook scores come from the vendored ig-reel scorer: it catches weak hooks, it does not predict virality."""

from __future__ import annotations

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..config import get_settings
from .hookkit import hookscore

log = logging.getLogger(__name__)

Perspective = Literal["third", "you", "i"]
Audience = Literal["beginner", "developer"]

_FORMULAS = json.loads((Path(__file__).parent / "hookkit" / "hooks.json").read_text())
_BY_ID = {h["id"]: h for h in _FORMULAS["hooks"]}
_MATCHERS = [
    (i, re.compile(_BY_ID[i]["match"], re.I)) for i in _FORMULAS["classify_order"] if _BY_ID[i].get("match")
]

CATEGORY_TAGS = {
    "ai": ["#aitools", "#chatgpt", "#ai"],
    "tech_concepts": ["#techexplained", "#learncoding", "#softwareengineering"],
    "career": ["#careertips", "#interviewtips", "#techcareers"],
    "skills": ["#communicationskills", "#selfimprovement", "#skills"],
    "relatable_learning": ["#developerlife", "#codinglife", "#learning"],
}
INDIA_TAGS = ["#techindia", "#indiandevelopers"]


def _pick(seed: str, n: int) -> int:
    return int(hashlib.sha256(seed.encode()).hexdigest()[:8], 16) % n


def classify_hook(text: str) -> str | None:
    """Name the formula a hook uses, with the same regexes the skills pack uses."""
    for i, rx in _MATCHERS:
        if rx.search(text):
            return _BY_ID[i]["name"]
    return None


def score_hook(text: str, perspective: Perspective = "you") -> dict:
    results, overall, verdict, flags = hookscore.run(text)
    checks = {k: {"score": round(v[0]), "detail": v[1]} for k, v in results.items()}
    if perspective == "third" and checks["ADDRESS"]["score"] < 70:
        # Third person was chosen on purpose. Credit it when it names a concrete someone.
        named = re.search(r"\b(most|every|this|that|one|a)\s+\w+|\b[A-Z][a-z]+\b", text[1:] if text else "")
        checks["ADDRESS"] = {
            "score": 75 if named else 55,
            "detail": "third person by choice" + (", names a specific someone" if named else ""),
        }
        scores = [c["score"] for c in checks.values()]
        overall = max(0.0, min(100.0, sum(scores) / len(scores) * 0.6 + min(scores) * 0.4 - len(flags) * 15))
        verdict = (
            "STRONG"
            if overall >= 70 and min(scores) >= 55 and not flags
            else ("OK" if overall >= 50 else "WEAK")
        )
    weakest = min(checks.items(), key=lambda kv: kv[1]["score"])
    return {
        "score": round(overall),
        "verdict": verdict,
        "checks": checks,
        "flags": flags,
        "fix": None if verdict == "STRONG" else f"Weakest: {weakest[0].lower()} ({weakest[1]['detail']})",
    }


# ---------------- hooks ----------------

# (formula name, third-person, you, I). {t}=topic, {a}=audience noun.
HOOK_TEMPLATES = [
    (
        "Nobody Tells You",
        "Nobody tells most {a} this about {t}.",
        "Nobody tells you this about {t}.",
        "Nobody told me this about {t}.",
    ),
    (
        "Negative Command",
        "Most {a} learn {t} the hard way. One idea fixes it.",
        "Stop learning {t} the hard way.",
        "I stopped learning {t} the hard way.",
    ),
    (
        "Identity Reframe",
        "Most {a} think {t} sounds hard. It isn't. They're missing one example.",
        "You're not bad at {t}. You're missing one example.",
        "I thought I was bad at {t}. I was missing one example.",
    ),
    (
        "Everyday India",
        "A ₹20 chai order explains {t} better than most tutorials.",
        "Your ₹20 chai order already explains {t}.",
        "My ₹20 chai order finally explained {t} to me.",
    ),
    (
        "Numbered",
        "3 things most {a} get wrong about {t}.",
        "3 things you're getting wrong about {t}.",
        "3 things I got wrong about {t}.",
    ),
    (
        "Before / After",
        "Same {a}, same task: one used {t}, one didn't. 2 hours vs 10 minutes.",
        "You're spending 2 hours on what {t} does in 10 minutes.",
        "I spent 2 hours on what {t} now does in 10 minutes.",
    ),
    (
        "Story Open",
        "Last week a {a_one} failed an interview over {t}. Here's what happened.",
        "Imagine failing an interview over {t}.",
        "I failed an interview over {t}. Here's what happened.",
    ),
    (
        "Question",
        "Why do some {a} always seem one step ahead on {t}?",
        "Why do some people always seem one step ahead on {t}?",
        "Why was I always one step behind on {t}?",
    ),
]
AUDIENCE_NOUN = {"beginner": ("beginners", "beginner"), "developer": ("developers", "developer")}


class Hook(BaseModel):
    text: str
    formula: str
    on_screen: str
    score: int
    verdict: str
    fix: str | None = None


# For ideas that are already a statement ("Your degree doesn't decide your career"), the title is the claim.
# These frame the claim instead of treating it as a noun. {s}=statement, {q}=statement as a lowercase clause.
STATEMENT_TEMPLATES = [
    (
        "Nobody Tells You",
        "Nobody tells most {a} this: {q}.",
        "Nobody tells you this: {q}.",
        "Nobody told me this: {q}.",
    ),
    (
        "Identity Reframe",
        "Most {a} believe the opposite. {s}.",
        "You've been told the opposite. {s}.",
        "I used to believe the opposite. {s}.",
    ),
    (
        "Story Open",
        "A {a_one} I mentored learned this the hard way: {q}.",
        "Here's what took me years to learn: {q}.",
        "I learned this the hard way: {q}.",
    ),
    (
        "Proof First",
        "{s}. Here's the proof most {a} never see.",
        "{s}. Here's the proof.",
        "{s}. Here's my proof.",
    ),
    (
        "Question",
        "What if most {a} have it backwards? {s}.",
        "What if you have it backwards? {s}.",
        "What if I had it backwards all along? {s}.",
    ),
    ("Plain Statement", "{s}.", "{s}.", "{s}."),
]


def is_statement(topic: str) -> bool:
    """A full claim rather than a subject: several words, or starts like a sentence."""
    w = topic.split()
    starts = (
        "your",
        "you",
        "my",
        "i",
        "why",
        "how",
        "what",
        "stop",
        "nobody",
        "most",
        "every",
        "this",
        "the",
    )
    return len(w) >= 5 or (bool(w) and w[0].lower().strip("'") in starts and len(w) >= 3)


def _clause(s: str) -> str:
    keep = s.split()[0] in ("I", "UPI", "AI", "AWS", "API", "APIs") if s else False
    return s if keep else s[:1].lower() + s[1:]


def generate_hooks(
    topic: str, audience: Audience = "beginner", perspective: Perspective = "third", n: int = 6
) -> list[Hook]:
    topic = topic.strip().rstrip(".?!")
    a, a_one = AUDIENCE_NOUN[audience]
    col = {"third": 1, "you": 2, "i": 3}[perspective]
    templates = STATEMENT_TEMPLATES if is_statement(topic) else HOOK_TEMPLATES
    start = _pick(topic, len(templates))
    out = []
    for k in range(min(n, len(templates))):
        t = templates[(start + k) % len(templates)]
        text = t[col].format(t=topic, s=topic, q=_clause(topic), a=a, a_one=a_one)
        sc = score_hook(text, perspective)
        out.append(
            Hook(
                text=text,
                formula=t[0],
                on_screen=_on_screen(text),
                score=sc["score"],
                verdict=sc["verdict"],
                fix=sc["fix"],
            )
        )
    return sorted(out, key=lambda h: -h.score)


def _on_screen(text: str) -> str:
    words = re.sub(r"[^\w₹\s']", "", text).split()
    return " ".join(words[:5]).upper()


# ---------------- caption ----------------


class Caption(BaseModel):
    first_line: str = Field(description="what shows before '... more' (<=125 chars)")
    body: str
    cta: str
    keywords: list[str]
    hashtags: list[str]
    full: str
    preview_cut: str


def generate_caption(
    topic: str, hook: str | None = None, category: str = "tech_concepts", audience: Audience = "beginner"
) -> Caption:
    topic = topic.strip().rstrip(".?!")
    first = (hook or f"{topic}, explained in 30 seconds.").strip()
    if len(first) > 125:
        first = first[:122].rstrip() + "..."
    if audience == "developer":
        who = "with the details that matter in production"
    elif category in ("career", "skills", "relatable_learning"):
        who = "even if you're just starting out"
    else:
        who = "even if you've never coded"
    lead = f"Here's what I mean, {who}." if is_statement(topic) else f"Here's how {topic} works, {who}."
    body = (
        f"{lead}\n\n"
        f"1. What it is, in one line\n2. The everyday example that makes it click\n"
        f"3. Where you'll actually use it"
    )
    cta = "Save this for later, and comment the next topic you want explained."
    kw = [
        topic.lower(),
        f"{topic.lower()} explained",
        "learn tech in hindi english" if audience == "beginner" else "software engineering",
        "tech for beginners" if audience == "beginner" else "developer tips",
    ]
    tags = (CATEGORY_TAGS.get(category, CATEGORY_TAGS["tech_concepts"])[:3] + INDIA_TAGS[:1])[:5]
    full = f"{first}\n\n{body}\n\n{cta}\n\n{' · '.join(kw)}\n\n{' '.join(tags)}"
    return Caption(
        first_line=first,
        body=body,
        cta=cta,
        keywords=kw,
        hashtags=tags,
        full=full,
        preview_cut=full[:125] + ("... more" if len(full) > 125 else ""),
    )


# ---------------- repurpose ----------------


class Slide(BaseModel):
    title: str
    text: str


class Repurposed(BaseModel):
    audience: Audience
    reel_30s: list[dict]
    carousel: list[Slide] = Field(min_length=5, max_length=5)
    linkedin_post: str
    youtube_short: str
    text_post: str


def repurpose(topic: str, audience: Audience = "beginner", hook: str | None = None) -> Repurposed:
    topic = topic.strip().rstrip(".?!")
    beg = audience == "beginner"
    analogy = (
        f"Think of {topic} like ordering chai: you ask, someone handles it, you get it back."
        if beg
        else f"{topic}: a contract between two systems: a request in, a predictable response out."
    )
    why = (
        "You already use it every day without noticing."
        if beg
        else "Get it wrong and you pay in latency, retries and on-call pages."
    )
    hook = hook or (
        f"Most beginners overthink {topic}."
        if beg
        else f"Most developers use {topic} without thinking about it."
    )
    reel = [
        {"t": "0-3s", "say": hook, "screen": _on_screen(hook)},
        {"t": "3-12s", "say": analogy, "screen": "THE SIMPLE VERSION"},
        {"t": "12-24s", "say": why + " Here's one real example.", "screen": "WHERE YOU SEE IT"},
        {"t": "24-30s", "say": f"Now {topic} won't feel hard again. Save this.", "screen": "SAVE FOR LATER"},
    ]
    slides = [
        Slide(title=hook, text="Swipe →"),
        Slide(title=f"What {topic} is", text=analogy),
        Slide(title="Why it matters", text=why),
        Slide(
            title="A real example",
            text=f"Where {topic} shows up: apps you open every day."
            if beg
            else f"Where {topic} bites: timeouts, versioning, error handling.",
        ),
        Slide(title="Remember this", text=f"{topic} = one clear request, one clear response. Save + share."),
    ]
    linkedin = (
        f"{hook}\n\n{analogy}\n\n{why}\n\nThe lesson I keep coming back to: explain it simply first, "
        f"then go deep.\n\nWhat's a concept you wish someone had explained this way?"
    )
    short = "\n".join(f"[{b['t']}] {b['say']}" for b in reel)
    text = f"{hook}\n\n{analogy} {why}"
    return Repurposed(
        audience=audience,
        reel_30s=reel,
        carousel=slides,
        linkedin_post=linkedin,
        youtube_short=short,
        text_post=text,
    )


# ---------------- duplicates ----------------

_STOP = set("a an the to of in on for and or is are your you my i how what why with this that it be".split())


def _tokens(s: str) -> set[str]:
    words = (w for w in re.findall(r"[a-z0-9₹]+", (s or "").lower()) if w not in _STOP and len(w) > 1)
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in words}  # "apis" ~ "api"


def similar(text: str, candidates: list[tuple[str, str, int]], threshold: float = 0.4) -> list[dict]:
    """candidates: (kind, text, id); text may carry extra words after a " || " (matched, not shown)."""
    a = _tokens(text)
    out: list[dict] = []
    for kind, other, ident in candidates:
        b = _tokens(other)
        if not a or not b:
            continue
        j = len(a & b) / len(a | b)
        if j >= threshold:
            out.append(
                {"kind": kind, "id": ident, "text": other.split(" || ")[0][:140], "similarity": round(j, 2)}
            )
    return sorted(out, key=lambda r: -float(r["similarity"]))[:5]


# ---------------- optional model path ----------------


def generate_with_model(kind: str, payload: dict, schema: type[BaseModel], fallback):
    """Use the configured model (Bedrock, OpenAI or Claude API); otherwise (or on error) the template.
    Returns (result, source)."""
    from ..agents.providers import MODEL_MODES, make_model, model_config_error

    s = get_settings()
    if s.agent_mode not in MODEL_MODES or model_config_error(s):
        return fallback(), "template"
    try:
        from strands import Agent, ModelRetryStrategy

        from ..agents.registry import BRAND, RULES

        agent = Agent(
            model=make_model(s),
            # Someone is waiting on screen: one retry, then fall back to the template.
            retry_strategy=ModelRetryStrategy(max_attempts=2, initial_delay=2),
            callback_handler=None,
            system_prompt=f"You write Instagram content for this creator.\n{BRAND}\n{RULES}\n"
            "Write like a person: no em dashes, no hype words, Indian everyday examples.",
        )
        res = agent(
            f"Task: {kind}\nInput: {json.dumps(payload, ensure_ascii=False)}", structured_output_model=schema
        )
        if res.structured_output is None:
            raise RuntimeError("no structured output")
        return res.structured_output, s.agent_mode
    except Exception as e:  # never block the user on the model
        log.warning("model generation failed, using template: %s", type(e).__name__)
        return fallback(), "template (model unavailable)"
