"""Reel Planner endpoints, used by Ideas -> Reel Planner.

    POST   /api/reels/trends                 niche -> 8-10 topic candidates (+ sources when live)
    POST   /api/reels/plan                   one topic -> a complete reel package, saved
    GET    /api/reels/plans                  "My reel plans"
    GET    /api/reels/plans/{id}             reopen one
    POST   /api/reels/plans/{id}/regenerate  redo one section (hooks | script | shots | caption | cta)
    DELETE /api/reels/plans/{id}
    GET    /api/reels/meta                   niche prefill, platforms, provider status

Read-only against Instagram. Nothing here publishes.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import ContentIdea, ReelPlan
from ..services import queries as q
from ..services import reel_prompts, reelplanner, trends

router = APIRouter(prefix="/reels")

Platform = Literal["instagram_reels", "youtube_shorts", "tiktok"]
Section = Literal["hooks", "script", "shots", "caption", "cta"]

NICHE_KEY = "reel_planner_niche"


class TrendsReq(BaseModel):
    niche: str = Field(min_length=2, max_length=200)
    platform: Platform = "instagram_reels"
    count: int = Field(default=reelplanner.TOPIC_COUNT, ge=4, le=10)
    audience: str | None = Field(default=None, max_length=300)


class PlanReq(BaseModel):
    niche: str = Field(min_length=2, max_length=200)
    platform: Platform = "instagram_reels"
    topic: dict = Field(description="the selected TrendTopic, as returned by /reels/trends")
    duration: int = Field(default=reelplanner.DEFAULT_DURATION, ge=15, le=45)
    audience: str | None = Field(default=None, max_length=300)
    save: bool = True


class RegenReq(BaseModel):
    section: Section


def _niche_prefill(db: Session) -> str:
    """Last niche used, else the strongest topic already in the notebook, else nothing."""
    saved = q.get_setting(db, NICHE_KEY)
    if isinstance(saved, str) and saved.strip():
        return saved.strip()
    row = db.scalar(
        select(ReelPlan).where(ReelPlan.is_demo.is_(q.use_demo(db))).order_by(ReelPlan.created_at.desc())
    )
    if row:
        return row.niche
    idea = db.scalar(
        select(ContentIdea)
        .where(ContentIdea.is_demo.is_(q.use_demo(db)), ContentIdea.pillar.is_not(None))
        .order_by(ContentIdea.updated_at.desc())
    )
    return (idea.pillar or "").replace("_", " ") if idea else ""


@router.get("/meta")
def meta(db: Session = Depends(get_db)):
    s = get_settings()
    provider = trends.get_provider(s)
    return {
        "niche": _niche_prefill(db),
        "platforms": [{"value": p, "label": reel_prompts.PLATFORM_LABEL[p]} for p in reel_prompts.PLATFORMS],
        "default_platform": reelplanner.DEFAULT_PLATFORM,
        "sections": list(reelplanner.SECTION_SCHEMAS),
        "live_research_available": provider.live,
        "research_provider": provider.name,
        "video_autoedit_available": False,
        "note": "Topics come from a live search provider when RESEARCH_API_URL is set. Without it they "
        "are written from model knowledge only and labelled that way.",
    }


@router.post("/trends")
def post_trends(body: TrendsReq, db: Session = Depends(get_db)):
    q.set_setting(db, NICHE_KEY, body.niche.strip())
    return reelplanner.find_trends(db, body.niche.strip(), body.platform, body.count, body.audience)


@router.post("/plan")
def post_plan(body: PlanReq, db: Session = Depends(get_db)):
    if not (body.topic.get("title") or "").strip():
        raise HTTPException(422, "topic.title is required; pick a topic from /reels/trends first")
    q.set_setting(db, NICHE_KEY, body.niche.strip())
    plan, source = reelplanner.build_plan(
        db, body.topic, body.niche.strip(), body.platform, body.duration, body.audience
    )
    live = bool(body.topic.get("sources"))
    if not body.save:
        return {"saved": False, "source": source, "package": plan.model_dump()}
    row = reelplanner.save(db, body.niche.strip(), body.platform, body.topic, plan, source, live)
    return {"saved": True, "source": source, **reelplanner.to_dict(row)}


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    return {"items": reelplanner.listing(db)}


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    row = reelplanner.get(db, plan_id)
    if row is None:
        raise HTTPException(404, "reel plan not found")
    return reelplanner.to_dict(row)


@router.post("/plans/{plan_id}/regenerate")
def regenerate(plan_id: int, body: RegenReq, db: Session = Depends(get_db)):
    row = reelplanner.get(db, plan_id)
    if row is None:
        raise HTTPException(404, "reel plan not found")
    pkg, source = reelplanner.regenerate_section(db, row, body.section)
    return {"section": body.section, "source": source, **reelplanner.to_dict(row)}


@router.delete("/plans/{plan_id}", status_code=204)
def delete_plan(plan_id: int, db: Session = Depends(get_db)):
    row = reelplanner.get(db, plan_id)
    if row is None:
        raise HTTPException(404, "reel plan not found")
    reelplanner.delete(db, row)
    return None
