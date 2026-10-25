"""Reel Planner: niche -> trending topics -> one complete, shootable reel package -> saved plan.

Model calls go through creator.generate_with_model (the same path Create uses), so every result is
validated against a Pydantic schema before it leaves this module. If the model returns something
that does not fit the schema we retry once with an explicit correction note, then fall back to a
deterministic template so the screen never dead-ends.

Trend evidence comes from services/trends.py. When no search provider is configured the topics are
written from model knowledge only and labelled that way all the way to the UI.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..agents import schemas as S
from ..config import get_settings
from ..models import ReelPlan, iso_utc
from . import creator, reel_prompts, trends
from . import queries as q

log = logging.getLogger(__name__)

DEFAULT_PLATFORM = "instagram_reels"
TOPIC_COUNT = 9  # the brief asks for 8-10
DEFAULT_DURATION = 32


# ---------------- model path: validate, retry once, then template ----------------


def _generate(kind: str, payload: dict, schema: type[BaseModel], fallback):
    """(result, source). One retry when the model's output does not validate."""
    from ..agents.providers import MODEL_MODES, model_config_error

    s = get_settings()
    if s.agent_mode not in MODEL_MODES or model_config_error(s):
        return fallback(), "template"

    sentinel = object()
    attempt_payload = payload
    for attempt in (1, 2):
        res, src = creator.generate_with_model(kind, attempt_payload, schema, lambda: sentinel)
        if res is not sentinel:
            try:
                # generate_with_model already validated; re-validate so a changed provider path
                # can never slip an unchecked dict through.
                return schema.model_validate(res.model_dump() if hasattr(res, "model_dump") else res), src
            except ValidationError as e:
                log.warning(
                    "reel planner %s: invalid output on attempt %s (%s)", kind, attempt, e.error_count()
                )
        if attempt == 1:
            attempt_payload = {
                **payload,
                "_correction": "Your previous answer did not match the required JSON schema. "
                "Return valid JSON matching the schema exactly, with every required field and "
                "every list within its length limits.",
            }
    return fallback(), "template (model output invalid)"


# ---------------- 1. trending topics ----------------

# Shapes used by the keyless template so the flow works with no API key at all. Deliberately
# labelled as not-live and not dressed up as research.
_TEMPLATE_SHAPES: list[tuple[str, str, str, str, str]] = [
    (
        "The {n} advice nobody actually follows",
        "Contrarian takes keep resurfacing in {n} because the standard advice stopped working for most people.",
        "Name the advice, then show what the people getting results do instead.",
        "high",
        "Disagreement drives comments, and comments drive reach.",
    ),
    (
        "{n}, explained with something you already do every day",
        "Beginner-level explainers in {n} get saved and resent long after they are posted.",
        "Take one everyday moment and map it onto the concept, one frame at a time.",
        "high",
        "Explainers that make someone feel smart get saves and shares.",
    ),
    (
        "3 mistakes beginners make in {n}",
        "Mistake lists stay in demand because new people enter {n} every week.",
        "Show the mistake on screen, then the fix, in under 10 seconds each.",
        "medium",
        "Useful but crowded; the hook has to do the work.",
    ),
    (
        "What I would do in my first 30 days in {n}",
        "First-steps questions are the most repeated question in every {n} community.",
        "A concrete week-by-week plan, no vague encouragement.",
        "medium",
        "Saves well, shares less.",
    ),
    (
        "The part of {n} that nobody warns you about",
        "Honest posts about the hard parts of {n} pull strong engagement from people mid-journey.",
        "One specific cost, told as a short story, with what you would do differently.",
        "high",
        "Story plus honesty keeps people to the end.",
    ),
    (
        "{n}: the textbook way vs the way it actually works",
        "Side-by-side comparisons are easy to follow on mute, which matters on short-form.",
        "Split screen, one claim per side, fastest cuts you can hold.",
        "medium",
        "Clear structure, but needs a sharp payoff.",
    ),
    (
        "How to explain your {n} work so people actually get it",
        "Communication gaps come up constantly in {n} and almost nobody makes content about it.",
        "Rewrite one bad explanation live, line by line.",
        "medium",
        "Underserved angle; low competition.",
    ),
    (
        "The one tool in {n} I would not give up",
        "Tool recommendations in {n} get asked for in comments more than anything else.",
        "Show the actual screen, the actual workflow, no sponsor energy.",
        "medium",
        "Comment bait, but easy to make generic.",
    ),
    (
        "Stop learning {n} this way",
        "Negative-command openers keep working as pattern interrupts.",
        "Call out the common approach in the first second, then give the replacement.",
        "high",
        "Strong hook shape; the claim must be defensible.",
    ),
]


def _template_trends(niche: str, platform: str, count: int, searched: int = 0) -> S.TrendReport:
    """Built-in topic shapes, used when no model is configured.

    `searched` is how many live hits the provider returned. They are deliberately NOT attached to
    these topics: the template's "why_trending" was not derived from them, so citing them would
    imply evidence that does not exist. We say so in the disclosure instead.
    """
    topics = []
    for title, why, angle, pot, reason in _TEMPLATE_SHAPES[:count]:
        topics.append(
            S.TrendTopic(
                title=title.format(n=niche)[:140],
                why_trending=why.format(n=niche),
                angle=angle.format(n=niche),
                engagement_potential=pot,  # type: ignore[arg-type]
                potential_reason=reason,
                sources=[],
            )
        )
    note = (
        f" A search provider returned {searched} results, but no AI model is configured to turn "
        "them into topics, so they were not used."
        if searched
        else " No search provider is configured, and these are built-in topic shapes, not AI-written."
    )
    return S.TrendReport(
        niche=niche,
        platform=platform,  # type: ignore[arg-type]
        topics=topics,
        live_research_performed=False,
        disclosure=trends.NOT_LIVE
        + note
        + " Set up a model in .env.secrets for topics written for your exact niche.",
    )


def find_trends(
    db: Session,
    niche: str,
    platform: str = DEFAULT_PLATFORM,
    count: int = TOPIC_COUNT,
    audience: str | None = None,
) -> dict:
    """Research the niche and return topic candidates. Never invents a source."""
    s = get_settings()
    provider = trends.get_provider(s)
    label = reel_prompts.PLATFORM_LABEL.get(platform, platform)
    try:
        results = provider.search(niche, label)
    except Exception as e:  # a dead search endpoint must not take the screen down
        log.warning("trend provider %s failed: %s", provider.name, type(e).__name__)
        results = []
    live = bool(results)

    voice = q.get_setting(db, "voice_profile") or None
    prompt = reel_prompts.trends(niche, platform, count, audience, voice, results or None)
    report, source = _generate(
        prompt,
        {"niche": niche, "platform": platform, "count": count, "audience": audience},
        S.TrendReport,
        lambda: _template_trends(niche, platform, count, len(results)),
    )
    out = report.model_dump()
    # The provider, not the model, is the authority on whether live search actually ran. A template
    # answer never counts as live even when the search itself succeeded.
    out["live_research_performed"] = live and not source.startswith("template")
    if not out["live_research_performed"]:
        out["topics"] = [{**t, "sources": []} for t in out["topics"]]
        if not out["disclosure"].lower().startswith("model knowledge only"):
            out["disclosure"] = trends.NOT_LIVE
    out["source"] = source
    out["provider"] = provider.name
    out["search_results_found"] = len(results)
    out["niche"] = niche
    out["platform"] = platform
    return out


# ---------------- 2. the full reel package ----------------


def _template_plan(topic: dict, niche: str, platform: str, duration: int) -> S.ReelPlanOut:
    t = str(topic.get("title") or niche)[:140]
    angle = str(topic.get("angle") or f"One concrete example from {niche}.")
    d = max(15, min(duration, 45))
    # Proportional beats so the sections always add up to d.
    b = [round(d * x) for x in (0.09, 0.25, 0.65, 0.88, 1.0)]
    hooks = [
        S.Hook(
            text=f"Most people in {niche} get this wrong in the first five seconds.",
            hook_type="contrarian",
            why_it_works="Opens on the viewer's belief, not on the topic.",
        ),
        S.Hook(
            text=f"Nobody told me this about {niche} until it cost me a month.",
            hook_type="story",
            why_it_works="A cost makes the next line feel necessary.",
        ),
        S.Hook(
            text=f"Why does {niche} feel so much harder than it should?",
            hook_type="curiosity",
            why_it_works="Names a feeling the viewer already has.",
        ),
    ]
    script = [
        S.ScriptSection(
            section="hook",
            t_start=0,
            t_end=b[0],
            spoken=hooks[0].text,
            on_screen_text="You're doing it backwards",
        ),
        S.ScriptSection(
            section="setup",
            t_start=b[0],
            t_end=b[1],
            spoken=f"Here is the version everyone repeats about {t}.\nIt sounds right. It just does not work.",
            on_screen_text="The advice everyone repeats",
        ),
        S.ScriptSection(
            section="value",
            t_start=b[1],
            t_end=b[2],
            spoken=f"{angle}\nDo that one thing and the rest gets easier.",
            on_screen_text="Do this instead",
        ),
        S.ScriptSection(
            section="payoff",
            t_start=b[2],
            t_end=b[3],
            spoken="That is the whole shift. One change, not ten.",
            on_screen_text="One change, not ten",
        ),
        S.ScriptSection(
            section="cta",
            t_start=b[3],
            t_end=b[4],
            spoken=f"Save this before your next {niche} session.",
            on_screen_text="Save it",
        ),
    ]
    shots = [
        S.Shot(
            order=1,
            shot_type="talking head",
            framing="tight crop, chest up, eye level",
            location="plain wall, window light from the side",
            action="Deliver the hook straight to the lens, no intro",
            delivery_tone="Fast, flat, certain. No smile on the first line.",
            b_roll=["hard cut from black on the first word"],
            seconds=float(b[0]),
        ),
        S.Shot(
            order=2,
            shot_type="over-the-shoulder / insert",
            framing="mid, slightly off centre",
            location="desk",
            action="Show the common approach on screen or on paper",
            delivery_tone="Conversational, drop the pace for one beat",
            b_roll=["screen recording", "hands pointing at the wrong step"],
            seconds=float(b[1] - b[0]),
        ),
        S.Shot(
            order=3,
            shot_type="screen recording",
            framing="full screen with a zoom on the key moment",
            location="laptop",
            action="Walk through the replacement step by step",
            delivery_tone="Steady, one idea per cut, pause after the key line",
            b_roll=["cursor zoom", "before/after side by side"],
            seconds=float(b[2] - b[1]),
        ),
        S.Shot(
            order=4,
            shot_type="talking head",
            framing="tight crop again, matching the opening",
            location="plain wall",
            action="Land the payoff, then the single CTA",
            delivery_tone="Slower, warmer, loop back to the opening words",
            b_roll=["text card with the one-line takeaway"],
            seconds=float(b[4] - b[2]),
        ),
    ]
    tag = "".join(ch for ch in niche.lower() if ch.isalnum())[:20] or "shortform"
    return S.ReelPlanOut(
        topic=t,
        platform=platform,  # type: ignore[arg-type]
        audience=f"People working on {niche} who already tried the obvious advice",
        one_idea=f"One specific change in {niche} that does more than the standard advice.",
        hooks=hooks,
        script=script,
        shots=shots,
        total_duration_seconds=d,
        caption=f"{t}\n\nThe advice everyone repeats is not wrong. It is just not the part that moves "
        f"anything.\n\nSave this for your next {niche} session.\n\nWhat would you add?",
        hashtags=[f"#{tag}", "#shortform", "#reels", "#learnonreels", "#creator", "#howto"],
        pinned_comment=f"What is the one piece of {niche} advice you have given up on?",
        cta_primary="Save this before your next session.",
        cta_alternative="Comment the step you are stuck on.",
        audio_direction="Low, steady instrumental under the voice, no drops. Pick from the platform's "
        "own licensed library so the audio stays available.",
        best_posting_time="19:00-21:00 IST. This is a starting default to test, not a measured best "
        "time for your account.",
        ab_test_idea="Same script, contrarian hook vs curiosity hook, three reels each. Compare "
        "watch-through and saves per 1,000 reached.",
    )


def build_plan(
    db: Session,
    topic: dict,
    niche: str,
    platform: str = DEFAULT_PLATFORM,
    duration: int = DEFAULT_DURATION,
    audience: str | None = None,
) -> tuple[S.ReelPlanOut, str]:
    voice = q.get_setting(db, "voice_profile") or None
    prompt = reel_prompts.reel_plan(topic, niche, platform, duration, audience, voice)
    plan, source = _generate(
        prompt,
        {"topic": topic, "niche": niche, "platform": platform, "target_seconds": duration},
        S.ReelPlanOut,
        lambda: _template_plan(topic, niche, platform, duration),
    )
    return plan, source


# ---------------- 3. regenerate one section ----------------

SECTION_SCHEMAS: dict[str, type[BaseModel]] = {
    "hooks": S.HooksOnly,
    "script": S.ScriptOnly,
    "shots": S.ShotsOnly,
    "caption": S.CaptionOnly,
    "cta": S.CtaOnly,
}


def regenerate_section(db: Session, row: ReelPlan, section: str) -> tuple[dict, str]:
    """Redo one part of a saved plan and persist only that part. Returns (new package, source)."""
    schema = SECTION_SCHEMAS[section]
    pkg = dict(row.package or {})
    prompt = reel_prompts.regenerate(section, pkg, row.niche, row.platform)
    whole = _template_plan(
        row.topic or {"title": row.title}, row.niche, row.platform, row.duration_seconds or DEFAULT_DURATION
    )

    def fallback():
        return schema.model_validate({k: getattr(whole, k) for k in schema.model_fields})

    part, source = _generate(prompt, {"section": section, "plan": pkg}, schema, fallback)
    pkg.update(part.model_dump())
    row.package = pkg
    row.source = source
    db.flush()
    return pkg, source


# ---------------- storage ----------------


def to_dict(row: ReelPlan) -> dict:
    return {
        "id": row.id,
        "niche": row.niche,
        "platform": row.platform,
        "title": row.title,
        "topic": row.topic or {},
        "package": row.package or {},
        "duration_seconds": row.duration_seconds,
        "source": row.source,
        "live_research": row.live_research,
        "idea_id": row.idea_id,
        "created_at": iso_utc(row.created_at),
        "updated_at": iso_utc(row.updated_at),
    }


def summary(row: ReelPlan) -> dict:
    pkg = row.package or {}
    hooks = pkg.get("hooks") or []
    return {
        "id": row.id,
        "title": row.title,
        "niche": row.niche,
        "platform": row.platform,
        "duration_seconds": row.duration_seconds,
        "source": row.source,
        "live_research": row.live_research,
        "hook": (hooks[0] or {}).get("text") if hooks else None,
        "created_at": iso_utc(row.created_at),
    }


def save(
    db: Session,
    niche: str,
    platform: str,
    topic: dict,
    plan: S.ReelPlanOut,
    source: str,
    live_research: bool,
) -> ReelPlan:
    row = ReelPlan(
        niche=niche[:200],
        platform=platform,
        title=(plan.topic or topic.get("title") or niche)[:200],
        topic=topic,
        package=plan.model_dump(),
        duration_seconds=plan.total_duration_seconds,
        source=source,
        live_research=live_research,
        is_demo=q.use_demo(db),
    )
    db.add(row)
    db.flush()
    return row


def listing(db: Session) -> list[dict]:
    rows = db.scalars(
        select(ReelPlan).where(ReelPlan.is_demo.is_(q.use_demo(db))).order_by(ReelPlan.created_at.desc())
    ).all()
    return [summary(r) for r in rows]


def get(db: Session, plan_id: int) -> ReelPlan | None:
    return db.get(ReelPlan, plan_id)


def delete(db: Session, row: ReelPlan) -> None:
    db.delete(row)
    db.flush()


# ---------------- video auto-edit: interface only ----------------


class VideoEditor(Protocol):
    """Planned, not built. The UI shows a disabled "Upload video for auto-edit (Coming soon)"
    button; nothing in the app calls this yet.

    The intended contract: take a raw clip plus a saved plan and return a cut that follows the
    plan's shot list and burns in the per-section on-screen text.
    """

    def edit(self, source_path: str, plan: dict) -> dict:
        """-> {"output_path": str, "cuts": [...]} . Raises NotImplementedError today."""
        ...


class NotImplementedVideoEditor:
    """The only implementation, on purpose."""

    name = "coming_soon"
    available = False

    def edit(self, source_path: str, plan: dict[str, Any]) -> dict:
        raise NotImplementedError("Video auto-edit is not built yet.")
