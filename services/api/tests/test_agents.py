import time

from sqlalchemy import select

from app.agents import schemas as S
from app.agents.registry import AGENTS
from app.agents.tools import ToolContext, ToolError, call_tool
from app.db import SessionLocal
from app.models import ToolCallAudit


def _wait(client, run_id, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = client.get(f"/api/agent-runs/{run_id}").json()
        if r["status"] in ("succeeded", "failed", "cancelled"):
            return r
        time.sleep(0.1)
    raise AssertionError("run did not finish")


def test_every_agent_runs_in_mock_and_validates(client):
    for aid, spec in AGENTS.items():
        r = client.post(f"/api/agents/{aid}/run", json={"input": {"topic": "APIs"}, "wait": True})
        assert r.status_code == 202
        run = _wait(client, r.json()["id"])
        assert run["status"] == "succeeded", (aid, run["error"])
        spec.output.model_validate({k: v for k, v in run["output"].items() if k != "generated_by"})


def test_reel_package_shape(client):
    run = _wait(
        client,
        client.post(
            "/api/agents/reel_creative/run", json={"input": {"topic": "UPI", "options": 2}, "wait": True}
        ).json()["id"],
    )
    opts = S.ReelOptions.model_validate({"options": run["output"]["options"]}).options
    assert len(opts) == 2
    for o in opts:
        assert len(o.hook_options) == 3 and o.recommended_hook in o.hook_options
        assert o.timeline[0].t_start == 0


def test_simulated_failure_and_retry(client):
    run = _wait(
        client,
        client.post(
            "/api/agents/analytics/run", json={"input": {"simulate_failure": True}, "wait": True}
        ).json()["id"],
    )
    assert run["status"] == "failed" and "simulated" in run["error"]
    retry = client.post(f"/api/agent-runs/{run['id']}/retry").json()
    assert _wait(client, retry["id"])["status"] == "succeeded"
    assert client.post(f"/api/agent-runs/{retry['id']}/retry").status_code == 409


def test_workflow_records_children_and_plan(client):
    run = _wait(client, client.post("/api/agents/daily_plan/run", json={"wait": True}).json()["id"])
    assert run["status"] == "succeeded"
    steps = run["output"]["steps"]
    assert [s["agent_id"] for s in steps] == ["analytics", "growth_strategist"]
    child = client.get(f"/api/agent-runs/{steps[1]['run_id']}").json()
    assert child["parent_run_id"] == run["id"]
    assert "get_growth_target_progress" in child["tools_called"]
    assert len(client.get("/api/growth/daily-plan").json()) > 0


def test_cancel_finished_run_is_not_cancelled(client):
    run = _wait(client, client.post("/api/agents/analytics/run", json={"wait": True}).json()["id"])
    assert client.post(f"/api/agent-runs/{run['id']}/cancel").json()["state"] == "succeeded"


def test_unknown_agent(client):
    assert client.post("/api/agents/nope/run", json={}).status_code == 404


def test_tool_permissions_enforced_and_audited():
    with SessionLocal() as db:
        ctx = ToolContext(db=db, run_id=None, allowed={"get_account_summary"}, demo=True)
        call_tool(ctx, "get_account_summary")
        try:
            call_tool(ctx, "save_content_draft", title="x", pillar="p", recommended_hook="h")
            raise AssertionError("should be denied")
        except ToolError:
            pass
        db.flush()
        rows = db.scalars(select(ToolCallAudit).where(ToolCallAudit.tool == "save_content_draft")).all()
        assert rows and rows[-1].ok is False
        db.rollback()


def test_agents_cannot_mark_published():
    with SessionLocal() as db:
        ctx = ToolContext(
            db=db, run_id=None, allowed={"update_content_status", "save_content_draft"}, demo=True
        )
        d = call_tool(ctx, "save_content_draft", title="x", pillar="p", recommended_hook="h")
        try:
            call_tool(ctx, "update_content_status", idea_id=d["id"], status="published")
            raise AssertionError
        except ToolError:
            pass
        db.rollback()


def test_no_publishing_tool_exists():
    from app.agents.tools import TOOLS

    assert not any("publish" in n and n != "create_approval_request" for n in TOOLS)
