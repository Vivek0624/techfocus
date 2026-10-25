"use client";
import * as React from "react";
import { toast } from "sonner";
import { Eye, Loader2, Play, RotateCcw, Square } from "lucide-react";
import { api, errorMessage, isTerminal, type Agent, type AgentRun } from "@/lib/api";
import { useApi, useRunPoller } from "@/lib/hooks";
import { fmtDateTime } from "@/lib/utils";
import { Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Textarea } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { JsonView, PageHeader } from "@/components/page-header";
import { useDataChanged } from "@/components/shell";

export function fmtDuration(ms: number | null | undefined) {
  if (ms === null || ms === undefined) return "—";
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export function RunStatusLine({ status, run }: { status: string | null; run: AgentRun }) {
  const live = status && !isTerminal(status);
  return (
    <span className="inline-flex items-center gap-2" data-testid="run-status">
      {live && <Loader2 className="size-3.5 animate-spin text-muted" />}
      <StatusBadge status={status} />
      <span className="text-xs text-muted">
        run #{run.id} · {run.mode}
        {run.duration_ms !== null ? ` · ${fmtDuration(run.duration_ms)}` : ""}
      </span>
    </span>
  );
}

export function RunDetails({ run, status }: { run: AgentRun; status?: string | null }) {
  return (
    <div className="flex flex-col gap-4 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <RunStatusLine status={status ?? run.status} run={run} />
        {run.is_demo && <Badge tone="amber">DEMO</Badge>}
      </div>
      {run.error && (
        <div role="alert" className="rounded-md border border-red-500/30 bg-red-500/10 p-3 text-red-700 dark:text-red-200">
          <p className="font-medium">Error</p>
          <p className="mt-1 whitespace-pre-wrap">{run.error}</p>
        </div>
      )}
      {run.output_summary && (
        <div>
          <p className="text-xs font-medium text-muted">Summary</p>
          <p>{run.output_summary}</p>
        </div>
      )}
      <dl className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Info k="Started" v={fmtDateTime(run.started_at)} />
        <Info k="Finished" v={fmtDateTime(run.finished_at)} />
        <Info k="Tokens (in/out)" v={run.input_tokens === null && run.output_tokens === null ? "n/a" : `${run.input_tokens ?? "?"} / ${run.output_tokens ?? "?"}`} />
        <Info k="Est. cost" v={run.est_cost_usd === null ? "n/a" : `$${run.est_cost_usd.toFixed(4)}`} />
      </dl>
      <div>
        <p className="mb-1 text-xs font-medium text-muted">Tools called</p>
        {run.tools_called?.length ? (
          <div className="flex flex-wrap gap-1">
            {run.tools_called.map((t, i) => (
              <Badge key={i}>{t}</Badge>
            ))}
          </div>
        ) : (
          <span className="text-muted">none</span>
        )}
      </div>
      <div>
        <p className="mb-1 text-xs font-medium text-muted">Input</p>
        <JsonView value={run.input} />
      </div>
      <div>
        <p className="mb-1 text-xs font-medium text-muted">Output</p>
        <JsonView value={run.output} />
      </div>
    </div>
  );
}

function Info({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{k}</dt>
      <dd>{v}</dd>
    </div>
  );
}

export function parseRunInput(text: string, simulateFailure: boolean): { input?: Record<string, unknown>; error?: string } {
  let input: Record<string, unknown> = {};
  if (text.trim()) {
    try {
      const v = JSON.parse(text);
      if (!v || typeof v !== "object" || Array.isArray(v)) return { error: "Input must be a JSON object" };
      input = v;
    } catch {
      return { error: "Input is not valid JSON" };
    }
  }
  if (simulateFailure) input = { ...input, simulate_failure: true };
  return { input };
}

export function AgentsPage() {
  const agents = useApi(() => api.agents(), []);
  const [page, setPage] = React.useState(1);
  const runs = useApi(() => api.agentRuns({ page, page_size: 15 }), [page]);
  useDataChanged(() => {
    agents.reload();
    runs.reload();
  });

  const [runFor, setRunFor] = React.useState<Agent | null>(null);
  const [viewing, setViewing] = React.useState<AgentRun | null>(null);
  const [liveOpen, setLiveOpen] = React.useState(false);

  const poller = useRunPoller((r) => {
    if (r.status === "failed") toast.error(`Run #${r.id} failed: ${r.error ?? "unknown error"}`);
    else if (r.status === "succeeded") toast.success(`Run #${r.id} succeeded`);
    else if (r.status === "cancelled") toast(`Run #${r.id} cancelled`);
    agents.reload();
    runs.reload();
  });

  const startRun = async (agent: Agent, input: Record<string, unknown>) => {
    const r = await poller.start(agent.id, input);
    if (r) {
      setRunFor(null);
      setLiveOpen(true);
      runs.reload();
    }
  };

  const openRun = (r: AgentRun) => {
    if (!isTerminal(r.status)) {
      poller.track(r);
      setLiveOpen(true);
    } else setViewing(r);
  };

  const pages = runs.data ? Math.max(1, Math.ceil(runs.data.total / runs.data.page_size)) : 1;

  return (
    <div>
      <PageHeader title="AI Agents" description="Specialist agents and workflows. Runs are async; status updates live." />
      <Card>
        <CardHeader title="Agents" />
        {agents.loading && !agents.data && <Loading />}
        {agents.error && <ErrorState message={agents.error} onRetry={agents.reload} />}
        {agents.data && agents.data.length === 0 && <EmptyState title="No agents registered" />}
        {agents.data && agents.data.length > 0 && (
          <Table>
            <thead>
              <tr>
                <Th>Agent</Th>
                <Th>Responsibility</Th>
                <Th>Mode</Th>
                <Th>Tools</Th>
                <Th>Write tools</Th>
                <Th>Last run</Th>
                <Th className="text-right">Actions</Th>
              </tr>
            </thead>
            <tbody>
              {agents.data.map((a) => (
                <tr key={a.id}>
                  <Td>
                    <div className="font-medium">{a.name}</div>
                    <Badge tone={a.kind === "workflow" ? "violet" : "neutral"}>{a.kind}</Badge>
                  </Td>
                  <Td className="max-w-xs text-muted">{a.responsibility}</Td>
                  <Td><Badge tone="blue">{a.mode}</Badge></Td>
                  <Td className="max-w-[14rem] text-xs text-muted">{a.tools.join(", ") || "—"}</Td>
                  <Td className="text-xs">{a.write_tools.length ? a.write_tools.join(", ") : <span className="text-muted">none</span>}</Td>
                  <Td>
                    {a.last_run ? (
                      <button type="button" onClick={() => openRun(a.last_run!)} className="flex flex-col items-start gap-0.5">
                        <StatusBadge status={a.last_run.status} />
                        <span className="text-xs text-muted">{fmtDuration(a.last_run.duration_ms)}</span>
                      </button>
                    ) : (
                      <span className="text-xs text-muted">never</span>
                    )}
                  </Td>
                  <Td className="text-right">
                    <Button size="sm" onClick={() => setRunFor(a)} aria-label={`Run ${a.name}`}>
                      <Play /> Run
                    </Button>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <Card className="mt-6">
        <CardHeader title="Run history" />
        {runs.loading && !runs.data && <Loading />}
        {runs.error && <ErrorState message={runs.error} onRetry={runs.reload} />}
        {runs.data && runs.data.items.length === 0 && <EmptyState title="No runs yet" />}
        {runs.data && runs.data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>
                  <Th>#</Th>
                  <Th>Agent</Th>
                  <Th>Status</Th>
                  <Th>Input</Th>
                  <Th>Summary / error</Th>
                  <Th>Duration</Th>
                  <Th>Created</Th>
                  <Th />
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((r) => (
                  <tr key={r.id}>
                    <Td className="tabular-nums">{r.id}{r.parent_run_id ? <span className="text-xs text-muted"> ↳{r.parent_run_id}</span> : null}</Td>
                    <Td>{r.agent_id}</Td>
                    <Td><StatusBadge status={r.status} /></Td>
                    <Td className="max-w-[12rem] truncate text-xs text-muted">{r.input_summary ?? "—"}</Td>
                    <Td className="max-w-xs truncate text-xs">{r.error ? <span className="text-red-700 dark:text-red-300">{r.error}</span> : r.output_summary ?? "—"}</Td>
                    <Td className="text-xs">{fmtDuration(r.duration_ms)}</Td>
                    <Td className="whitespace-nowrap text-xs">{fmtDateTime(r.created_at)}</Td>
                    <Td>
                      <Button size="sm" variant="ghost" onClick={() => openRun(r)} aria-label={`View run ${r.id}`}>
                        <Eye /> View
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex items-center justify-between p-3 text-sm text-muted">
              <span>{runs.data.total} runs · page {runs.data.page} of {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      {runFor && <RunDialog agent={runFor} onClose={() => setRunFor(null)} onRun={startRun} error={poller.error} />}

      <Dialog open={liveOpen && !!poller.run} onOpenChange={setLiveOpen} title={poller.run ? `Run #${poller.run.id} · ${poller.run.agent_id}` : "Run"} side="right"
        footer={
          poller.run && (
            <>
              {poller.active && poller.status !== "cancelling" && (
                <Button variant="outline" onClick={poller.cancel}><Square /> Cancel</Button>
              )}
              {(poller.run.status === "failed" || poller.run.status === "cancelled") && (
                <Button variant="outline" onClick={poller.retry}><RotateCcw /> Retry</Button>
              )}
              <Button variant="secondary" onClick={() => setLiveOpen(false)}>Close</Button>
            </>
          )
        }
      >
        {poller.error && <ErrorState message={poller.error} />}
        {poller.run && <RunDetails run={poller.run} status={poller.status} />}
      </Dialog>

      <Dialog open={!!viewing} onOpenChange={(o) => !o && setViewing(null)} title={viewing ? `Run #${viewing.id} · ${viewing.agent_id}` : "Run"} side="right"
        footer={
          viewing && (viewing.status === "failed" || viewing.status === "cancelled") ? (
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  const r = await api.retryRun(viewing.id);
                  setViewing(null);
                  poller.track(r);
                  setLiveOpen(true);
                  runs.reload();
                } catch (e) {
                  toast.error(errorMessage(e));
                }
              }}
            >
              <RotateCcw /> Retry
            </Button>
          ) : null
        }
      >
        {viewing && <RunDetails run={viewing} />}
      </Dialog>
    </div>
  );
}

function RunDialog({ agent, onClose, onRun, error }: { agent: Agent; onClose: () => void; onRun: (a: Agent, input: Record<string, unknown>) => Promise<void>; error: string | null }) {
  const [text, setText] = React.useState("");
  const [fail, setFail] = React.useState(false);
  const [localErr, setLocalErr] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);
  const submit = async () => {
    const { input, error: e } = parseRunInput(text, fail);
    if (e) return setLocalErr(e);
    setLocalErr(null);
    setBusy(true);
    await onRun(agent, input!);
    setBusy(false);
  };
  return (
    <Dialog
      open
      onOpenChange={(o) => !o && onClose()}
      title={`Run ${agent.name}`}
      description={agent.responsibility}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>Cancel</Button>
          <Button onClick={submit} disabled={busy}><Play /> {busy ? "Starting…" : "Start run"}</Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field label="Input (optional JSON object)" htmlFor="run-input" error={localErr ?? undefined}>
          <Textarea id="run-input" rows={6} className="font-mono text-xs" placeholder='{"topic": "APIs"}' value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={fail} onChange={(e) => setFail(e.target.checked)} className="size-4 accent-[#5b7cfa]" />
          Simulate failure (adds {"{"}&quot;simulate_failure&quot;: true{"}"})
        </label>
        {error && <ErrorState message={error} />}
      </div>
    </Dialog>
  );
}
