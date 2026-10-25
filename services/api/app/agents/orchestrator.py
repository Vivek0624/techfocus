"""Bounded agent execution and deterministic multi-agent workflows.

- Specialists never call each other. Only workflows here chain agents, at depth 1.
- A global semaphore caps concurrency; every run has a timeout.
- A run is marked 'cancelled' only after its worker has actually stopped."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutTimeout
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from ..config import Settings, get_settings
from ..models import AgentRun, DailyTask, GrowthPlan, LearningRecord, utcnow
from ..services import queries as q
from .providers import Provider, make_provider
from .registry import AGENTS
from .tools import ToolContext

log = logging.getLogger(__name__)

WORKFLOWS = {
    "daily_plan": ["analytics", "growth_strategist"],
    "weekly_review": ["analytics", "growth_experiment", "growth_strategist"],
    "reel_package": ["audience_intelligence", "reel_creative"],
}


class Orchestrator:
    def __init__(
        self,
        session_factory: sessionmaker,
        settings: Settings | None = None,
        provider: Provider | None = None,
    ):
        self.sf = session_factory
        self.s = settings or get_settings()
        self._provider = provider
        self.pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent")
        self.inner = ThreadPoolExecutor(max_workers=8, thread_name_prefix="agent-call")
        self.sem = threading.BoundedSemaphore(self.s.agent_max_concurrency)
        self.handles: dict[int, dict] = {}
        self.futures: dict[int, Future] = {}

    @property
    def provider(self) -> Provider:
        if self._provider is None:
            self._provider = make_provider(self.s)
        return self._provider

    # ---------- single agent ----------

    def create_run(self, db: Session, agent_id: str, inp: dict, parent: int | None = None) -> AgentRun:
        if agent_id not in AGENTS and agent_id not in WORKFLOWS:
            raise KeyError(agent_id)
        mode = "workflow" if agent_id in WORKFLOWS else self.s.agent_mode
        run = AgentRun(
            agent_id=agent_id,
            mode=mode,
            status="queued",
            input=inp,
            parent_run_id=parent,
            input_summary=_summ(inp),
            is_demo=q.use_demo(db),
        )
        db.add(run)
        db.flush()
        return run

    def submit(self, run_id: int, wait: bool = False) -> None:
        fut = self.pool.submit(self._execute, run_id)
        self.futures[run_id] = fut
        if wait:
            fut.result()

    def _execute(self, run_id: int) -> None:
        with self.sf() as db:
            run = db.get(AgentRun, run_id)
            if run is None:
                return
            if run.cancel_requested:
                run.status = "cancelled"
                db.commit()
                return
            if run.agent_id in WORKFLOWS:
                self._workflow(db, run)
            else:
                self._single(db, run)
            db.commit()

    def _single(self, db: Session, run: AgentRun) -> dict | None:
        spec = AGENTS[run.agent_id]
        with self.sem:
            run.status, run.started_at = "running", utcnow()
            db.commit()
            t0 = time.monotonic()
            ctx = ToolContext(db=db, run_id=run.id, allowed=set(spec.tools), demo=run.is_demo)
            handle: dict = {}
            self.handles[run.id] = handle
            fut = self.inner.submit(self.provider.run, spec, ctx, dict(run.input or {}), handle)
            try:
                res = fut.result(timeout=self.s.agent_timeout_seconds)
                db.refresh(run)
                if run.cancel_requested:
                    run.status = "cancelled"
                else:
                    run.status, run.output = "succeeded", res.output
                    run.output_summary = _out_summ(res.output)
                    run.input_tokens, run.output_tokens, run.est_cost_usd = (
                        res.input_tokens,
                        res.output_tokens,
                        res.est_cost,
                    )
            except FutTimeout:
                if handle.get("cancel"):
                    handle["cancel"]()
                run.status, run.error = "failed", f"timed out after {self.s.agent_timeout_seconds}s"
            except Exception as e:  # provider/model/tool errors become a failed run, never a crash
                log.exception("agent run %s failed", run.id)
                run.status, run.error = "failed", _safe_err(e)
            finally:
                self.handles.pop(run.id, None)
            run.finished_at = utcnow()
            run.duration_ms = int((time.monotonic() - t0) * 1000)
            db.commit()
            return run.output if run.status == "succeeded" else None

    def _workflow(self, db: Session, run: AgentRun) -> None:
        run.status, run.started_at = "running", utcnow()
        db.commit()
        t0 = time.monotonic()
        steps, failures, carry = [], [], dict(run.input or {})
        for agent_id in WORKFLOWS[run.agent_id]:
            db.refresh(run)
            if run.cancel_requested:
                failures.append("cancelled by user before " + agent_id)
                break
            child = self.create_run(db, agent_id, carry, parent=run.id)
            db.commit()
            out = self._single(db, child)
            steps.append({"agent_id": agent_id, "run_id": child.id, "status": child.status})
            if out is None:
                failures.append(f"{agent_id}: {child.error}")
                continue
            carry = {**carry, f"{agent_id}_result": _out_summ(out)}
            if agent_id == "growth_strategist" and run.agent_id in ("daily_plan", "weekly_review"):
                self._store_plan(db, run, out)
            if agent_id == "reel_creative":
                run.output = {"reel": out}
        db.refresh(run)
        run.output = {**(run.output or {}), "steps": steps, "failures": failures}
        run.status = (
            "cancelled"
            if run.cancel_requested
            else ("failed" if len(failures) == len(steps) else "succeeded")
        )
        run.output_summary = f"{len(steps) - len(failures)}/{len(steps)} steps succeeded"
        run.finished_at, run.duration_ms = utcnow(), int((time.monotonic() - t0) * 1000)

    def _store_plan(self, db: Session, run: AgentRun, plan: dict) -> None:
        today = date.today()
        db.add(
            GrowthPlan(
                period="weekly" if run.agent_id == "weekly_review" else "daily",
                plan_date=today,
                content=plan,
                agent_run_id=run.id,
                is_demo=run.is_demo,
            )
        )
        if run.agent_id == "daily_plan":
            for i, title in enumerate([plan["next_action"], *plan.get("daily_priorities", [])]):
                db.add(
                    DailyTask(
                        task_date=today,
                        title=title[:200],
                        reason="from growth plan",
                        impact=3 if i == 0 else 2,
                        effort_minutes=45 if i == 0 else 30,
                        priority=10 - i,
                        is_demo=run.is_demo,
                    )
                )
        else:
            db.add(
                LearningRecord(
                    kind="decision",
                    statement=plan["next_action"],
                    evidence={"plan": plan},
                    confidence=plan.get("confidence", "low"),
                    decision="test_more",
                    is_demo=run.is_demo,
                )
            )

    # ---------- control ----------

    def cancel(self, db: Session, run_id: int) -> str:
        run = db.get(AgentRun, run_id)
        if run is None:
            raise KeyError(run_id)
        if run.status in ("succeeded", "failed", "cancelled"):
            return run.status
        run.cancel_requested = True
        if run.status == "queued":
            fut = self.futures.get(run_id)
            if fut is not None and fut.cancel():
                run.status = "cancelled"
            return run.status if run.status == "cancelled" else "cancelling"
        h = self.handles.get(run_id)
        if h and h.get("cancel"):
            h["cancel"]()
        return "cancelling"  # becomes 'cancelled' only when the worker observes it


def _summ(d: dict) -> str:
    keys = [k for k in d if not k.endswith("_result")]
    return ", ".join(f"{k}={str(d[k])[:40]}" for k in keys)[:300] or "(no input)"


def _out_summ(o: dict) -> str:
    for k in ("next_action", "recommended_action", "summary", "bottleneck"):
        if isinstance(o.get(k), str):
            return o[k][:300]
    if "options" in o:
        return f"{len(o['options'])} reel option(s): " + "; ".join(
            x["recommended_hook"][:60] for x in o["options"]
        )
    if "insights" in o:
        return f"{len(o['insights'])} audience insights"
    if "recommendations" in o:
        return "; ".join(o["recommendations"])[:300]
    if "slots" in o:
        return f"{len(o['slots'])} proposed slots"
    return str(o)[:300]


def _safe_err(e: Exception) -> str:
    from ..security import redact

    name = type(e).__name__
    msg = redact(str(e))[:400]
    if "AccessDenied" in msg or "UnrecognizedClient" in msg or "NoCredentials" in name:
        return f"{name}: AWS credentials or model access missing. See docs/aws-setup.md."
    return f"{name}: {msg}"
