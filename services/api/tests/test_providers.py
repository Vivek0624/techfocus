import json

import pytest

from app.agents.providers import AgentCoreProvider, ModelProvider, _strands_tool
from app.agents.tools import ToolContext
from app.config import Settings
from app.db import SessionLocal


def test_strands_tool_wrapping_runs_our_tool_with_audit_and_budget():
    with SessionLocal() as db:
        ctx = ToolContext(db=db, run_id=None, allowed={"get_follower_history"}, demo=True)
        budget = {"tool_calls": 0, "max_tool_calls": 1}
        t = _strands_tool(ctx, "get_follower_history", budget)
        assert t.tool_name == "get_follower_history"
        props = t.tool_spec["inputSchema"]["json"]["properties"]
        assert "days" in props and "ctx" not in props
        out = json.loads(t(days=7))
        assert isinstance(out, list)
        assert "budget" in json.loads(t(days=7))["error"]
        db.rollback()


def test_bedrock_requires_model_id():
    with pytest.raises(RuntimeError, match="BEDROCK_MODEL_ID"):
        ModelProvider(Settings(agent_mode="bedrock", bedrock_model_id=None))


def test_agentcore_requires_arn():
    with pytest.raises(RuntimeError, match="AGENTCORE_RUNTIME_ARN"):
        AgentCoreProvider(Settings(agent_mode="agentcore", agentcore_runtime_arn=None))


def test_openai_and_anthropic_modes_need_keys():
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        ModelProvider(Settings(agent_mode="openai", openai_api_key=None, openai_model_id=None))
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        ModelProvider(Settings(agent_mode="anthropic", anthropic_api_key=None))
    p = ModelProvider(Settings(agent_mode="openai", openai_api_key="sk-test", openai_model_id="gpt-test"))
    assert p.mode == "openai"


def test_ollama_mode_needs_no_key():
    assert ModelProvider(Settings(agent_mode="ollama")).mode == "ollama"
