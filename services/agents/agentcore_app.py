"""Amazon Bedrock AgentCore Runtime entrypoint (Mode C).

The deployed agent never touches the local SQLite database or Instagram tokens. The local API sends a
read-only context snapshot (results of the agent's read tools) and receives a schema-validated result.
Write actions (drafts, proposals, approvals) still happen locally, after validation.

Local smoke test (no AWS):  python agentcore_app.py  then
  curl -X POST localhost:8080/invocations -d '{"agent_id":"analytics","input":{},"context":{}}'
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# The shared agent definitions live in services/api/app. The build script copies them next to this file.
for p in (Path(__file__).parent, Path(__file__).parent.parent / "api"):
    sys.path.insert(0, str(p))

from bedrock_agentcore.runtime import BedrockAgentCoreApp  # noqa: E402

from app.agents.registry import AGENTS, jsonable, system_prompt  # noqa: E402

app = BedrockAgentCoreApp()
MODEL_ID = os.environ.get("BEDROCK_MODEL_ID")


@app.entrypoint
def invoke(payload: dict) -> dict:
    agent_id = payload.get("agent_id")
    if agent_id not in AGENTS:
        return {"error": f"unknown agent {agent_id}"}
    if not MODEL_ID:
        return {"error": "BEDROCK_MODEL_ID not set on the runtime"}
    from strands import Agent
    from strands.models.bedrock import BedrockModel

    spec = AGENTS[agent_id]
    agent = Agent(model=BedrockModel(model_id=MODEL_ID, max_tokens=2000), system_prompt=system_prompt(spec),
                  callback_handler=None)
    prompt = (f"Task input: {json.dumps(jsonable(payload.get('input', {})))}\n"
              f"Read-only data gathered by the app's tools (cite these tool names as sources):\n"
              f"{json.dumps(jsonable(payload.get('context', {})))[:60000]}")
    res = agent(prompt, structured_output_model=spec.output)
    usage = getattr(res.metrics, "accumulated_usage", {}) or {}
    return {"output": res.structured_output.model_dump(), "input_tokens": usage.get("inputTokens"),
            "output_tokens": usage.get("outputTokens")}


if __name__ == "__main__":
    app.run()
