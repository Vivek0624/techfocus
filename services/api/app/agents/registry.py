"""Agent definitions: responsibility, permitted tools, system prompt, output schema, and a deterministic
mock implementation that is grounded in the same tool data the live model would see."""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from . import schemas as S
from .tools import ToolContext, call_tool

BRAND = (
    "Creator: Vivek (@vivek_techfocus), Pune, software developer, 4x AWS certified. Audience: Indian "
    "software engineers, students, beginners and non-technical learners. Pillars: simple tech explanations, "
    "AI tools/workflows, APIs/system design/coding, career + communication + interviews, tech through "
    "everyday Indian examples, productivity, consistency. Tone: clear, warm, practical, no hype."
)
RULES = (
    "Rules: never invent metrics, trends, demographics or follower predictions; cite the tool or metric "
    "behind every claim; say when data is missing or the sample is small; do not treat one post as a rule; "
    "never publish, comment or message - you can only create drafts, proposals and approval requests."
)


@dataclass
class AgentSpec:
    id: str
    name: str
    responsibility: str
    tools: list[str]
    output: type[BaseModel]
    prompt: str
    mock: Callable[[ToolContext, dict], dict]


def _seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


# ---------------- mock implementations ----------------


def mock_analytics(ctx: ToolContext, inp: dict) -> dict:
    top = call_tool(ctx, "get_top_performing_reels", limit=5)
    media = call_tool(ctx, "list_recent_media", limit=30)
    ins = call_tool(ctx, "get_instagram_insights", days=int(inp.get("days", 30)))
    views = [m["views"] for m in media if m.get("views") is not None]
    findings = []
    if views:
        findings.append(
            S.Evidence(
                claim=f"Median views per post: {int(statistics.median(views)):,} across {len(views)} posts.",
                source="list_recent_media",
            )
        )
    if ins.get("net_follower_growth") is not None:
        findings.append(
            S.Evidence(
                claim=f"Net follower change over {ins['days']} days: {ins['net_follower_growth']:+,}.",
                source="get_instagram_insights",
            )
        )
    if ins.get("follows_per_1k_reach") is not None:
        findings.append(
            S.Evidence(
                claim=f"{ins['follows_per_1k_reach']} follows per 1,000 accounts reached.",
                source="get_instagram_insights",
            )
        )
    outliers = [
        f"{(t['caption'] or '(no caption)')[:70]} - {t['multiple']}x median"
        for t in top
        if t["multiple"] and t["multiple"] >= 3
    ]
    weak = [
        f"{(m['caption'] or '(no caption)')[:60]} - {m['views']:,} views"
        for m in media
        if m.get("views") is not None and views and m["views"] < 0.5 * statistics.median(views)
    ][:3]
    lim = ["Follows are account-level; the API does not attribute them to individual posts."]
    if len(views) < 10:
        lim.append(f"Only {len(views)} posts with metrics - patterns are tentative.")
    action = (
        f"Make a follow-up to your top outlier ('{outliers[0].split(' - ')[0]}') in the same format, "
        "and pin the original."
        if outliers
        else "Post 3-4 more reels before drawing conclusions."
    )
    return S.AnalyticsReport(
        key_findings=findings,
        outliers=outliers,
        weak_patterns=weak,
        recommended_action=action,
        limitations=lim,
        sample_size=len(views),
    ).model_dump()


def mock_growth(ctx: ToolContext, inp: dict) -> dict:
    prog = call_tool(ctx, "get_growth_target_progress")
    ins = call_tool(ctx, "get_instagram_insights", days=7)
    top = call_tool(ctx, "get_top_performing_reels", limit=3)
    exps = call_tool(ctx, "get_experiment_results")
    ev, lim = [], []
    reach, f1k = ins.get("reach"), ins.get("follows_per_1k_reach")
    if f1k is not None and reach:
        bottleneck = (
            "conversion: people see the reels but few follow"
            if f1k < 5
            else "reach: conversion is healthy, more viewers are needed"
        )
        ev.append(
            S.Evidence(
                claim=f"7-day reach {reach:,}; {f1k} follows per 1k reached", source="get_instagram_insights"
            )
        )
    else:
        bottleneck = "unknown: follows or reach data unavailable"
        lim.append("Follows/unfollows unavailable (API omits them under 100 followers or before first sync).")
    if prog.get("configured"):
        ev.append(
            S.Evidence(
                claim=f"{prog['remaining']:,} followers to target; needs "
                f"{prog['required_per_day']}/day for {prog['days_remaining']} days",
                source="get_growth_target_progress",
            )
        )
    if top:
        ev.append(
            S.Evidence(
                claim=f"Best recent post ran {top[0]['multiple']}x the account median",
                source="get_top_performing_reels",
            )
        )
    running = [e for e in exps if e["status"] == "running"]
    exp = running[0]["name"] if running else "Hook style: identity-reframe vs explainer opener, 3 reels each"
    return S.GrowthPlan(
        bottleneck=bottleneck,
        next_action=(
            "Rewrite bio line 1 to say what a follower gets, pin the top reel, then post its follow-up"
            if bottleneck.startswith("conversion")
            else "Post one reel today in your top-performing format"
        ),
        daily_priorities=[
            "Review yesterday's reel vs your median",
            "Produce and post one reel",
            "Reply to every genuine question in comments",
        ],
        weekly_priorities=["5 reels across 2 pillars", "Close or advance one experiment", "Weekly review"],
        experiment_to_run=exp,
        expected_learning="Which opener raises 3-second hold and follows per 1k reach",
        evidence=ev,
        confidence="low" if lim else "medium",
        limitations=lim,
    ).model_dump()


def mock_audience(ctx: ToolContext, inp: dict) -> dict:
    top = call_tool(ctx, "get_top_performing_reels", limit=3)
    seg = [
        (
            "College students",
            "don't know which skills matter for a first job",
            "skills that matter more than marks",
            ["Your marks won't get you hired. These 3 things will."],
        ),
        (
            "Interview candidates",
            "freeze when explaining their own projects",
            "communication for developers",
            ["Your English is not why you're failing interviews."],
        ),
        (
            "Non-technical learners",
            "AI and tech sound intimidating",
            "tech through everyday Indian examples",
            ["Your ₹20 chai order is an API call."],
        ),
        (
            "Working engineers",
            "busywork eats the day",
            "AI-assisted workflows",
            ["I gave my standup notes to AI for a week. Here's what changed."],
        ),
    ]
    insights = []
    for name, need, angle, hooks in seg:
        evid = []
        level = "hypothesis"
        if top and "communication" in angle and any("communic" in (t["caption"] or "").lower() for t in top):
            level = "observed"
            evid.append(
                S.Evidence(
                    claim="A communication reel is among your top outliers", source="get_top_performing_reels"
                )
            )
        insights.append(
            S.AudienceInsight(
                segment=name, need=need, angle=angle, hook_ideas=hooks, evidence_level=level, evidence=evid
            )
        )  # type: ignore[arg-type]
    return S.AudienceReport(
        insights=insights,
        limitations=["Personas are inferred from content performance, not from Instagram demographic data."],
    ).model_dump()


def mock_research(ctx: ToolContext, inp: dict) -> dict:
    topic = str(inp.get("topic") or "APIs")
    return S.ResearchReport(
        topic=topic,
        summary=f"Mock mode: no live research. Draft angles for '{topic}' from general knowledge only.",
        key_claims=[],
        proposed_angles=[
            f"{topic} explained with an everyday Indian example",
            f"3 mistakes beginners make with {topic}",
            f"{topic}: manual vs AI-assisted",
        ],
        live_research_performed=False,
        disclosure="No research provider configured. Verify every factual claim before recording.",
    ).model_dump()


HOOK_TEMPLATES = [
    ("identity_reframe", "You don't need to be a genius to understand {t}. You need one good example."),
    ("everyday_india", "Your ₹20 chai order already taught you {t}. Here's how."),
    ("negative_command", "Stop memorising {t}. Understand this one idea instead."),
    ("question", "Why does {t} matter to someone who's never written code?"),
    ("head_to_head", "{t}: the textbook way vs the way it actually works."),
]


def mock_reel(ctx: ToolContext, inp: dict) -> dict:
    topic = str(inp.get("topic") or "APIs").strip()[:120]
    seg = str(inp.get("audience_segment") or "Beginner developers")
    fmt = (
        inp.get("format")
        if inp.get("format") in ("talking_head", "motion_graphics", "mixed")
        else "talking_head"
    )
    n = max(1, min(int(inp.get("options", 1)), 3))
    out = []
    for k in range(n):
        start = _seed(topic, str(k)) % len(HOOK_TEMPLATES)
        hooks = [HOOK_TEMPLATES[(start + i) % len(HOOK_TEMPLATES)] for i in range(3)]
        hook_lines = [h[1].format(t=topic) for h in hooks]
        rec = hook_lines[0]
        timeline = [
            S.Scene(
                t_start=0,
                t_end=3,
                visual="Face to camera, tight crop"
                if fmt != "motion_graphics"
                else "Bold kinetic text on dark background",
                voiceover=rec,
                on_screen_text=rec[:40],
            ),
            S.Scene(
                t_start=3,
                t_end=12,
                visual="Everyday analogy: cutaway or simple icons",
                voiceover=f"Think of {topic} like ordering at a chai stall: you ask, someone handles it, "
                "you get a result.",
                on_screen_text="You ask → it handles → you get it",
            ),
            S.Scene(
                t_start=12,
                t_end=25,
                visual="Diagram builds step by step",
                voiceover=f"In tech terms, that's exactly what {topic} does. One request, one clear response.",
                on_screen_text=f"{topic} = request → response",
            ),
            S.Scene(
                t_start=25,
                t_end=30,
                visual="Back to face, loop to opening line",
                voiceover="Now you'll see it everywhere. Follow for one idea like this every day.",
                on_screen_text="Follow for daily tech, simply",
            ),
        ]
        out.append(
            S.ReelPackage(
                title=f"{topic} explained simply" + (f" (option {k + 1})" if n > 1 else ""),
                audience_segment=seg,
                audience_problem=f"{topic} feels abstract and intimidating",
                format=fmt,
                hook_options=hook_lines,
                recommended_hook=rec,
                hook_reasoning=f"'{hooks[0][0]}' opens on the viewer's belief before the topic; it is the shape "
                "behind the strongest outliers in the swipe research. Confirm with an experiment.",
                script="\n".join(s.voiceover for s in timeline),
                timeline=timeline,
                on_screen_text=[s.on_screen_text for s in timeline],
                visual_direction="Hard cuts every 2-3s; one idea per frame; captions burned in, high contrast.",
                sound_direction="Low, steady instrumental under voice; choose from Instagram's licensed library.",
                caption=f"{topic}, explained with something you already do every day.\n\nSave this for later. "
                f"Which tech idea should I explain next?",
                keywords=[
                    topic.lower(),
                    f"{topic.lower()} explained",
                    "tech for beginners",
                    "learn tech india",
                ],
                hashtags=["#techexplained", "#learntech", "#softwareengineer"],
                cta="Comment the next topic you want explained.",
                hypothesis="An everyday-analogy explainer earns saves and follows from non-technical viewers.",
                success_metrics=[
                    "views vs account median",
                    "saves per 1k reach",
                    "follows per 1k reach (account)",
                ],
                follow_up_experiment="Same topic, motion-graphics vs talking-head, 2 reels each.",
                duration_seconds=30,
            )
        )
    return S.ReelOptions(options=out).model_dump() | {
        "generated_by": "mock template - connect Bedrock for model-written scripts"
    }


def mock_schedule(ctx: ToolContext, inp: dict) -> dict:
    ideas = call_tool(ctx, "get_content_ideas", status="ready") + call_tool(
        ctx, "get_content_ideas", status="recording"
    )
    per_week = int(inp.get("posts_per_week", 4))
    issues, slots = [], []
    if not ideas:
        issues.append("No ideas are in 'ready' or 'production'. Move some forward in Content Ideas.")
    day = date.today() + timedelta(days=1)
    for idea in ideas[:per_week]:
        slots.append(
            {"idea_id": idea["id"], "title": idea["title"], "date": day.isoformat(), "time_ist": "19:00"}
        )
        day += timedelta(days=max(1, 7 // max(per_week, 1)))
    return S.ScheduleProposal(
        slots=slots,
        reasons=[
            "19:00 IST is a starting default, not a proven best time. Run the posting-window experiment "
            "to replace it with your own data."
        ],
        issues=issues,
        required_user_actions=["Approve proposed slots in the calendar"],
    ).model_dump()


def mock_community(ctx: ToolContext, inp: dict) -> dict:
    q = call_tool(ctx, "get_audience_questions")
    return S.CommunityReport(
        available=q["available"],
        common_questions=q["questions"],
        draft_responses=[],
        content_ideas=[],
        note=q["note"],
    ).model_dump()


def mock_experiment(ctx: ToolContext, inp: dict) -> dict:
    res = call_tool(ctx, "get_experiment_results")
    recs = []
    for e in res:
        r = e["result"]
        if r["status"] != "ok":
            recs.append(f"{e['name']}: keep collecting ({r['n_control']}/{r['n_variant']} so far).")
        elif r["confidence"] in ("medium", "high") and (r["lift_pct"] or 0) > 0:
            recs.append(
                f"{e['name']}: variant ahead by {r['lift_pct']}% (p={r['p_value']}). Repeat once more "
                "before adopting."
            )
        else:
            recs.append(f"{e['name']}: no reliable difference yet (p={r['p_value']}).")
    return S.ExperimentReport(
        proposal={
            "name": "Posting window",
            "variable": "publication window",
            "control": "19:00 IST",
            "variant": "13:00 IST",
            "min_samples_per_arm": 3,
        },
        analyses=res,
        recommendations=recs,
        caveats=["Posts differ in topic; results are correlational."],
    ).model_dump()


AGENTS: dict[str, AgentSpec] = {
    a.id: a
    for a in [
        AgentSpec(
            "growth_strategist",
            "Growth Strategist",
            "Find the current bottleneck and set the next action, daily and weekly priorities.",
            [
                "get_growth_target_progress",
                "get_instagram_insights",
                "get_follower_history",
                "get_top_performing_reels",
                "get_experiment_results",
                "get_content_ideas",
            ],
            S.GrowthPlan,
            "You are the growth strategist.",
            mock_growth,
        ),
        AgentSpec(
            "audience_intelligence",
            "Audience Intelligence",
            "Maintain personas and map audience problems to angles; separate observed from inferred.",
            ["get_top_performing_reels", "list_recent_media", "get_audience_questions"],
            S.AudienceReport,
            "You are the audience analyst.",
            mock_audience,
        ),
        AgentSpec(
            "content_research",
            "Content Research",
            "Research topics with an authorised provider and record sources; disclose when none ran.",
            ["search_content_library"],
            S.ResearchReport,
            "You are the content researcher.",
            mock_research,
        ),
        AgentSpec(
            "reel_creative",
            "Reel Creative",
            "Write complete, original Reel packages: hooks, script, timeline, caption, CTA.",
            ["get_top_performing_reels", "search_content_library", "save_content_draft"],
            S.ReelOptions,
            "You are the reel writer.",
            mock_reel,
        ),
        AgentSpec(
            "analytics",
            "Analytics",
            "Analyse stored insights, compare posts, flag outliers and weak patterns.",
            ["list_recent_media", "get_top_performing_reels", "get_instagram_insights", "get_media_insights"],
            S.AnalyticsReport,
            "You are the analytics agent.",
            mock_analytics,
        ),
        AgentSpec(
            "scheduling",
            "Scheduling",
            "Propose realistic calendar slots and flag missing captions or media.",
            ["get_content_ideas", "propose_calendar_change"],
            S.ScheduleProposal,
            "You are the scheduling agent.",
            mock_schedule,
        ),
        AgentSpec(
            "community_insights",
            "Community Insights",
            "Find recurring audience questions and draft replies for approval.",
            ["get_audience_questions", "create_approval_request"],
            S.CommunityReport,
            "You are the community agent.",
            mock_community,
        ),
        AgentSpec(
            "growth_experiment",
            "Growth Experiments",
            "Propose and read experiments without overclaiming.",
            ["get_experiment_results", "create_growth_experiment", "list_recent_media"],
            S.ExperimentReport,
            "You are the experiment designer.",
            mock_experiment,
        ),
    ]
}


def system_prompt(spec: AgentSpec) -> str:
    return f"{spec.prompt} {spec.responsibility}\n\n{BRAND}\n\n{RULES}"


def jsonable(x: Any) -> Any:
    from datetime import datetime

    if isinstance(x, dict):
        return {k: jsonable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [jsonable(v) for v in x]
    if isinstance(x, (datetime, date)):
        return x.isoformat()
    return x
