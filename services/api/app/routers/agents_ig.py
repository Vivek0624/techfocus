"""Agents, Instagram connection/sync/publish, AWS platform status."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..agents.orchestrator import WORKFLOWS
from ..agents.registry import AGENTS
from ..config import get_settings
from ..db import get_db
from ..instagram import client as ig
from ..instagram import service as igs
from ..models import AgentRun, ApprovalRequest, CalendarItem, ToolCallAudit, iso_utc
from ..schemas import AgentRunIn, AgentRunOut, CalendarOut, Page
from ..security import consume_oauth_state, get_cipher, new_oauth_state
from ..services import queries as q
from ..services.activity import sync_activity

router = APIRouter()
log = logging.getLogger(__name__)


def _orch(request: Request):
    return request.app.state.orchestrator


def _client_factory(request: Request):
    return request.app.state.instagram_client_factory


# ---------------- agents ----------------


def _run_out(db: Session, r: AgentRun) -> AgentRunOut:
    out = AgentRunOut.model_validate(r)
    out.tools_called = list(db.scalars(select(ToolCallAudit.tool).where(ToolCallAudit.run_id == r.id)))
    return out


@router.get("/agents")
def list_agents(db: Session = Depends(get_db)):
    s = get_settings()
    demo = q.use_demo(db)
    res = []
    for a in AGENTS.values():
        last = db.scalar(
            select(AgentRun)
            .where(AgentRun.agent_id == a.id, AgentRun.is_demo.is_(demo))
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        res.append(
            {
                "id": a.id,
                "name": a.name,
                "responsibility": a.responsibility,
                "tools": a.tools,
                "kind": "specialist",
                "mode": s.agent_mode,
                "write_tools": [
                    t for t in a.tools if t.startswith(("save_", "update_", "create_", "propose_"))
                ],
                "last_run": _run_out(db, last).model_dump(mode="json") if last else None,
            }
        )
    for wid, steps in WORKFLOWS.items():
        last = db.scalar(
            select(AgentRun)
            .where(AgentRun.agent_id == wid, AgentRun.is_demo.is_(demo))
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        res.append(
            {
                "id": wid,
                "name": wid.replace("_", " ").title() + " (workflow)",
                "responsibility": " → ".join(steps),
                "tools": [],
                "kind": "workflow",
                "mode": s.agent_mode,
                "write_tools": [],
                "last_run": _run_out(db, last).model_dump(mode="json") if last else None,
            }
        )
    return res


@router.post("/agents/{agent_id}/run", response_model=AgentRunOut, status_code=202)
def run_agent(agent_id: str, body: AgentRunIn, request: Request, db: Session = Depends(get_db)):
    orch = _orch(request)
    try:
        run = orch.create_run(db, agent_id, body.input)
    except KeyError as e:
        raise HTTPException(404, "unknown agent") from e
    db.commit()
    orch.submit(run.id, wait=body.wait)
    db.refresh(run)
    return _run_out(db, run)


@router.get("/agent-runs", response_model=Page[AgentRunOut])
def list_runs(
    agent_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    stmt = select(AgentRun).where(AgentRun.is_demo.is_(q.use_demo(db)))
    if agent_id:
        stmt = stmt.where(AgentRun.agent_id == agent_id)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(AgentRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return Page[AgentRunOut](
        items=[_run_out(db, r) for r in rows], total=total, page=page, page_size=page_size
    )


@router.get("/agent-runs/{run_id}", response_model=AgentRunOut)
def get_run(run_id: int, db: Session = Depends(get_db)):
    r = db.get(AgentRun, run_id)
    if r is None:
        raise HTTPException(404, "run not found")
    return _run_out(db, r)


@router.post("/agent-runs/{run_id}/cancel")
def cancel_run(run_id: int, request: Request, db: Session = Depends(get_db)):
    try:
        state = _orch(request).cancel(db, run_id)
    except KeyError as e:
        raise HTTPException(404, "run not found") from e
    return {"run_id": run_id, "state": state}


@router.post("/agent-runs/{run_id}/retry", response_model=AgentRunOut, status_code=202)
def retry_run(run_id: int, request: Request, db: Session = Depends(get_db)):
    old = db.get(AgentRun, run_id)
    if old is None:
        raise HTTPException(404, "run not found")
    if old.status not in ("failed", "cancelled"):
        raise HTTPException(409, "only failed or cancelled runs can be retried")
    inp = {k: v for k, v in (old.input or {}).items() if k != "simulate_failure"}
    return run_agent(old.agent_id, AgentRunIn(input=inp), request, db)


# ---------------- instagram ----------------


@router.get("/instagram/status")
def ig_status(db: Session = Depends(get_db)):
    s = get_settings()
    acct = igs.live_account(db)
    acct = acct if acct and acct.token else None
    return {
        "app_configured": bool(s.meta_app_id and s.meta_app_secret),
        "encryption_key_set": s.token_encryption_key is not None,
        "connected": acct is not None,
        "username": acct.username if acct else None,
        "account_type": acct.account_type if acct else None,
        "last_sync_at": iso_utc(acct.last_sync_at) if acct and acct.last_sync_at else None,
        "last_error": acct.last_error if acct else None,
        "auto_sync": {
            "enabled": s.enable_local_scheduler,
            "schedule": "Every day at 06:30 IST while the app is running (read-only)",
            "last": q.get_setting(db, "auto_sync"),
        },
        "token": igs.token_status(acct),
        "permissions": igs.permission_diagnostics(acct),
        "auth_flow": "Instagram API with Instagram Login (graph.instagram.com)",
        "requirements": [
            "The Instagram account must be a professional (Creator or Business) account.",
            "Your Meta app must have Instagram product with Business Login configured and the redirect URI "
            f"{s.meta_redirect_uri} added.",
            "While the app is in Development mode, only accounts added as Instagram testers can connect.",
        ],
    }


CAPABILITIES = [
    # (what, plain words, status, why)
    ("Profile, followers, media list", "Your name, follower count and every post.", "used", None),
    (
        "Reel and post numbers",
        "Plays, people reached, likes, comments, shares, saves for each post.",
        "used",
        None,
    ),
    ("Watch time", "Average seconds watched and total watch time per reel.", "used", None),
    ("Account numbers per day", "Reach, plays, interactions and follows for the account.", "used", None),
    (
        "Audience",
        "Age, gender, cities, countries and the hours your followers are online (100+ followers).",
        "used",
        None,
    ),
    (
        "Comments and replies",
        "Read comments and full reply threads on your posts; reply or hide one when you press the button.",
        "used",
        None,
    ),
    ("Tags / mentions", "Posts where someone tagged you.", "used", None),
    (
        "Publishing",
        "Post a reel, a single photo or a carousel after you approve it. Instagram must be able to "
        "download the files from a public https link.",
        "used",
        None,
    ),
    ("Daily auto-update", "This app re-reads your numbers once a day while it is running.", "used", None),
    (
        "Real-time comments and mentions",
        "Instant alerts when someone comments or mentions you.",
        "needs_server",
        "Needs webhooks, which need a public server Instagram can reach. This app runs only on your laptop.",
    ),
    (
        "Story numbers",
        "Story replies and exits are only kept by Instagram for 24 hours.",
        "needs_server",
        "Would need a sync running every few hours or webhooks.",
    ),
    (
        "Your saved and liked posts",
        "What you save or like on Instagram.",
        "not_possible",
        "The API never shares this. Use Settings > Import your Instagram data instead.",
    ),
    (
        "Other accounts' numbers",
        "Followers, plays or posts of other creators.",
        "not_possible",
        "Not allowed by the API (and scraping breaks Instagram's terms).",
    ),
    (
        "Trending audio, hashtags or topics",
        "What is trending right now.",
        "not_possible",
        "Instagram doesn't offer trends through the API.",
    ),
    (
        "DMs",
        "Reading or sending direct messages.",
        "not_used",
        "Possible with extra permissions, but this app deliberately doesn't automate messages.",
    ),
]


@router.get("/instagram/capabilities")
def ig_capabilities():
    return [{"what": w, "plain": p, "status": st, "why": why} for w, p, st, why in CAPABILITIES]


@router.get("/instagram/connect")
def ig_connect(db: Session = Depends(get_db)):
    s = get_settings()
    if not s.instagram_configured:
        raise HTTPException(
            503,
            "Set META_APP_ID, META_APP_SECRET and TOKEN_ENCRYPTION_KEY in .env "
            "(see docs/instagram-setup.md).",
        )
    state = new_oauth_state(db)
    return {"authorize_url": ig.authorize_url(s, state)}


@router.get("/instagram/callback")
def ig_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
    db: Session = Depends(get_db),
):
    s = get_settings()
    back = f"{s.web_origin}/instagram"
    if error:
        return RedirectResponse(f"{back}?{urlencode({'error': error[:100]})}")
    if not consume_oauth_state(db, state):
        db.commit()
        return RedirectResponse(f"{back}?error=invalid_state")
    if not code:
        return RedirectResponse(f"{back}?error=missing_code")
    try:
        tok = ig.exchange_code(s, code.removesuffix("#_"))
        client = _client_factory(request)(tok["access_token"], "me")
        profile = client.get_profile()
        acct = igs.store_connection(db, get_cipher(), tok, profile)
        db.commit()
        try:
            igs.sync_account(db, acct, client)
            sync_activity(db, acct, client)
        except Exception as e:  # first sync failure must not lose the connection
            acct.last_error = f"initial sync failed: {type(e).__name__}"
        db.commit()
    except ig.InstagramAPIError as e:
        log.warning("oauth exchange failed: %s", e)
        return RedirectResponse(f"{back}?error=exchange_failed")
    return RedirectResponse(f"{back}?connected=1")


@router.post("/instagram/disconnect")
def ig_disconnect(db: Session = Depends(get_db)):
    acct = igs.live_account(db)
    if acct is None:
        raise HTTPException(404, "no connected account")
    igs.disconnect(db, acct)
    return {
        "ok": True,
        "note": "Token deleted locally. Also remove the app in Instagram > Settings > "
        "Apps and websites to revoke access on Meta's side.",
    }


def _live_client(request: Request, db: Session):
    acct = igs.live_account(db)
    if acct is None or acct.token is None:
        raise HTTPException(409, "Instagram is not connected")
    st = igs.token_status(acct)
    if st["state"] == "expired":
        raise HTTPException(401, "Instagram token expired; reconnect")
    cipher = get_cipher()
    try:
        igs.maybe_refresh(db, get_settings(), cipher, acct)
    except ig.InstagramAPIError as e:
        log.warning("token refresh failed: %s", e)
    return acct, _client_factory(request)(cipher.decrypt(acct.token.ciphertext), acct.ig_user_id)


@router.post("/instagram/sync")
def ig_sync(
    request: Request, media_limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)
):
    acct, client = _live_client(request, db)
    try:
        res = igs.sync_account(db, acct, client, media_limit)
        db.commit()
        res["activity"] = sync_activity(db, acct, client)  # comments, mentions, audience; each part optional
        return res
    except ig.InstagramAPIError as e:
        acct.last_error = str(e)[:300]
        db.commit()
        raise HTTPException(502, f"Instagram API error: {e}") from e


@router.get("/instagram/media")
def ig_media(db: Session = Depends(get_db)):
    if q.data_mode(db) != "live":
        return {"connected": False, "items": [], "note": "Connect Instagram to see real media."}
    return {"connected": True, "items": q.media_with_latest(db, demo=False)}


@router.get("/instagram/insights")
def ig_insights(days: int = Query(default=30, ge=1, le=90), db: Session = Depends(get_db)):
    if q.data_mode(db) != "live":
        return {"connected": False, "note": "Connect Instagram to see real insights."}
    return {"connected": True, **q.account_insights_window(db, False, days)}


@router.post("/calendar/{item_id}/request-publish")
def request_publish(item_id: int, db: Session = Depends(get_db)):
    item = db.get(CalendarItem, item_id)
    if item is None:
        raise HTTPException(404, "calendar item not found")
    ap = igs.request_publish_approval(db, item)
    return {
        "approval_id": ap.id,
        "status": ap.status,
        "preview": {
            "title": item.title,
            "caption": item.caption,
            "video_url": item.asset_ref,
            "scheduled_at": iso_utc(item.scheduled_at),
            "timezone": item.timezone,
        },
    }


@router.post("/approvals/{aid}/execute")
def execute_approval(aid: int, request: Request, db: Session = Depends(get_db)):
    ap = db.get(ApprovalRequest, aid)
    if ap is None:
        raise HTTPException(404, "approval not found")
    if ap.status != "approved":
        raise HTTPException(403, "approval is not approved")
    acct = igs.live_account(db)
    if acct is None or "instagram_business_content_publish" not in (acct.granted_scopes or []):
        raise HTTPException(
            403, "instagram_business_content_publish was not granted; use the manual checklist"
        )
    _, client = _live_client(request, db)
    job = igs.execute_publish(db, ap, client, poll=lambda: time.sleep(60))
    item = db.get(CalendarItem, ap.target_id)
    return {
        "job_status": job.status,
        "media_id": job.media_id,
        "error": job.error,
        "item": CalendarOut.model_validate(item).model_dump(mode="json") if item else None,
    }


# ---------------- AWS platform ----------------


@router.get("/aws/status")
def aws_status():
    s = get_settings()
    out: dict = {
        "agent_mode": s.agent_mode,
        "region": s.aws_region,
        "profile": s.aws_profile,
        "bedrock_model_id": s.bedrock_model_id,
        "agentcore_runtime_arn_set": bool(s.agentcore_runtime_arn),
        "credentials": None,
        "checked_at": datetime.now(UTC).isoformat(),
    }
    try:
        import boto3

        sess = boto3.Session(profile_name=s.aws_profile, region_name=s.aws_region)
        creds = sess.get_credentials()
        out["credentials"] = "found" if creds else "not found"
    except Exception as e:
        out["credentials"] = f"error: {type(e).__name__}"
    out["services"] = [
        {"name": "Amazon Bedrock Runtime", "phase": "B (local Bedrock)", "needed": s.agent_mode != "mock"},
        {"name": "Strands Agents", "phase": "B", "needed": s.agent_mode == "bedrock"},
        {"name": "AgentCore Runtime", "phase": "C (cloud agents)", "needed": s.agent_mode == "agentcore"},
        {"name": "AgentCore Observability / CloudWatch", "phase": "C", "needed": s.agent_mode == "agentcore"},
        {"name": "AgentCore Memory", "phase": "C, optional", "needed": False},
        {
            "name": "Amazon S3 (public media for publishing)",
            "phase": "publishing",
            "needed": bool(s.s3_media_bucket),
        },
        {
            "name": "EventBridge Scheduler + Step Functions",
            "phase": "cloud scheduling, optional",
            "needed": False,
        },
    ]
    return out
