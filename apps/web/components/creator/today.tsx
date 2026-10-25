"use client";
import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { AlertTriangle, ArrowRight, Bell, Bookmark, Check, Clock, Lightbulb, RefreshCw, ThumbsDown, Users } from "lucide-react";
import { ActivityLink } from "./activity";
import { api, errorMessage, v2, v5, type Recommendation, type Suggestion, type Today } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { CONFIDENCE_LABEL, nextStage, STAGE_LABEL, whenLabel } from "@/lib/creator";
import { cn, fmtDateTime, fmtNum } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Explain } from "@/components/ui/explain";
import { Input } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { DATA_CHANGED, useDataChanged } from "@/components/shell";
import { CopyButton } from "./kit";
import { Shortlist } from "./growth";
import { InterestsSummary, useInterests } from "./interests";
import { Panel, Screen, Tabs } from "./layout";

export function TodayPage() {
  const q = useApi(() => v2.today(), []);
  const recs = useApi(() => v5.recommendations().catch(() => null), []);
  const dash = useApi(() => api.dashboard({ days: 7 }).catch(() => null), []);
  useDataChanged(() => {
    q.reload();
    recs.reload();
    dash.reload();
  });
  if (q.loading && !q.data) return <Loading label="Finding your next reel…" />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const t = q.data!;
  const handle = (dash.data?.account.username ?? "vivek_techfocus").replace(/\s*\(.*\)$/, "");
  return (
    <Screen
      title={`Hi @${handle}`}
      sub="Here's what to do next. One reel at a time."
      actions={
        <>
          <LastUpdated t={t} onSynced={() => window.dispatchEvent(new Event(DATA_CHANGED))} />
          <ActivityLink />
        </>
      }
    >
      <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-12 md:grid-rows-2">
        <div className="flex flex-col md:col-span-5 md:row-span-2 md:min-h-0">
          {recs.data && recs.data.items.length > 0 ? (
            <NextReel recs={recs.data.items} onChanged={recs.reload} />
          ) : recs.loading ? (
            <Panel title="Your next reel">
              <Loading />
            </Panel>
          ) : (
            <FirstIdea
              onAdded={() => {
                q.reload();
                recs.reload();
              }}
            />
          )}
        </div>
        <StepGuide t={t} onChanged={q.reload} className="md:col-span-4" />
        <QuickStats t={t} followers={dash.data?.account.followers ?? t.goal?.current ?? null} gained={dash.data?.metrics.net_follower_growth ?? null} className="md:col-span-3" />
        <WhenToPost t={t} rec={recs.data?.items[0] ?? null} className="md:col-span-4" />
        <MoreTabs t={t} className="md:col-span-3" />
      </div>
    </Screen>
  );
}

function LastUpdated({ t, onSynced }: { t: Today; onSynced: () => void }) {
  const [busy, setBusy] = React.useState(false);
  if (t.mode !== "live") return null;
  return (
    <span className="flex items-center gap-2 text-xs text-muted" data-testid="last-updated">
      Last updated {t.last_sync_at ? fmtDateTime(t.last_sync_at) : "never"} · updates daily
      <Button
        size="sm"
        variant="ghost"
        disabled={busy}
        aria-label="Update from Instagram now"
        onClick={async () => {
          setBusy(true);
          try {
            await api.instagramSync();
            toast.success("Updated from Instagram");
            onSynced();
          } catch (e) {
            toast.error(errorMessage(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        <RefreshCw className={cn(busy && "animate-spin")} /> {busy ? "Updating…" : "Update now"}
      </Button>
    </span>
  );
}

// ---------- Your next reel ----------

const SOURCE_TONE: Record<string, "blue" | "violet" | "green" | "amber" | "neutral"> = {
  reels: "blue",
  comments: "green",
  interests: "violet",
  ideas: "neutral",
  audience: "blue",
  memory: "amber",
  feedback: "amber",
};

export function createHref(r: Recommendation) {
  const p = new URLSearchParams({ topic: r.topic, tab: "hooks" });
  if (r.hook?.text) p.set("hook", r.hook.text);
  if (r.category) p.set("category", r.category);
  if (r.idea_id) p.set("idea", String(r.idea_id));
  return `/create?${p.toString()}`;
}

export function NextReel({ recs, onChanged }: { recs: Recommendation[]; onChanged: () => void }) {
  const [i, setI] = React.useState(0);
  const [busy, setBusy] = React.useState<string | null>(null);
  const r = recs[Math.min(i, recs.length - 1)];
  const act = async (name: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(name);
    try {
      await fn();
      toast.success(ok);
      onChanged();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  return (
    <Panel
      testid="next-reel"
      tone="hero"
      title={<span className="ig-gradient-text">Your next reel</span>}
      what="Picked from your own reels, comments, saves and feedback."
      actions={<Badge tone={r.confidence === "high" ? "green" : r.confidence === "medium" ? "blue" : "amber"}>{CONFIDENCE_LABEL[r.confidence] ?? r.confidence}</Badge>}
      className="md:flex-1"
    >
      <div className="flex flex-col gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge>{r.category_label}</Badge>
            <Badge tone="violet">
              <Users className="size-3" /> For {r.for_who.label}
            </Badge>
            {r.written_by && (
              <Badge tone="blue" title={r.data_topic ? `Based on: ${r.data_topic}` : undefined}>
                Written with AI
              </Badge>
            )}
          </div>
          <h3 className="mt-2 text-2xl font-semibold leading-tight tracking-tight" data-testid="rec-topic">
            {r.topic}
          </h3>
          {r.angle && <p className="mt-1 text-sm text-muted" data-testid="rec-angle">{r.angle}</p>}
        </div>

        <div className="rounded-xl bg-panel-2 p-3.5">
          <p className="text-xs font-medium text-muted">
            <Explain term="hook">Say this in the first 2 seconds</Explain>
          </p>
          <p className="mt-1 text-lg font-semibold leading-snug" data-testid="today-hook">
            “{r.hook.text}”
          </p>
          <div className="mt-2 flex items-center gap-2">
            <CopyButton text={r.hook.text} label="Copy hook" variant="ghost" />
          </div>
        </div>

        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">Why this one</p>
          <ul className="flex flex-col gap-2" data-testid="rec-reasons">
            {r.reasons.map((x) => (
              <li key={x.text} className="flex items-start gap-2 text-sm">
                <Badge tone={SOURCE_TONE[x.source] ?? "neutral"} className="mt-0.5 shrink-0">
                  {x.source_label}
                </Badge>
                <span>{x.text}</span>
              </li>
            ))}
          </ul>
          {r.flags.map((f) => (
            <p key={f} className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-300">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {f}
            </p>
          ))}
        </div>

        <p className="flex items-start gap-2 text-sm" data-testid="best-time">
          <Clock className="mt-0.5 size-4 shrink-0 text-muted" />
          <span>
            <b className="font-semibold">{r.best_time.label}.</b> <span className="text-muted">{r.best_time.why}</span>
          </span>
        </p>

        <div className="flex flex-wrap gap-2">
          <Link href={createHref(r)} className="ig-gradient inline-flex h-10 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold text-white hover:opacity-90">
            Write script <ArrowRight className="size-4" />
          </Link>
          <Button variant="secondary" className="h-10 rounded-xl" disabled={busy !== null} onClick={() => act("save", () => v5.saveRecommendation(r.id), "Saved to Ideas")}>
            <Bookmark /> Save to ideas
          </Button>
        </div>
        <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3 text-xs text-muted">
          <span>Tell us so picks get better:</span>
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => act("made", () => v5.recommendationFeedback(r.id, "made_it"), "Nice! Marked as made.")}>
            <Check /> Made it
          </Button>
          <Button size="sm" variant="ghost" disabled={busy !== null} onClick={() => act("no", () => v5.recommendationFeedback(r.id, "not_for_me"), "Got it. We'll suggest less like this.")}>
            <ThumbsDown /> Not for me
          </Button>
        </div>
        {recs.length > 1 && (
          <div>
            <p className="mb-1.5 text-xs font-medium text-muted">Other picks</p>
            <div className="flex flex-col gap-1.5">
              {recs.map((x, k) =>
                k === i ? null : (
                  <button key={x.id} type="button" onClick={() => setI(k)} className="flex items-center justify-between gap-2 rounded-xl border border-line px-3 py-2 text-left text-sm hover:border-accent">
                    <span className="truncate">{x.topic}</span>
                    <Badge>{x.category_label}</Badge>
                  </button>
                ),
              )}
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}

// ---------- step guide ----------

const STEPS: { key: string; label: string; where: string; href: string | null; count?: string }[] = [
  { key: "idea", label: "Idea", where: "Ideas page", href: "/ideas", count: "idea" },
  { key: "script", label: "Script", where: "Create → Hooks & Script", href: "/create", count: "script" },
  { key: "record", label: "Record", where: "Your phone camera", href: null, count: "recording" },
  { key: "edit", label: "Edit", where: "CapCut or Instagram's editor", href: null, count: "editing" },
  { key: "post", label: "Post", where: "Instagram app (copy the caption from Create)", href: "/create?tab=caption", count: "ready" },
  { key: "check", label: "Check results after 48h", where: "Insights → Reels", href: "/insights?tab=content" },
];

function StepGuide({ t, onChanged, className }: { t: Today; onChanged: () => void; className?: string }) {
  return (
    <Panel
      title="How a reel gets made"
      what="Six steps. The number is how many of your ideas are at each one."
      todo={t.suggestion ? `Next: ${t.suggestion.step.toLowerCase()} “${t.suggestion.title}”` : "Start with step 1: add an idea."}
      className={className}
    >
      <ol className="flex flex-col gap-0.5" data-testid="step-guide">
        {STEPS.map((s, n) => {
          const c = s.count ? (t.pipeline_counts?.[s.count] ?? 0) : null;
          const inner = (
            <>
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-panel-2 text-xs font-semibold">{n + 1}</span>
              <span className="min-w-0 flex-1">
                <span className="block text-sm font-medium">{s.label}</span>
                <span className="block truncate text-[11px] text-muted">{s.where}</span>
              </span>
              {c !== null && <span className={cn("text-xs tabular-nums", c ? "font-semibold" : "text-muted")}>{c}</span>}
            </>
          );
          return (
            <li key={s.key}>
              {s.href ? (
                <Link href={s.href} className="flex items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-panel-2">
                  {inner}
                </Link>
              ) : (
                <div className="flex items-center gap-3 px-2 py-1.5">{inner}</div>
              )}
            </li>
          );
        })}
      </ol>
      {t.suggestion && <ContinueCard s={t.suggestion} onChanged={onChanged} />}
    </Panel>
  );
}

function ContinueCard({ s, onChanged }: { s: Suggestion; onChanged: () => void }) {
  const [busy, setBusy] = React.useState(false);
  const next = nextStage(s.status);
  return (
    <div data-testid="next-post" className="mt-3 rounded-xl border border-line p-3">
      <div className="flex items-center gap-2 text-xs">
        <Badge tone="blue">{s.step}</Badge>
        <span className="text-muted">Continue where you left off</span>
      </div>
      <p className="mt-1 text-sm font-semibold">{s.title}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Link href={`/create?idea=${s.idea_id}`} className="inline-flex h-8 items-center gap-1 rounded-lg border border-line px-2.5 text-xs font-medium hover:bg-panel-2">
          Open in Create <ArrowRight className="size-3.5" />
        </Link>
        {next && (
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                await v2.updateIdea(s.idea_id, { status: next });
                toast.success(`Nice. Moved to ${STAGE_LABEL[next]}.`);
                onChanged();
              } catch (e) {
                toast.error(errorMessage(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            Mark done → {STAGE_LABEL[next]}
          </Button>
        )}
      </div>
    </div>
  );
}

// ---------- stats / when to post / tabs ----------

function QuickStats({ t, followers, gained, className }: { t: Today; followers: number | null; gained: number | null; className?: string }) {
  const g = t.goal;
  const pct = g?.configured && g.target ? Math.min(100, ((g.current ?? 0) / g.target) * 100) : 0;
  return (
    <Panel title="Quick stats" what="Where your account is right now." className={className}>
      <dl className="grid grid-cols-2 gap-3">
        <div data-testid="followers">
          <dt className="text-xs text-muted">
            <Explain term="followers" />
          </dt>
          <dd className="text-2xl font-semibold tabular-nums">
            {fmtNum(followers) ?? "–"}
            <span className="sr-only"> followers</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Gained this week</dt>
          <dd className={cn("text-2xl font-semibold tabular-nums", gained !== null && gained > 0 && "text-emerald-600 dark:text-emerald-400")} data-testid="gained">
            {gained === null ? "–" : `${gained > 0 ? "+" : ""}${fmtNum(gained)}`}
          </dd>
        </div>
        <div className="col-span-2">
          <dt className="text-xs text-muted">Posted this week</dt>
          <dd className="text-lg font-semibold tabular-nums">
            {t.week.published} <span className="text-sm font-normal text-muted">of {t.week.target} planned</span>
          </dd>
        </div>
      </dl>
      <div className="mt-3 text-xs">
        {!g?.configured ? (
          <p className="text-muted">
            <Link href="/settings" className="font-semibold text-accent">
              Set your goal
            </Link>{" "}
            to see if you&apos;re on pace.
          </p>
        ) : (
          <>
            <div className="flex justify-between text-muted">
              <span>
                Goal {fmtNum(g.target)}
                {g.days_remaining != null ? ` · ${g.days_remaining}d left` : ""}
              </span>
              <Link href="/settings" className="font-semibold text-accent">
                Edit
              </Link>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-panel-2">
              <div className="ig-gradient h-1.5 rounded-full" style={{ width: `${Math.max(2, pct)}%` }} />
            </div>
            <p className="mt-1 text-muted">
              You need ~{fmtNum(Math.round(g.required_per_day ?? 0))}/day; you&apos;re doing ~{fmtNum(Math.round(g.actual_per_day ?? 0))}/day.
            </p>
          </>
        )}
      </div>
    </Panel>
  );
}

function WhenToPost({ t, rec, className }: { t: Today; rec: Recommendation | null; className?: string }) {
  const [now] = React.useState(() => Date.now());
  const soon = t.reminders.filter((r) => {
    const d = new Date(r.scheduled_at).getTime() - now;
    return d > -3600000 && d < 48 * 3600000;
  });
  return (
    <Panel title="When to post" what="Best time, from when your followers are online and how past reels did (IST)." todo={rec ? rec.best_time.label : undefined} className={className}>
      {rec && (
        <p className="text-sm text-muted">
          {rec.best_time.why} <span className="text-[11px]">({rec.best_time.source_label})</span>
        </p>
      )}
      <p className="mb-1.5 mt-3 text-xs font-medium text-muted">Planned for the next 48 hours</p>
      {soon.length === 0 ? (
        <p className="text-sm text-muted">
          Nothing planned.{" "}
          <Link href="/ideas?view=week" className="text-accent">
            Plan a post
          </Link>
        </p>
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {soon.map((r) => (
            <li key={r.id} className="flex items-center gap-2 py-2 text-sm">
              <Bell className="size-4 shrink-0" />
              <span className="min-w-0 flex-1 truncate">{r.title}</span>
              <span className="shrink-0 text-xs text-muted">{whenLabel(r.scheduled_at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

function MoreTabs({ t, className }: { t: Today; className?: string }) {
  const [tab, setTab] = React.useState<"into" | "short">(t.shortlist?.length ? "short" : "into");
  const ints = useInterests();
  return (
    <Panel
      title={tab === "into" ? "What you're into" : "Ready to make"}
      what={tab === "into" ? "From your own saves, likes and notes." : "Your ideas, ranked by stage and past results."}
      className={className}
    >
      <Tabs
        label="Home extras"
        value={tab}
        onChange={setTab}
        className="mb-3"
        items={[
          ["short", "Ideas"],
          ["into", "You like"],
        ]}
      />
      {tab === "short" ? (
        t.shortlist?.length ? (
          <Shortlist items={t.shortlist} compact />
        ) : (
          <p className="text-sm text-muted">
            No ideas yet.{" "}
            <Link href="/ideas" className="text-accent">
              Add one
            </Link>
            .
          </p>
        )
      ) : ints.data ? (
        <InterestsSummary p={ints.data} />
      ) : (
        <Loading />
      )}
    </Panel>
  );
}

export function FirstIdea({ onAdded }: { onAdded: () => void }) {
  const [title, setTitle] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  return (
    <section data-testid="first-idea" className="flex flex-1 flex-col items-center justify-center rounded-2xl border border-dashed border-line bg-panel p-6 text-center md:p-10">
      <Lightbulb className="mx-auto size-6 text-accent" />
      <h2 className="mt-3 text-xl font-semibold">Capture your first idea</h2>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted">Anything you&apos;d explain to a friend: a tech concept, a career lesson, an AI tool. We&apos;ll help with the hook and caption.</p>
      <form
        className="mx-auto mt-5 flex w-full max-w-lg gap-2"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!title.trim()) return;
          setBusy(true);
          try {
            await v2.quickIdea({ title: title.trim(), force: true });
            toast.success("Idea saved");
            setTitle("");
            onAdded();
          } catch (err) {
            toast.error(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Input aria-label="Your idea" placeholder="e.g. What is an API, explained with chai" value={title} onChange={(e) => setTitle(e.target.value)} className="h-10" />
        <Button type="submit" className="h-10" disabled={busy || !title.trim()}>
          Save idea
        </Button>
      </form>
    </section>
  );
}
