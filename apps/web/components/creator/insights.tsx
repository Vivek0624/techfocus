"use client";
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { errorMessage, v2, type GroupRow, type Insight, type InsightPost, type Insights } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { big, CATEGORIES, catLabel, CONFIDENCE_LABEL, FORMATS, fmtLabel } from "@/lib/creator";
import { cn, fmtDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { useDataChanged } from "@/components/shell";
import { Explain } from "@/components/ui/explain";
import { Bar, Section } from "./kit";
import { Panel, Screen, Tabs } from "./layout";
import { InterestsDetail } from "./interests";
import { AudienceTab, FollowersSection } from "./audience";
import { AUDIENCES, audLabel, FatigueSection, GapsSection, ScheduleSection, SegmentsSection } from "./growth";

type InsTab = "overview" | "patterns" | "content" | "comments" | "audience" | "interests";
const TABS: [InsTab, string][] = [
  ["overview", "Overview"],
  ["patterns", "Patterns"],
  ["content", "Content"],
  ["comments", "Comments"],
  ["audience", "Audience"],
  ["interests", "You like"],
];

/** A grid cell that scrolls on its own (for sections that already draw their own card). */
function Cell({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn("thin-scroll md:min-h-0 md:overflow-y-auto [&>section]:rounded-2xl", className)}>{children}</div>;
}

export function InsightsPage() {
  const params = useSearchParams();
  const initial = params?.get("tab") as InsTab | null;
  const [tab, setTab] = React.useState<InsTab>(initial && TABS.some(([k]) => k === initial) ? initial : "overview");
  const q = useApi(() => v2.insights(), []);
  useDataChanged(q.reload);
  if (q.loading && !q.data) return <Loading label="Reading your posts…" />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const d = q.data!;
  return (
    <Screen title="Insights" sub="What's working on your account, compared only against your own posts." actions={<Tabs label="Insights" value={tab} onChange={setTab} items={TABS} />}>
      {d.sample_size === 0 && tab !== "interests" ? (
        <EmptyState title="No posts yet">
          <p>
            <Link href="/connect" className="text-accent hover:underline">Connect Instagram or add your numbers</Link> and your coach will start spotting patterns.
          </p>
        </EmptyState>
      ) : (
        <>
          {tab === "overview" && (
            <>
              <Headline d={d} />
              <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-3">
                <Cell><FollowersSection history={d.follower_history ?? []} /></Cell>
                <Panel title="What your coach noticed" what="Patterns in your own reels, with how many posts back each one." todo="Act on the top one this week.">
                  <Coach items={d.insights} />
                </Panel>
                <Panel title="What to do next" what="Keep, fix or drop, based on your results.">
                  <RepeatImproveStop d={d} />
                </Panel>
              </div>
            </>
          )}
          {tab === "patterns" && <Engine d={d} />}
          {tab === "content" && <PostsTable posts={d.posts} onChange={q.reload} />}
          {tab === "comments" && (
            <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-2">
              <Cell><GapsSection /></Cell>
              <Cell><FatigueSection /></Cell>
            </div>
          )}
          {tab === "audience" && <Cell className="md:flex-1"><AudienceTab /></Cell>}
          {tab === "interests" && <InterestsDetail />}
        </>
      )}
      <p className="shrink-0 text-[11px] text-muted">{d.note}</p>
    </Screen>
  );
}

function Stat({ label, value, hint, term }: { label: string; value: string; hint?: string; term?: string }) {
  return (
    <div data-testid={`stat-${label}`} className="rounded-2xl border border-line bg-panel px-4 py-3">
      <p className="text-xs text-muted">{term ? <Explain term={term}>{label}</Explain> : label}</p>
      <p className={cn("mt-1 text-2xl font-semibold tabular-nums", value === "unavailable" && "text-base font-normal text-muted")}>{value}</p>
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

function Headline({ d }: { d: Insights }) {
  const s = d.summary;
  const n = (x: number | null) => (x === null || x === undefined ? "unavailable" : String(x));
  return (
    <div className="grid shrink-0 grid-cols-2 gap-3 md:grid-cols-5">
      <Stat label="Reels" term="reel" value={String(d.sample_size)} hint={d.tagged < d.sample_size ? `${d.sample_size - d.tagged} need tags` : "analysed"} />
      <Stat label="Plays" term="views" value={big(s.median_views)} hint="on a usual reel" />
      <Stat label="Shares" term="shares" value={n(s.median_shares_per_1k)} hint="per 1,000 people reached" />
      <Stat label="Saves" term="saves" value={n(s.median_saves_per_1k)} hint="per 1,000 people reached" />
      <Stat label="Average watch time" term="watch_time" value={s.median_watch_seconds === null ? "unavailable" : `${s.median_watch_seconds}s`} hint="on a usual reel" />
    </div>
  );
}

/** Rewrite engine jargon into plain words. */
function plain(s: string | null | undefined) {
  return (s ?? "")
    .replace(/median ([\d.]+)x your usual views/g, "usually $1x your usual views")
    .replace(/\(n=(\d+)\)/g, "(based on $1 posts)")
    .replace(/, n=(\d+)\)/g, ", based on $1 posts)")
    .replace(/\bmedian\b/g, "usually");
}

function Coach({ items }: { items: Insight[] }) {
  return (
    <section>
      {items.length === 0 ? (
        <p className="text-sm text-muted">Nothing clear yet. Tag a few more posts below.</p>
      ) : (
        <ul className="flex flex-col gap-3" data-testid="coach">
          {items.map((it, i) => (
            <CoachItem key={i} it={it} />
          ))}
        </ul>
      )}
    </section>
  );
}

function CoachItem({ it }: { it: Insight }) {
  const [made, setMade] = React.useState(false);
  const conf = it.confidence ?? "none";
  const postTitle = it.headline.match(/“(.+?)”/)?.[1];
  return (
    <li className="border-b border-line py-3 last:border-0">
      <div className="flex items-start justify-between gap-3">
        <p className="font-semibold leading-snug">{it.headline}</p>
        <Badge tone={conf === "high" ? "green" : conf === "medium" ? "blue" : conf === "low" ? "amber" : "neutral"}>{CONFIDENCE_LABEL[conf] ?? conf}</Badge>
      </div>
      {it.detail && <p className="mt-1 text-sm text-muted">{plain(it.detail)}</p>}
      {it.action && (
        <p className="mt-2 text-sm">
          <span className="text-accent">Try next:</span> {it.action}
        </p>
      )}
      {it.kind === "outlier" && postTitle && (
        <div className="mt-3">
          {made ? (
            <Link href="/ideas" className="text-sm text-accent hover:underline">
              Follow-up saved. Open Ideas →
            </Link>
          ) : (
            <Button
              size="sm"
              variant="secondary"
              onClick={async () => {
                try {
                  await v2.quickIdea({ title: `Follow-up: ${postTitle}`, force: true });
                  setMade(true);
                  toast.success("Follow-up added to Ideas");
                } catch (e) {
                  toast.error(errorMessage(e));
                }
              }}
            >
              Make a follow-up
            </Button>
          )}
        </div>
      )}
    </li>
  );
}

function Answer({ title, rows, unit }: { title: string; rows: GroupRow[]; unit: "x" | "per1k" }) {
  const max = Math.max(0, ...rows.map((r) => r.median));
  return (
    <Section title={title}>
      {rows.length === 0 ? (
        <p className="text-sm text-muted">Not enough tagged posts yet.</p>
      ) : (
        <ul className="flex flex-col gap-3">
          {rows.slice(0, 5).map((r) => {
            const dim = r.n < 2;
            return (
              <li key={r.group} className={cn(dim && "opacity-50")}>
                <div className="flex items-baseline justify-between gap-2 text-sm">
                  <span>{r.label}</span>
                  <span className="tabular-nums">{unit === "x" ? `${r.median}x your usual plays` : `${r.median} per 1,000 reached`}</span>
                </div>
                <Bar value={r.median} max={max} dim={dim} className="mt-1" />
                <p className="mt-0.5 text-[11px] text-muted">
                  based on {r.n} post{r.n === 1 ? "" : "s"}
                  {dim ? " · too early to tell" : ""}
                </p>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function Engine({ d }: { d: Insights }) {
  const a = d.answers;
  return (
    <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-3 md:grid-rows-2">
      <Cell><Answer title="Which hooks work" rows={a.best_hooks} unit="x" /></Cell>
      <Cell><Answer title="Topics that get shared" rows={a.topics_by_shares} unit="per1k" /></Cell>
      <Cell><SegmentsSection /></Cell>
      <Cell><Answer title="Talking head vs motion graphics vs screen recording" rows={a.formats} unit="x" /></Cell>
      <Cell><Answer title="Best length" rows={a.lengths} unit="x" /></Cell>
      <Cell><ScheduleSection /></Cell>
    </div>
  );
}

/** AI-written brief from the coach's own findings. Loads after the page; hidden when AI is off or fails. */
function CoachBriefCard() {
  const q = useApi(() => v2.coachAI(), []);
  if (q.loading && !q.data) return <p className="pb-3 text-xs text-muted">Your coach is writing a summary…</p>;
  const b = q.data;
  if (!b?.available || !(b.headline || b.this_week?.length)) return null;
  return (
    <div className="mb-1 rounded-xl bg-panel-2 p-3.5" data-testid="coach-brief">
      <div className="mb-1.5 flex items-center gap-2">
        <p className="text-xs font-medium text-muted">Coach&apos;s take</p>
        <Badge tone="blue">Written with AI</Badge>
      </div>
      {b.headline && <p className="text-sm font-semibold leading-snug">{b.headline}</p>}
      {!!b.this_week?.length && (
        <>
          <p className="mt-3 text-xs font-medium text-muted">This week</p>
          <ol className="mt-1 flex list-decimal flex-col gap-1 pl-4 text-sm">
            {b.this_week.map((x) => <li key={x}>{x}</li>)}
          </ol>
        </>
      )}
      {(!!b.working?.length || !!b.fix?.length) && (
        <div className="mt-3 grid gap-2 text-sm">
          {b.working?.map((x) => <p key={x}><span className="text-emerald-700 dark:text-emerald-300">Working: </span>{x}</p>)}
          {b.fix?.map((x) => <p key={x}><span className="text-amber-700 dark:text-amber-300">Fix: </span>{x}</p>)}
        </div>
      )}
    </div>
  );
}

function RepeatImproveStop({ d }: { d: Insights }) {
  const a = d.answers;
  return (
    <section>
      <CoachBriefCard />
      <div className="flex flex-col gap-2" data-testid="ris">
        {(
          [
            ["Repeat", a.repeat, "text-emerald-700 dark:text-emerald-300"],
            ["Improve", a.improve, "text-amber-700 dark:text-amber-300"],
            ["Stop", a.stop, "text-red-700 dark:text-red-300"],
          ] as const
        ).map(([t, list, c]) => (
          <div key={t} className="border-b border-line py-3 last:border-0">
            <h3 className={cn("text-sm font-semibold", c)}>{t}</h3>
            <ul className="mt-2 flex list-disc flex-col gap-1.5 pl-4 text-sm">
              {list.map((x) => (
                <li key={x}>{plain(x)}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}

function PostsTable({ posts, onChange }: { posts: InsightPost[]; onChange: () => void }) {
  return (
    <Panel title="Your reels" what="Every post with its numbers. Check each one 48 hours after posting." todo="Tag topic, format, length and hook so the coach can compare them." className="md:flex-1" bodyClassName="px-0 pb-0">
      <div className="thin-scroll overflow-x-auto md:h-full">
        <table className="w-full min-w-[1180px] text-sm">
          <thead className="sticky top-0 z-10 bg-panel text-left text-xs text-muted shadow-[0_1px_0_var(--ig-line)]">
            <tr>
              {(
                [
                  ["Post", null],
                  ["Plays", "views"],
                  ["People reached", "reach"],
                  ["Shares", "shares"],
                  ["Saves", "saves"],
                  ["How much they watched", "retention"],
                  ["vs your usual", "multiple"],
                  ["Topic", null],
                  ["Who it's for", "audience"],
                  ["Format", "format"],
                  ["Length (s)", null],
                  ["Hook", "hook"],
                ] as [string, string | null][]
              ).map(([h, t]) => (
                <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">
                  {t ? <Explain term={t}>{h}</Explain> : h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {posts.map((p) => (
              <PostRow key={p.id} p={p} onChange={onChange} />
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function PostRow({ p, onChange }: { p: InsightPost; onChange: () => void }) {
  const untagged = !p.pillar || !p.format_style || !p.length_seconds || !p.hook_text;
  const [hook, setHook] = React.useState(p.hook_text ?? "");
  const [len, setLen] = React.useState(p.length_seconds ? String(p.length_seconds) : "");
  const patch = async (body: Parameters<typeof v2.tagPost>[1]) => {
    try {
      await v2.tagPost(p.id, body);
      toast.success("Tag saved");
      onChange();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const m = p.multiple;
  return (
    <tr className={cn("border-t border-line/60 align-top", untagged && "bg-amber-500/5")}>
      <td className="max-w-56 px-3 py-2">
        <p className="font-medium leading-snug">{p.title ?? p.caption ?? "Untitled"}</p>
        <p className="text-xs text-muted">{fmtDate(p.published_at)}</p>
        {untagged && <Badge tone="amber" className="mt-1">Tag me</Badge>}
        <Attribution p={p} />
      </td>
      <td className="px-3 py-2 tabular-nums">{big(p.views)}</td>
      <td className="px-3 py-2 tabular-nums">{big(p.reach)}</td>
      <td className="px-3 py-2 tabular-nums">{big(p.shares)}</td>
      <td className="px-3 py-2 tabular-nums">{big(p.saved)}</td>
      <td className="px-3 py-2"><Retention p={p} /></td>
      <td className={cn("px-3 py-2 tabular-nums", m !== null && m >= 1.5 && "text-emerald-700 dark:text-emerald-300", m !== null && m < 0.75 && "text-red-700 dark:text-red-300")}>{m === null ? "—" : `${m}x`}</td>
      <td className="px-3 py-2">
        <Select aria-label="Topic" value={p.pillar ?? ""} onChange={(e) => patch({ category: e.target.value || null })} className="h-8 w-36 text-xs">
          <option value="">—</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {catLabel(c)}
            </option>
          ))}
        </Select>
      </td>
      <td className="px-3 py-2">
        <Select aria-label="Audience" value={p.audience_tag && !p.audience_tag.inferred ? p.audience_tag.audience : ""} onChange={(e) => patch({ audience: e.target.value || null })} className="h-8 w-36 text-xs">
          <option value="">{p.audience_tag ? `Auto: ${audLabel(p.audience_tag.audience)}` : "—"}</option>
          {AUDIENCES.map((a) => (
            <option key={a} value={a}>
              {audLabel(a)}
            </option>
          ))}
        </Select>
      </td>
      <td className="px-3 py-2">
        <Select aria-label="Format" value={p.format_style ?? ""} onChange={(e) => patch({ format_style: e.target.value || null })} className="h-8 w-36 text-xs">
          <option value="">—</option>
          {FORMATS.map((f) => (
            <option key={f} value={f}>
              {fmtLabel(f)}
            </option>
          ))}
        </Select>
      </td>
      <td className="px-3 py-2">
        <Input
          aria-label="Length seconds"
          type="number"
          min={1}
          value={len}
          onChange={(e) => setLen(e.target.value)}
          onBlur={() => len !== (p.length_seconds ? String(p.length_seconds) : "") && patch({ length_seconds: len ? Number(len) : null })}
          className="h-8 w-20 text-xs"
        />
      </td>
      <td className="px-3 py-2">
        <Input aria-label="Hook text" value={hook} onChange={(e) => setHook(e.target.value)} onBlur={() => hook !== (p.hook_text ?? "") && patch({ hook_text: hook || null })} className="h-8 w-56 text-xs" />
      </td>
    </tr>
  );
}

function Retention({ p }: { p: InsightPost }) {
  const r = p.retention;
  if (!r) return <span className="text-muted">—</span>;
  return (
    <div className="w-40" data-testid="retention">
      <p className="tabular-nums">
        <b>{r.avg_seconds}s</b>
        {r.length_seconds ? <span className="text-muted"> of {r.length_seconds}s</span> : null}
        {r.percent_watched != null && <span className="text-muted"> · {r.percent_watched}%</span>}
      </p>
      {r.percent_watched != null && <Bar value={r.percent_watched} className="mt-1 h-1.5" dim={r.percent_watched < 30} />}
      <p className="mt-1 text-[11px] leading-snug text-muted">{r.verdict}</p>
    </div>
  );
}

function Attribution({ p }: { p: InsightPost }) {
  const a = p.attribution;
  if (!a) return null;
  if (a.available)
    return (
      <p className="mt-1 text-xs" data-testid="attribution">
        <span className="font-semibold">{a.follows ?? "—"}</span> follows from this post · <span className="font-semibold">{a.profile_visits ?? "—"}</span> profile visits
        {a.reposts != null && <> · {a.reposts} reposts</>}
      </p>
    );
  return (
    <p className="mt-1 text-[11px] text-muted" data-testid="attribution">
      {a.note}
      {a.reposts != null && <> · {a.reposts} reposts</>}
    </p>
  );
}
