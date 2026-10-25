"use client";
import * as React from "react";
import { api } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";

const MODES = [
  { id: "mock", title: "mock", body: "Deterministic local templates. No AWS calls, no cost. Good for trying the app and for tests." },
  { id: "bedrock", title: "bedrock (local Strands)", body: "Agents run on this machine with Strands Agents, calling Amazon Bedrock models using your local AWS credentials." },
  { id: "agentcore", title: "agentcore (remote)", body: "Agents run in Amazon Bedrock AgentCore Runtime; this app invokes the deployed runtime ARN and reads results back." },
];

export function AwsPage() {
  const s = useApi(() => api.awsStatus(), []);
  const d = s.data;
  return (
    <div>
      <PageHeader title="AWS Agent Platform" description="Where the AI agents run. Switch modes with AGENT_MODE in the backend .env and restart the API." />
      {s.loading && !d && <Loading />}
      {s.error && <ErrorState message={s.error} onRetry={s.reload} />}
      {d && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader title="Current configuration" description={`Checked ${fmtDateTime(d.checked_at)}`} actions={<Badge tone="blue">{d.agent_mode}</Badge>} />
            <CardBody>
              <dl className="grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-muted">Mode</dt><dd>{d.agent_mode}</dd></div>
                <div><dt className="text-xs text-muted">Region</dt><dd>{d.region ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted">Profile</dt><dd>{d.profile ?? "default"}</dd></div>
                <div><dt className="text-xs text-muted">Model ID</dt><dd className="break-all">{d.bedrock_model_id ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted">Credentials</dt><dd><Badge tone={d.credentials === "found" ? "green" : "amber"}>{d.credentials}</Badge></dd></div>
                <div><dt className="text-xs text-muted">AgentCore runtime ARN</dt><dd>{d.agentcore_runtime_arn_set ? "set" : "not set"}</dd></div>
              </dl>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Services" />
            <Table>
              <thead><tr><Th>Service</Th><Th>Phase</Th><Th>Needed now</Th></tr></thead>
              <tbody>
                {d.services.map((x) => (
                  <tr key={x.name}><Td>{x.name}</Td><Td className="text-muted">{x.phase}</Td><Td><Badge tone={x.needed ? "blue" : "neutral"}>{x.needed ? "yes" : "no"}</Badge></Td></tr>
                ))}
              </tbody>
            </Table>
          </Card>
        </div>
      )}
      <Card className="mt-6">
        <CardHeader title="Modes" description="Set AGENT_MODE=mock | bedrock | agentcore in .env. The frontend never holds AWS credentials." />
        <CardBody className="grid gap-4 md:grid-cols-3">
          {MODES.map((m) => (
            <div key={m.id} className={`rounded-md border p-3 ${d?.agent_mode === m.id ? "border-accent" : "border-line"}`}>
              <p className="font-medium">{m.title}</p>
              <p className="mt-1 text-sm text-muted">{m.body}</p>
            </div>
          ))}
        </CardBody>
      </Card>
    </div>
  );
}
