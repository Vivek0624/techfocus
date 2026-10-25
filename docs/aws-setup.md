# AWS setup

Nothing in this repo creates AWS resources automatically. Mock mode needs no AWS at all.

## Which services, when
| phase | services | why |
| --- | --- | --- |
| A mock | none | |
| B local Bedrock | Bedrock Runtime (+ Strands Agents library, runs on your Mac) | model-written plans and scripts |
| publishing via API | S3 (public `reels/` prefix) | Meta must fetch videos from a public URL |
| C cloud agents | AgentCore Runtime, CloudWatch / AgentCore Observability | run agents remotely |
| optional | AgentCore Memory, AgentCore Evaluations, EventBridge Scheduler + Lambda | cross-session context, quality scoring, weekly cloud review |
| not used yet | Step Functions, Lambda tool endpoints, AgentCore Gateway, Knowledge Bases, Secrets Manager | no workflow needs them locally; Secrets Manager becomes required when the API is deployed |

## Mode B: local Bedrock
1. `aws configure sso` (or `aws configure`) to create a profile. No keys go in `.env`.
2. Bedrock console → pick a region (e.g. `us-east-1` or `ap-south-1`) → Model catalog → enable/request access
   to a model. Note its **model ID or inference profile ID** (Claude models usually need the inference profile,
   e.g. a `us.` or `apac.`-prefixed id).
3. Attach `infra/aws/iam-local-bedrock-policy.json` (replace placeholders) to the profile's user/role.
4. `.env`: `AGENT_MODE=bedrock`, `AWS_PROFILE=…`, `AWS_REGION=…`, `BEDROCK_MODEL_ID=…`. Restart.
5. AWS Agent Platform page → credentials "found". Run any agent; failures show the reason (e.g. AccessDenied →
   model not enabled).
Cost: per-token Bedrock pricing. A Reel package is typically a few thousand tokens. Runs show token counts and
a rough cost estimate (edit `PRICE_PER_1K` in `providers.py` for your model).

## Mode C: AgentCore Runtime
Uses the npm-based AgentCore CLI (`npm install -g @aws/agentcore`; Node 20+, uv). Checked 2026-10-22; the CLI is
evolving, so confirm flags with `agentcore --help`.
```bash
make build-agentcore                 # assembles services/agents/dist (entrypoint + shared agent code)
cd services/agents/dist
agentcore create --name vtf_agents --framework Strands --model-provider Bedrock --memory none --build CodeZip
# replace the generated entrypoint with agentcore_app.py / point the project at it, set env BEDROCK_MODEL_ID
agentcore dev                        # local server; POST {"agent_id":"analytics","input":{},"context":{}}
agentcore deploy                     # creates billable resources
agentcore invoke '{"agent_id":"analytics","input":{},"context":{}}'
```
Then `.env`: `AGENT_MODE=agentcore`, `AGENTCORE_RUNTIME_ARN=…`, and attach `iam-agentcore-invoke-policy.json`.
The cloud agent receives a read-only snapshot; it has no database, token or Instagram access.
Older tutorials use `agentcore configure` / `agentcore launch` from the deprecated Python starter toolkit; don't install both.

## Optional cloud scheduling
`infra/aws/cloudformation/scheduled-weekly-review.yaml` (EventBridge Scheduler → Lambda → runtime, Mondays 09:00 IST).
Locally, set `ENABLE_LOCAL_SCHEDULER=true` instead: it creates "post now" reminders for calendar items. It never publishes.

## Teardown
`aws cloudformation delete-stack --stack-name <name>` for each stack; empty S3 buckets first; remove the
AgentCore runtime (`agentcore remove …` then `agentcore deploy`, or the console). Check Cost Explorer after.
