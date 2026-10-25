"use client";
import * as React from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";
import { api, type Analytics, type DateFilter as DF, type GroupStat } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDateTime, fmtNum, humanize } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { NumOrNA, SourceBadge } from "@/components/metric";
import { DateFilter } from "@/components/date-filter";
import { PageHeader } from "@/components/page-header";
import { useDataChanged } from "@/components/shell";

const AXIS = { stroke: "#6b6e76", fontSize: 11 };
const TOOLTIP_STYLE = { background: "#18191c", border: "1px solid #26282d", borderRadius: 6, fontSize: 12 };

export function AnalyticsPage() {
  const [filter, setFilter] = React.useState<DF>({ days: 30 });
  const a = useApi(() => api.analytics(filter), [filter.days, filter.start, filter.end]);
  useDataChanged(a.reload);
  return (
    <div>
      <PageHeader title="Growth Analytics" description="Followers, reach and what's driving it." actions={<DateFilter value={filter} onChange={setFilter} />} />
      {a.loading && !a.data && <Loading label="Loading analytics…" />}
      {a.error && <ErrorState message={a.error} onRetry={a.reload} />}
      {a.data && <AnalyticsBody a={a.data} />}
    </div>
  );
}

function AnalyticsBody({ a }: { a: Analytics }) {
  const hist = a.follower_history ?? [];
  const src = a.insights?.sources?.[0] ?? hist[0]?.source;
  const refreshed = a.insights?.last_refresh;
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Followers" description={`${a.range.start} → ${a.range.end} · refreshed ${fmtDateTime(refreshed)}`} actions={<SourceBadge source={src} />} />
          <CardBody className="h-72">
            {hist.length === 0 ? (
              <EmptyState title="No follower history in this range" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={hist}>
                  <CartesianGrid stroke="#26282d" vertical={false} />
                  <XAxis dataKey="date" tick={AXIS} tickLine={false} />
                  <YAxis tick={AXIS} tickLine={false} width={48} domain={["auto", "auto"]} />
                  <RTooltip contentStyle={TOOLTIP_STYLE} />
                  <Line type="monotone" dataKey="followers" stroke="#5b7cfa" strokeWidth={2} dot={false} connectNulls={false} />
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Reach & views" description="Daily account totals" actions={<SourceBadge source={src} />} />
          <CardBody className="h-72">
            {hist.length === 0 ? (
              <EmptyState title="No data in this range" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hist}>
                  <CartesianGrid stroke="#26282d" vertical={false} />
                  <XAxis dataKey="date" tick={AXIS} tickLine={false} />
                  <YAxis tick={AXIS} tickLine={false} width={48} />
                  <RTooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "#ffffff08" }} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="reach" fill="#5b7cfa" />
                  <Bar dataKey="views" fill="#8b7cf6" />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader title="Posts" description="Multiple = views ÷ median of the account's other posts in range" />
        {a.posts.length === 0 ? (
          <EmptyState title="No posts in this range" />
        ) : (
          <Table>
            <thead>
              <tr>
                <Th>Post</Th>
                <Th>Pillar</Th>
                <Th>Hook</Th>
                <Th className="text-right">Views</Th>
                <Th className="text-right">Reach</Th>
                <Th className="text-right">Interactions</Th>
                <Th className="text-right">Multiple</Th>
                <Th>Source</Th>
              </tr>
            </thead>
            <tbody>
              {a.posts.map((p) => (
                <tr key={p.id}>
                  <Td className="max-w-xs">
                    <div className="truncate">{p.caption ?? "(no caption)"}</div>
                    <div className="text-xs text-muted">{fmtDateTime(p.published_at)} · {p.media_product_type ?? "—"}</div>
                  </Td>
                  <Td>{humanize(p.pillar)}</Td>
                  <Td>{humanize(p.hook_style)}</Td>
                  <Td className="text-right tabular-nums"><NumOrNA value={p.views} /></Td>
                  <Td className="text-right tabular-nums"><NumOrNA value={p.reach} /></Td>
                  <Td className="text-right tabular-nums"><NumOrNA value={p.total_interactions} /></Td>
                  <Td className="text-right tabular-nums">{p.multiple === null ? <NumOrNA value={null} /> : `${fmtNum(p.multiple, 2)}×`}</Td>
                  <Td><SourceBadge source={p.source} /></Td>
                </tr>
              ))}
            </tbody>
          </Table>
        )}
      </Card>

      <div className="grid gap-6 lg:grid-cols-3">
        <GroupTable title="By pillar" rows={a.by_pillar} />
        <GroupTable title="By hook" rows={a.by_hook} />
        <GroupTable title="By format" rows={a.by_format} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="Best time to post" description="Windows in IST, median outlier multiple" actions={<Badge tone={a.best_time.status === "ok" ? "green" : "amber"}>{a.best_time.status}</Badge>} />
          <CardBody>
            <p className="mb-3 text-sm">{a.best_time.recommendation ?? "Not enough data for a recommendation yet."}</p>
            <GroupRows rows={a.best_time.windows ?? []} label="Window (IST)" digits={2} />
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Metric definitions" />
          <CardBody>
            <dl className="flex flex-col gap-3 text-sm">
              {Object.entries(a.definitions ?? {}).map(([k, v]) => (
                <div key={k}>
                  <dt className="font-medium">{humanize(k)}</dt>
                  <dd className="text-muted">{v}</dd>
                </div>
              ))}
            </dl>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

function GroupTable({ title, rows }: { title: string; rows: GroupStat[] }) {
  return (
    <Card>
      <CardHeader title={title} description="Median views per group" />
      <GroupRows rows={rows} label="Group" />
    </Card>
  );
}

function GroupRows({ rows, label, digits = 0 }: { rows: GroupStat[]; label: string; digits?: number }) {
  if (!rows?.length) return <EmptyState title="No groups yet" />;
  return (
    <Table>
      <thead>
        <tr>
          <Th>{label}</Th>
          <Th className="text-right">n</Th>
          <Th className="text-right">Median</Th>
          <Th />
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.group} className={r.enough_data ? "" : "opacity-50"} data-enough={r.enough_data}>
            <Td>{humanize(r.group)}</Td>
            <Td className="text-right tabular-nums">{r.n}</Td>
            <Td className="text-right tabular-nums"><NumOrNA value={r.median} digits={digits} /></Td>
            <Td className="text-xs text-muted">{r.enough_data ? "" : "n too small"}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
