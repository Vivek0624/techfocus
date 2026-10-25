"""Every prompt the Reel Planner sends to a model lives here, so tuning the output never means
touching routing or storage code.

Three jobs: find trending topics, turn one topic into a shootable reel, and redo a single section
of an existing reel. The house rules in agents/registry.py (BRAND, RULES) are prepended by
creator.generate_with_model, so these strings only carry the craft instructions.
"""

from __future__ import annotations

import json

PLATFORMS = ("instagram_reels", "youtube_shorts", "tiktok")

PLATFORM_LABEL = {
    "instagram_reels": "Instagram Reels",
    "youtube_shorts": "YouTube Shorts",
    "tiktok": "TikTok",
}

# Platform-specific craft notes. Short on purpose: the model gets one paragraph, not a manual.
PLATFORM_NOTES = {
    "instagram_reels": (
        "Instagram Reels: 15-40s works best. Saves and shares matter more than likes. The caption's "
        "first line is the only one most people read. Burned-in captions are expected."
    ),
    "youtube_shorts": (
        "YouTube Shorts: viewers tolerate up to 45s if the payoff grows. The title/first frame carries "
        "more weight than the caption. Searchable phrasing helps; shorts resurface weeks later."
    ),
    "tiktok": (
        "TikTok: fastest cuts of the three, 15-30s. Comment bait and a rewatchable loop beat polish. "
        "Spoken language should sound like talking to a friend, not presenting."
    ),
}

# ---------------- shared craft rules ----------------

CRAFT = """How short-form that actually travels is written:
- ONE idea per reel. If you can split it in two, you have two reels. Cut the second one.
- The hook is a pattern interrupt, not a topic announcement. Never open with "In this video" or
  "Today I'll explain" or "Let's talk about". Open on the viewer's belief, their cost, or a
  concrete moment.
- Spoken word, not written word. Short lines. Say it out loud as you write it. No semicolons, no
  em dashes, no "furthermore", no "in today's fast-paced world".
- Zero filler. Every line either earns the next second or gets deleted. No "so basically", no
  restating the hook, no sign-off chatter.
- Be specific. Real numbers, real tools, real situations the audience has lived. "Use AI to be
  productive" is useless. "I gave my standup notes to one prompt for a week" is a reel.
- No generic advice. If the line would fit any niche, it is wrong for this one.
- One CTA, one action. "Comment X" or "Save this" or "Follow for Y" - never two at once.
- Tailor every line to the stated niche and audience: their words, their tools, their frustrations.
"""

NO_INVENTION = """Honesty rules you cannot break:
- Never invent a trend, a statistic, a source, or a URL. If you did not receive it in the input,
  you do not have it.
- Only list a source you were given in SEARCH RESULTS, copied exactly.
- When you have no search results, say so in the disclosure and return sources as empty lists.
"""


def _ctx(niche: str, platform: str, audience: str | None, voice: dict | None) -> str:
    lines = [
        f"NICHE: {niche}",
        f"PLATFORM: {PLATFORM_LABEL.get(platform, platform)}",
        PLATFORM_NOTES.get(platform, ""),
    ]
    if audience:
        lines.append(f"AUDIENCE: {audience}")
    if voice:
        tone = ", ".join(voice.get("tone_words") or [])
        banned = ", ".join(voice.get("banned_words") or [])
        if tone:
            lines.append(f"VOICE - sound like this: {tone}")
        if banned:
            lines.append(f"VOICE - never use these words: {banned}")
        if voice.get("preferred_cta"):
            lines.append(f"VOICE - preferred CTA: {voice['preferred_cta']}")
        if voice.get("signature_hashtags"):
            lines.append(f"VOICE - signature hashtags: {' '.join(voice['signature_hashtags'])}")
    return "\n".join(x for x in lines if x)


# ---------------- 1. trends ----------------


def trends(
    niche: str,
    platform: str,
    count: int,
    audience: str | None = None,
    voice: dict | None = None,
    results: list[dict] | None = None,
) -> str:
    """Prompt for the topic-discovery step. `results` are live search hits, or None for no live search."""
    if results:
        found = json.dumps(results, ensure_ascii=False)[:12000]
        evidence = (
            f"SEARCH RESULTS (live, from the configured search provider; these are your only facts):\n{found}\n\n"
            "Ground every topic in these results. Copy source titles and URLs exactly from them. "
            "Set live_research_performed = true. Disclosure: say the topics come from live search on "
            "today's results and that the creator should still check each link before filming."
        )
    else:
        evidence = (
            "NO SEARCH RESULTS. No search provider is configured, so you have no live data.\n"
            "Work from what you already know about this niche's recurring, durable interest patterns. "
            "Return sources as empty lists. Set live_research_performed = false. Disclosure must start "
            'with "Model knowledge only, not live" and tell the creator to verify before filming.'
        )
    return f"""Find {count} short-form video topics worth filming in this niche.

{_ctx(niche, platform, audience, voice)}

{evidence}

For each topic give:
- title: the reel subject, phrased the way the creator would say it out loud. Not a headline.
- why_trending: what is pulling attention to it right now. Concrete. If it is a durable
  evergreen pull rather than a spike, say that honestly.
- angle: the specific take for THIS audience. Not the generic version everyone posts.
- engagement_potential: high / medium / low, and potential_reason in one line.

Spread the {count} topics across different shapes: something contrarian, something painfully
practical, something explained through a concrete everyday example, something career-shaped.
Do not give {count} variations of one topic.

{CRAFT}
{NO_INVENTION}"""


# ---------------- 2. full reel plan ----------------


def reel_plan(
    topic: dict,
    niche: str,
    platform: str,
    duration: int,
    audience: str | None = None,
    voice: dict | None = None,
) -> str:
    """Prompt for the full shootable package from one chosen topic."""
    return f"""Write one complete, shootable reel for this topic. The creator films it today.

TOPIC: {topic.get("title")}
WHY IT IS GETTING ATTENTION: {topic.get("why_trending") or "not given"}
THE ANGLE: {topic.get("angle") or "not given"}

{_ctx(niche, platform, audience, voice)}

TARGET LENGTH: about {duration} seconds. total_duration_seconds must be between 15 and 45 and
must match the sum of your shot lengths and the end of your last script section.

Deliver:
1. one_idea: the single idea this reel delivers, in one sentence. Everything else serves it.
2. hooks: exactly 3 versions of the first 1-3 seconds, each a DIFFERENT hook_type, each under
   14 words, each one a pattern interrupt. Say why each one works.
3. script: sections hook, setup, value, payoff, cta, with t_start and t_end in seconds and no
   gaps between them. `spoken` is what the creator says out loud: short lines, natural rhythm,
   written to be read off a phone while filming. `on_screen_text` is at most 7 words.
4. shots: shot-by-shot directions in order. Each one: shot_type, framing, location/background,
   action, delivery_tone (pace, energy, where to pause), b_roll ideas, seconds. The cuts should
   land where the script changes gear.
5. caption: real line breaks. First line stands alone and works even if nothing below it is read.
6. hashtags: 5-8, mixed broad and niche. No hashtag soup, no banned-word hashtags.
7. pinned_comment: the comment the creator pins to steer the conversation.
8. cta_primary: one action, tied to the payoff. cta_alternative: a different single action.
9. audio_direction: the kind of track and how it sits under the voice. Direction only, do not
   claim any specific song is licensed or trending.
10. best_posting_time: a window in IST plus the reason. Say plainly that it is a starting
    default to test, not a measured best time.
11. ab_test_idea: one variable to change, and what the result would teach.

{CRAFT}
{NO_INVENTION}"""


# ---------------- 3. regenerate one section ----------------

SECTIONS = ("hooks", "script", "shots", "caption", "cta")

_SECTION_BRIEF = {
    "hooks": (
        "Rewrite ONLY the 3 hooks. Keep the same idea and audience. Use three hook_types that are "
        "different from each other AND different from the ones below. Harder pattern interrupts."
    ),
    "script": (
        "Rewrite ONLY the script sections. Same idea, same total length. Tighter lines, fewer words, "
        "more concrete. Keep t_start/t_end continuous with no gaps."
    ),
    "shots": (
        "Rewrite ONLY the shot list. Same script, same total length. More filmable with one phone and "
        "no crew. Vary framing so no two neighbouring shots look alike."
    ),
    "caption": (
        "Rewrite ONLY the caption, hashtags and pinned comment. First caption line must stand alone. "
        "Keep 5-8 hashtags."
    ),
    "cta": (
        "Rewrite ONLY the two CTAs. One action each, both tied to this reel's payoff, clearly "
        "different from each other."
    ),
}


def regenerate(section: str, plan: dict, niche: str, platform: str, audience: str | None = None) -> str:
    """Prompt to redo one part of a saved plan without touching the rest."""
    keep = {
        "topic": plan.get("topic"),
        "one_idea": plan.get("one_idea"),
        "total_duration_seconds": plan.get("total_duration_seconds"),
        "script": plan.get("script") if section in ("shots", "cta", "caption") else None,
        "hooks": plan.get("hooks") if section == "hooks" else None,
    }
    keep = {k: v for k, v in keep.items() if v is not None}
    return f"""{_SECTION_BRIEF.get(section, "Rewrite this section.")}

{_ctx(niche, platform, audience, None)}

THE REEL SO FAR (do not change anything outside the section you were asked for):
{json.dumps(keep, ensure_ascii=False)[:8000]}

{CRAFT}
{NO_INVENTION}"""
