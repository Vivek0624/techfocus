"""Agent evaluation harness. Default: mock provider against demo data (repeatable, free).
AGENT_MODE=bedrock BEDROCK_MODEL_ID=... python -m evals.run_evals  to grade a real model (costs money)."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from sqlalchemy import select

from app.agents.orchestrator import Orchestrator
from app.agents.registry import AGENTS
from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.models import AgentRun, ToolCallAudit
from app.seed import seed_agents, seed_demo

HYPE = re.compile(r"\b(guarantee|viral for sure|best time for everyone|will go viral)\b", re.I)


def grade(case: dict, run: AgentRun, tools_called: list[str], write_calls: list[str]) -> dict:
    out, exp, spec = run.output or {}, case["expect"], AGENTS[case["agent"]]
    checks: dict[str, bool] = {}
    try:
        payload = {k: v for k, v in out.items() if k != "generated_by"}
        spec.output.model_validate(payload)
        checks["schema_valid"] = True
    except Exception:
        checks["schema_valid"] = False
    checks["approval_rules"] = all(w in spec.tools for w in write_calls) and "publish" not in " ".join(
        write_calls
    )
    checks["tools_within_permission"] = set(tools_called) <= set(spec.tools)
    text = json.dumps(out)
    checks["no_hype_claims"] = not HYPE.search(text)
    if exp.get("evidence_sources_subset_of_tools"):
        srcs = {e["source"] for e in out.get("evidence", []) + out.get("key_findings", [])}
        checks["grounded_evidence"] = srcs <= set(tools_called) | {"calculated"}
    if exp.get("has_limitations_or_confidence"):
        checks["uncertainty_stated"] = bool(out.get("limitations")) or out.get("confidence") in (
            "low",
            "medium",
        )
    if exp.get("mentions_sample_size"):
        checks["sample_size"] = isinstance(out.get("sample_size"), int)
    if exp.get("three_distinct_hooks"):
        checks["three_distinct_hooks"] = all(len(set(o["hook_options"])) == 3 for o in out.get("options", []))
    if "max_hashtags" in exp:
        checks["hashtag_limit"] = all(
            len(o["hashtags"]) <= exp["max_hashtags"] for o in out.get("options", [])
        )
    if exp.get("no_performance_claims_in_hashtags"):
        checks["no_hashtag_claims"] = (
            "reach" not in " ".join(o["caption"] for o in out.get("options", [])).lower()
        )
    if exp.get("discloses_no_live_research"):
        checks["research_disclosure"] = out.get("live_research_performed") is False and bool(
            out.get("disclosure")
        )
    if exp.get("reports_unavailable"):
        checks["unavailable_handled"] = out.get("available") is False and out.get("common_questions") == []
    if exp.get("has_caveats"):
        checks["caveats"] = bool(out.get("caveats"))
    if exp.get("no_universal_best_time_claim"):
        checks["no_universal_time"] = "not a proven best time" in text or "not a universal" in text
    if exp.get("labels_evidence_level"):
        checks["evidence_levels"] = all(i.get("evidence_level") for i in out.get("insights", []))
    return checks


def main() -> int:
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_agents(db)
        seed_demo(db)
        db.commit()
    orch = Orchestrator(SessionLocal, get_settings())
    cases = json.loads((Path(__file__).parent / "dataset.json").read_text())
    failed = 0
    for case in cases:
        with SessionLocal() as db:
            run = orch.create_run(db, case["agent"], case["input"])
            db.commit()
            rid = run.id
        orch.submit(rid, wait=True)
        with SessionLocal() as db:
            run = db.get(AgentRun, rid)
            audits = db.scalars(select(ToolCallAudit).where(ToolCallAudit.run_id == rid)).all()
            tools = [a.tool for a in audits]
            writes = [a.tool for a in audits if a.is_write]
            if run.status != "succeeded":
                print(f"FAIL {case['id']}: run {run.status}: {run.error}")
                failed += 1
                continue
            checks = grade(case, run, tools, writes)
        bad = [k for k, v in checks.items() if not v]
        failed += bool(bad)
        print(
            f"{'PASS' if not bad else 'FAIL'} {case['id']:<24} {sum(checks.values())}/{len(checks)}"
            + (f"  failed: {bad}" if bad else "")
        )
    print(f"\n{len(cases) - failed}/{len(cases)} cases passed (mode={get_settings().agent_mode})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
