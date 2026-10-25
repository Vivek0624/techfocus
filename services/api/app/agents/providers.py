"""Execution providers.
mock      deterministic, data-grounded, no credentials
bedrock   Strands Agents + Amazon Bedrock, running in this process with your local AWS credentials
openai    Strands Agents + the OpenAI API (OPENAI_API_KEY)
anthropic Strands Agents + the Claude API (ANTHROPIC_API_KEY)
ollama    Strands Agents + a free local model via Ollama (nothing leaves this Mac)
agentcore invokes an agent deployed to Amazon Bedrock AgentCore Runtime (a remote service)"""

from __future__ import annotations

import functools
import inspect
import json
import logging
import typing
import uuid
from dataclasses import dataclass
from typing import Any, Protocol

from ..config import Settings
from .registry import AgentSpec, jsonable, system_prompt
from .tools import TOOLS, ToolContext, ToolError, call_tool

log = logging.getLogger(__name__)

# Rough per-1k-token prices (USD) for cost estimates; override in settings UI later. Estimates only.
PRICE_PER_1K = {"input": 0.003, "output": 0.015}


@dataclass
class ProviderResult:
    output: dict
    input_tokens: int | None = None
    output_tokens: int | None = None

    @property
    def est_cost(self) -> float | None:
        if self.input_tokens is None or self.output_tokens is None:
            return None
        return round(
            self.input_tokens / 1000 * PRICE_PER_1K["input"]
            + self.output_tokens / 1000 * PRICE_PER_1K["output"],
            5,
        )


class Provider(Protocol):
    mode: str

    def run(self, spec: AgentSpec, ctx: ToolContext, inp: dict, handle: dict) -> ProviderResult: ...


class MockProvider:
    mode = "mock"

    def run(self, spec: AgentSpec, ctx: ToolContext, inp: dict, handle: dict) -> ProviderResult:
        if inp.get("simulate_failure"):
            raise RuntimeError("simulated failure (demo error-state test)")
        out = spec.mock(ctx, inp)
        spec.output.model_validate(out)  # schema check even in mock mode
        return ProviderResult(output=jsonable(out))


def _strands_tool(ctx: ToolContext, name: str, budget: dict):
    """Wrap one of our tools as a Strands tool bound to this run's context."""
    from strands import tool

    spec = TOOLS[name]
    sig = inspect.signature(spec.fn)
    params = [p for p in sig.parameters.values() if p.name != "ctx"]
    hints = typing.get_type_hints(spec.fn)

    @functools.wraps(spec.fn)
    def wrapper(**kwargs: Any) -> str:
        budget["tool_calls"] += 1
        if budget["tool_calls"] > budget["max_tool_calls"]:
            return json.dumps({"error": "tool-call budget exhausted; answer with what you have"})
        try:
            return json.dumps(jsonable(call_tool(ctx, name, **kwargs)))
        except ToolError as e:
            return json.dumps({"error": str(e)})

    wrapper.__signature__ = sig.replace(parameters=params)  # type: ignore[attr-defined]
    wrapper.__annotations__ = {k: v for k, v in hints.items() if k != "ctx"} | {"return": str}
    wrapper.__doc__ = spec.description + "\n\nArgs:\n" + "".join(f"    {p.name}: {p.name}\n" for p in params)
    return tool(name=name, description=spec.description)(wrapper)


MODEL_MODES = ("bedrock", "openai", "anthropic", "ollama")


def model_config_error(s: Settings) -> str | None:
    """Why the configured model mode can't run, or None if it can."""
    if s.agent_mode == "bedrock" and not s.bedrock_model_id:
        return "BEDROCK_MODEL_ID is not set. Pick a model enabled in your account/region."
    if s.agent_mode == "openai" and not (s.openai_api_key and s.openai_model_id):
        return "OPENAI_API_KEY and OPENAI_MODEL_ID must both be set in .env."
    if s.agent_mode == "anthropic" and not s.anthropic_api_key:
        return "ANTHROPIC_API_KEY is not set in .env."
    return None


def make_model(s: Settings):
    """The Strands model for the configured mode (bedrock | openai | anthropic)."""
    if s.agent_mode == "ollama":
        from strands.models.ollama import OllamaModel

        return OllamaModel(s.ollama_host, model_id=s.ollama_model_id, max_tokens=s.model_max_tokens)
    if s.agent_mode == "openai":
        from strands.models.openai import OpenAIModel

        return OpenAIModel(
            client_args={
                "api_key": s.openai_api_key.get_secret_value() if s.openai_api_key else None,
                "base_url": s.openai_base_url or None,
                "timeout": s.agent_timeout_seconds,
                "max_retries": 0,
            },
            model_id=s.openai_model_id or "",
            params={"max_completion_tokens": s.model_max_tokens},
        )
    if s.agent_mode == "anthropic":
        from strands.models.anthropic import AnthropicModel

        return AnthropicModel(
            client_args={
                "api_key": s.anthropic_api_key.get_secret_value() if s.anthropic_api_key else None,
                "timeout": s.agent_timeout_seconds,
                "max_retries": 0,
            },
            model_id=s.anthropic_model_id,
            max_tokens=s.model_max_tokens,
        )
    import boto3
    from botocore.config import Config
    from strands.models.bedrock import BedrockModel

    return BedrockModel(
        boto_session=boto3.Session(profile_name=s.aws_profile, region_name=s.aws_region),
        model_id=s.bedrock_model_id or "",
        max_tokens=s.bedrock_max_tokens,
        boto_client_config=Config(read_timeout=s.agent_timeout_seconds, retries={"max_attempts": 2}),
    )


class ModelProvider:
    """Strands agent loop on whichever model API is configured (Bedrock, OpenAI or Claude API)."""

    def __init__(self, s: Settings):
        err = model_config_error(s)
        if err:
            raise RuntimeError(err)
        self.s = s
        self.mode: str = s.agent_mode

    def run(self, spec: AgentSpec, ctx: ToolContext, inp: dict, handle: dict) -> ProviderResult:
        from strands import Agent, ModelRetryStrategy

        model = make_model(self.s)
        budget = {"tool_calls": 0, "max_tool_calls": self.s.agent_max_model_calls * 2}
        agent = Agent(
            model=model,
            retry_strategy=ModelRetryStrategy(max_attempts=3, initial_delay=2),
            system_prompt=system_prompt(spec),
            callback_handler=None,
            tools=[_strands_tool(ctx, t, budget) for t in spec.tools],
            name=spec.id,
        )
        handle["cancel"] = agent.cancel
        prompt = (
            f"Task input (JSON): {json.dumps(jsonable(inp))}\n"
            "Use the tools to gather evidence first, then return the structured output."
        )
        res = agent(prompt, structured_output_model=spec.output)
        out = res.structured_output
        if out is None:
            raise RuntimeError("model returned no structured output")
        usage = getattr(res.metrics, "accumulated_usage", {}) or {}
        return ProviderResult(
            output=jsonable(out.model_dump()),
            input_tokens=usage.get("inputTokens"),
            output_tokens=usage.get("outputTokens"),
        )


class AgentCoreProvider:
    """Calls a deployed AgentCore Runtime. The deployed entrypoint is services/agents/agentcore_app.py.
    The cloud agent has no access to this local database; the app sends it a read-only context snapshot."""

    mode = "agentcore"

    def __init__(self, s: Settings):
        if not s.agentcore_runtime_arn:
            raise RuntimeError("AGENTCORE_RUNTIME_ARN is not set. Deploy first (docs/aws-setup.md).")
        self.s = s

    def run(self, spec: AgentSpec, ctx: ToolContext, inp: dict, handle: dict) -> ProviderResult:
        import boto3

        snapshot = {}
        for t in spec.tools:
            if not TOOLS[t].is_write:
                try:
                    snapshot[t] = call_tool(ctx, t)
                except (ToolError, TypeError):
                    continue
        session = boto3.Session(profile_name=self.s.aws_profile, region_name=self.s.aws_region)
        client = session.client("bedrock-agentcore")
        resp = client.invoke_agent_runtime(
            agentRuntimeArn=self.s.agentcore_runtime_arn,
            runtimeSessionId=str(uuid.uuid4()) + "-" + uuid.uuid4().hex[:8],
            payload=json.dumps(jsonable({"agent_id": spec.id, "input": inp, "context": snapshot})).encode(),
        )
        body = resp["response"].read() if hasattr(resp.get("response"), "read") else resp.get("response")
        data = json.loads(body)
        out = spec.output.model_validate(data.get("output", data))
        return ProviderResult(
            output=jsonable(out.model_dump()),
            input_tokens=data.get("input_tokens"),
            output_tokens=data.get("output_tokens"),
        )


def make_provider(s: Settings) -> Provider:
    if s.agent_mode in MODEL_MODES:
        return ModelProvider(s)
    if s.agent_mode == "agentcore":
        return AgentCoreProvider(s)
    return MockProvider()
