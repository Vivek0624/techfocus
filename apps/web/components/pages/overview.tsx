"use client";
import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { CheckCircle2, Circle, Plus } from "lucide-react";
import { api, errorMessage, type Dashboard, type DateFilter as DF, type Post, type TargetProgress, type Task } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDateTime, fmtNum, fmtSlot, humanize } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { Metric, NumOrNA, SourceBadge } from "@/components/metric";
import { DateFilter } from "@/components/date-filter";
import { PageHeader } from "@/components/page-header";
import { useDataChanged } from "@/components/shell";

export function OverviewPage() {
  const [filter, setFilter] = React.useState<DF>({ days: 30 });
  const dash = useApi(() => api.dashboard(filter), [filter.days, filter.start, filter.end]);
  useDataChanged(dash.reload);

  return (
    <div>
      <PageHeader title="Overview" description="Where the account stands and what to do next." actions={<DateFilter value={filter} onChange={setFilter} />} />
      {dash.loading && !dash.data && <Loading label="Loading dashboard…" />}
      {dash.error && <ErrorState message={dash.error} onRetry={dash.reload} />}
      {dash.data && <DashboardBody d={dash.data} />}
      <div className="mt-6">
        <DailyActionCenter />
      </div>
    </div>
  );
}

function DashboardBody({ d }: { d: Dashboard }) {
  const m = d.metrics;
  const src = d.metric_sources ?? {};
  const followerSrc = src["followers"] ?? d.account.source;
  const insightSrc = src["reach/views/interactions"] ?? m.sources?.[0];
  const calc = "calculated";
  const r = m.last_refresh;
  const hasAnyData = m.followers_end !== null || m.reach !== null || (d.recent_posts?.length ?? 0) > 0;

  return (
    <div className="flex flex-col gap-6">
      {!d.target?.configured && (
        <Card className="border-accent/40">
          <CardBody className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="font-medium">Set your growth target</p>
              <p className="text-sm text-muted">Tell the app where you want to be and by when, so it can track pace and plan your days.</p>
            </div>
            <Link href="/settings#target" className="rounded-md bg-accent px-3 py-2 text-sm font-medium text-white">
              Set target
            </Link>
          </CardBody>
        </Card>
      )}

      {!hasAnyData && (
        <Card>
          <EmptyState title="No data yet">
            <p>
              Connect Instagram on the <Link className="text-accent underline" href="/instagram">Instagram page</Link> or add a manual snapshot.
            </p>
          </EmptyState>
        </Card>
      )}

      <Card>
        <CardHeader
          title={d.account.username ?? "Account"}
          description={`${d.range.start} → ${d.range.end}${d.account.account_type ? ` · ${d.account.account_type}` : ""}`}
          actions={<SourceBadge source={d.account.source} />}
        />
        <CardBody className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <Metric label="Followers" value={d.account.followers ?? m.followers_end} source={followerSrc} refreshed={d.account.last_refresh} />
          <Metric label="Net growth" value={m.net_follower_growth} source={followerSrc} refreshed={r} />
          <Metric label="Gained" value={m.followers_gained} source={followerSrc} refreshed={r} />
          <Metric label="Lost" value={m.followers_lost} source={followerSrc} refreshed={r} />
          <Metric label="Reach" value={m.reach} source={insightSrc} refreshed={r} />
          <Metric label="Views" value={m.views} source={insightSrc} refreshed={r} />
          <Metric label="Accounts engaged" value={m.accounts_engaged} source={insightSrc} refreshed={r} />
          <Metric label="Likes" value={m.likes} source={insightSrc} refreshed={r} />
          <Metric label="Comments" value={m.comments} source={insightSrc} refreshed={r} />
          <Metric label="Shares" value={m.shares} source={insightSrc} refreshed={r} />
          <Metric label="Saves" value={m.saves} source={insightSrc} refreshed={r} />
          <Metric label="Profile link taps" value={m.profile_links_taps} source={insightSrc} refreshed={r} />
          <Metric label="Follows / 1k reach" value={m.follows_per_1k_reach} digits={2} source={src["follows_per_1k_reach"] ?? calc} refreshed={r} />
          <Metric label="Posts published" value={d.posts_published} source={calc} refreshed={r} />
          <Metric label="Engagement rate (reach)" value={d.engagement_rate_by_reach} digits={2} suffix="%" source={src["engagement_rate_by_reach"] ?? calc} refreshed={r} />
        </CardBody>
        {d.limitations?.length > 0 && (
          <ul className="border-t border-line px-4 py-3 text-xs text-muted">
            {d.limitations.map((l) => (
              <li key={l}>• {l}</li>
            ))}
          </ul>
        )}
      </Card>

      {d.target?.configured && <TargetProgressCard t={d.target} />}

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Best reels" description="Outlier multiple = views ÷ median views of your other posts" />
          <PostList posts={d.best_reels} showMultiple />
        </Card>
        <Card>
          <CardHeader title="Recent posts" />
          <PostList posts={d.recent_posts} />
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card>
          <CardHeader title="Top recommended action" />
          <CardBody>
            {d.top_action ? (
              <div>
                <p className="font-medium">{d.top_action.title}</p>
                {d.top_action.reason && <p className="mt-1 text-sm text-muted">{d.top_action.reason}</p>}
              </div>
            ) : (
              <p className="text-sm text-muted">No recommendation yet. Run the Growth Strategist agent.</p>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Upcoming posts" actions={<Link className="text-xs text-accent" href="/calendar">Calendar →</Link>} />
          <CardBody className="flex flex-col gap-2">
            {d.upcoming?.length ? (
              d.upcoming.map((u) => (
                <div key={u.id} className="flex items-start justify-between gap-2 text-sm">
                  <div>
                    <div>{u.title}</div>
                    <div className="text-xs text-muted">{fmtSlot(u.scheduled_at)}</div>
                  </div>
                  <StatusBadge status={u.approval_status} />
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">Nothing scheduled.</p>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Recent agent runs" actions={<Link className="text-xs text-accent" href="/agents">Agents →</Link>} />
          <CardBody className="flex flex-col gap-2">
            {d.recent_agent_runs?.length ? (
              d.recent_agent_runs.slice(0, 6).map((run) => (
                <div key={run.id} className="flex items-start justify-between gap-2 text-sm">
                  <div className="min-w-0">
                    <div>{humanize(run.agent_id)}</div>
                    <div className="truncate text-xs text-muted">{run.output_summary ?? run.error ?? "—"}</div>
                  </div>
                  <StatusBadge status={run.status} />
                </div>
              ))
            ) : (
              <p className="text-sm text-muted">No runs yet.</p>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

export function TargetProgressCard({ t }: { t: TargetProgress }) {
  const start = t.start_followers ?? 0;
  const target = t.target ?? 0;
  const current = t.current ?? null;
  const pct = current !== null && target > start ? Math.max(0, Math.min(100, ((current - start) / (target - start)) * 100)) : 0;
  return (
    <Card>
      <CardHeader
        title="Target progress"
        description={`${t.start_date ?? "?"} → ${t.end_date ?? "?"} · day ${t.days_elapsed ?? "?"} of ${t.days_total ?? "?"}`}
        actions={t.on_pace === null || t.on_pace === undefined ? null : <Badge tone={t.on_pace ? "green" : "red"}>{t.on_pace ? "On pace" : "Behind pace"}</Badge>}
      />
      <CardBody className="flex flex-col gap-4">
        <div>
          <div className="mb-1 flex justify-between text-sm">
            <span>
              <NumOrNA value={current} /> / {fmtNum(target)} followers
            </span>
            <span className="text-muted">{pct.toFixed(1)}%</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded bg-line" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
            <div className="h-full bg-accent" style={{ width: `${pct}%` }} />
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
          <Stat label="Remaining" value={<NumOrNA value={t.remaining} />} />
          <Stat label="Days remaining" value={<NumOrNA value={t.days_remaining} />} />
          <Stat label="Required / day" value={<NumOrNA value={t.required_per_day} digits={1} />} />
          <Stat label="Actual / day" value={<NumOrNA value={t.actual_per_day} digits={1} />} />
        </div>
        {t.scenarios && t.scenarios.length > 0 && (
          <div>
            <p className="mb-2 text-xs font-medium text-amber-700 dark:text-amber-300">Scenarios — illustration, not prediction</p>
            <Table>
              <thead>
                <tr>
                  <Th>Daily net growth</Th>
                  <Th>Projected followers at end</Th>
                </tr>
              </thead>
              <tbody>
                {t.scenarios.map((s) => (
                  <tr key={s.daily_net}>
                    <Td>{fmtNum(s.daily_net, 1)}</Td>
                    <Td>{fmtNum(s.projected_followers)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {t.scenario_note && <p className="mt-2 text-xs text-muted">{t.scenario_note}</p>}
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-md border border-line bg-bg/40 p-2.5">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-0.5 font-semibold tabular-nums">{value}</div>
    </div>
  );
}

function PostList({ posts, showMultiple }: { posts: Post[]; showMultiple?: boolean }) {
  if (!posts?.length) return <EmptyState title="No posts in this range" />;
  return (
    <Table>
      <thead>
        <tr>
          <Th>Post</Th>
          <Th className="text-right">Views</Th>
          <Th className="text-right">Reach</Th>
          {showMultiple && <Th className="text-right">Multiple</Th>}
          <Th>Source</Th>
        </tr>
      </thead>
      <tbody>
        {posts.map((p) => (
          <tr key={p.id}>
            <Td className="max-w-xs">
              <div className="truncate">{p.permalink ? <a className="hover:underline" href={p.permalink} target="_blank" rel="noreferrer">{p.caption ?? "(no caption)"}</a> : p.caption ?? "(no caption)"}</div>
              <div className="text-xs text-muted">{fmtDateTime(p.published_at)} · {humanize(p.pillar)}</div>
            </Td>
            <Td className="text-right tabular-nums"><NumOrNA value={p.views} /></Td>
            <Td className="text-right tabular-nums"><NumOrNA value={p.reach} /></Td>
            {showMultiple && (
              <Td className="text-right tabular-nums">
                {p.multiple === null ? <NumOrNA value={null} /> : <Badge tone={p.multiple >= 2 ? "violet" : "neutral"}>{fmtNum(p.multiple, 2)}×</Badge>}
              </Td>
            )}
            <Td><SourceBadge source={p.source} /></Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}

function DailyActionCenter() {
  const plan = useApi(() => api.dailyPlan(), []);
  useDataChanged(plan.reload);
  const [title, setTitle] = React.useState("");
  const [busy, setBusy] = React.useState(false);

  const toggle = async (t: Task) => {
    const next = !t.done;
    plan.setData((plan.data ?? []).map((x) => (x.id === t.id ? { ...x, done: next } : x)));
    try {
      await api.setTaskDone(t.id, next);
    } catch (e) {
      toast.error(errorMessage(e));
      plan.reload();
    }
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await api.addTask({ title: title.trim() });
      setTitle("");
      toast.success("Task added");
      plan.reload();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const tasks = plan.data ?? [];
  const done = tasks.filter((t) => t.done).length;
  return (
    <Card>
      <CardHeader title="Daily action center" description={tasks.length ? `${done} of ${tasks.length} done today` : "Today's checklist"} />
      {plan.loading && !plan.data && <Loading />}
      {plan.error && <ErrorState message={plan.error} onRetry={plan.reload} />}
      {plan.data && tasks.length === 0 && <EmptyState title="No tasks for today" />}
      {tasks.length > 0 && (
        <ul className="divide-y divide-line/60">
          {tasks.map((t) => (
            <li key={t.id} className="flex items-start gap-3 px-4 py-2.5">
              <button type="button" onClick={() => toggle(t)} aria-label={t.done ? `Mark "${t.title}" not done` : `Mark "${t.title}" done`} aria-pressed={t.done} className="mt-0.5 text-muted hover:text-fg">
                {t.done ? <CheckCircle2 className="size-5 text-emerald-400" /> : <Circle className="size-5" />}
              </button>
              <div className="min-w-0 flex-1">
                <div className={t.done ? "text-muted line-through" : ""}>{t.title}</div>
                <div className="text-xs text-muted">
                  {t.reason ?? ""} · impact {t.impact} · {t.effort_minutes} min
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={add} className="flex gap-2 border-t border-line p-3">
        <Input placeholder="Add a task for today" value={title} onChange={(e) => setTitle(e.target.value)} aria-label="New task" />
        <Button type="submit" disabled={busy || !title.trim()}>
          <Plus /> Add
        </Button>
      </form>
    </Card>
  );
}
