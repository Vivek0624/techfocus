# Agent design

## Agents
| id | responsibility | tools (write tools marked ✎) | output schema |
| --- | --- | --- | --- |
| growth_strategist | bottleneck, next action, daily/weekly priorities | target progress, insights, follower history, top reels, experiment results, content ideas | `GrowthPlan` |
| audience_intelligence | personas → angles, observed vs inferred | top reels, recent media, audience questions | `AudienceReport` |
| content_research | facts + sources; discloses when no live research ran | search library | `ResearchReport` |
| reel_creative | full Reel packages, 3 hooks each | top reels, search library, ✎save_content_draft | `ReelOptions` |
| analytics | outliers, weak patterns, findings with limitations | recent media, top reels, insights, media insights | `AnalyticsReport` |
| scheduling | proposed slots, missing captions/media | content ideas, ✎propose_calendar_change | `ScheduleProposal` |
| community_insights | recurring questions, draft replies (approval required) | audience questions, ✎create_approval_request | `CommunityReport` |
| growth_experiment | propose + read experiments without overclaiming | experiment results, ✎create_growth_experiment, recent media | `ExperimentReport` |

## Orchestrator (`agents/orchestrator.py`)
- Workflows: `daily_plan` = analytics → growth_strategist; `weekly_review` = analytics → growth_experiment →
  growth_strategist; `reel_package` = audience_intelligence → reel_creative. Earlier outputs are passed forward
  as summaries. Depth is 1; no agent can start another agent.
- Bounds: global concurrency semaphore (`AGENT_MAX_CONCURRENCY`), per-run timeout (`AGENT_TIMEOUT_SECONDS`),
  tool-call budget per run (`AGENT_MAX_MODEL_CALLS`×2), Bedrock client retries 2.
- Every output is validated against its Pydantic schema before it is stored; invalid output = failed run.
- Cancel: queued runs are cancelled immediately; running runs get `cancel_requested` (and Strands
  `agent.cancel()` in Bedrock mode). Status changes to `cancelled` only when the worker actually stops.
- Run history: `agent_runs` (+ children via `parent_run_id`), `tool_call_audit` per tool call, tokens and
  estimated cost when the provider reports usage.

## Modes
| mode | where it runs | needs |
| --- | --- | --- |
| `mock` | in-process, deterministic, grounded in DB data | nothing |
| `bedrock` | in-process Strands `Agent` + `BedrockModel`; our tools wrapped as Strands tools | AWS profile + model access + `BEDROCK_MODEL_ID` |
| `agentcore` | remote AgentCore Runtime (`services/agents/agentcore_app.py`); app sends a read-only snapshot of tool results, validates the returned JSON locally | deployed runtime + `AGENTCORE_RUNTIME_ARN` |

AgentCore Runtime was chosen over a managed harness because the orchestration is our own deterministic code:
the runtime only needs to host single specialist invocations. The database stays the source of truth; AgentCore
Memory is optional and never authoritative.

## Evaluations
`make evals` runs `services/api/evals/dataset.json` (9 cases) and grades: schema validity, tools within
permission, approval-rule compliance, evidence grounded in tools actually called, stated uncertainty, research
disclosure, unavailable-data handling, no hype claims. Run with `AGENT_MODE=bedrock` to grade a real model.

## Learning
`learning_records` stores patterns, hooks, experiment outcomes and decisions with `sample_size` and
`confidence`. Weekly review writes a `decision=test_more` record; nothing becomes a "rule" from one post.
