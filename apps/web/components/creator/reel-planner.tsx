"use client";
import * as React from "react";
import { toast } from "sonner";
import { Clapperboard, ExternalLink, RefreshCw, Search, Trash2, Upload } from "lucide-react";
import {
  errorMessage,
  reels,
  type ReelPackage,
  type ReelPlanSummary,
  type ReelPlatform,
  type ReelSection,
  type SavedReelPlan,
  type TrendReport,
  type TrendTopic,
} from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { CopyButton } from "./kit";
import { Panel } from "./layout";

const POTENTIAL_TONE: Record<string, BadgeTone> = { high: "green", medium: "amber", low: "neutral" };
const secs = (n: number) => `${Math.round(n)}s`;
const SECTION_LABEL: Record<ReelSection, string> = { hooks: "hooks", script: "script", shots: "shot list", caption: "caption", cta: "CTAs" };

/** The plan as plain text, for the "Copy whole plan" button and the per-section copies. */
function asText(p: ReelPackage, part?: ReelSection): string {
  const hooks = p.hooks.map((h, i) => `${i + 1}. [${h.hook_type.replace(/_/g, " ")}] ${h.text}\n   why: ${h.why_it_works}`).join("\n");
  const script = p.script.map((s) => `[${secs(s.t_start)}-${secs(s.t_end)}] ${s.section.toUpperCase()}\n${s.spoken}\nON SCREEN: ${s.on_screen_text}`).join("\n\n");
  const shots = p.shots
    .map((s) => `SHOT ${s.order} (${secs(s.seconds)}) ${s.shot_type}\nFraming: ${s.framing}\nWhere: ${s.location}\nAction: ${s.action}\nDelivery: ${s.delivery_tone}${s.b_roll.length ? `\nB-roll: ${s.b_roll.join(", ")}` : ""}`)
    .join("\n\n");
  const caption = `${p.caption}\n\n${p.hashtags.join(" ")}\n\nPinned comment: ${p.pinned_comment}`;
  const cta = `Primary CTA: ${p.cta_primary}\nAlternative: ${p.cta_alternative}`;
  if (part === "hooks") return hooks;
  if (part === "script") return script;
  if (part === "shots") return shots;
  if (part === "caption") return caption;
  if (part === "cta") return cta;
  return [
    `${p.topic}  (${p.total_duration_seconds}s)`,
    `One idea: ${p.one_idea}`,
    `Audience: ${p.audience}`,
    `\nHOOKS\n${hooks}`,
    `\nSCRIPT\n${script}`,
    `\nSHOT LIST\n${shots}`,
    `\nCAPTION\n${caption}`,
    `\nCTA\n${cta}`,
    `\nAUDIO\n${p.audio_direction}`,
    `\nPOSTING TIME\n${p.best_posting_time}`,
    `\nA/B TEST\n${p.ab_test_idea}`,
  ].join("\n");
}

/** A block with its own heading, copy button and optional "regenerate just this" action. */
function Block({ title, section, text, onRegenerate, busy, children }: { title: string; section?: ReelSection; text: string; onRegenerate?: (s: ReelSection) => void; busy?: boolean; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-line bg-panel-2/40 p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{title}</h3>
        <div className="flex items-center gap-1.5">
          {section && onRegenerate && (
            <Button size="sm" variant="ghost" disabled={busy} onClick={() => onRegenerate(section)} aria-label={`Regenerate ${SECTION_LABEL[section]}`}>
              <RefreshCw className={cn(busy && "animate-spin")} /> Redo
            </Button>
          )}
          <CopyButton text={text} />
        </div>
      </div>
      {children}
    </section>
  );
}

export function ReelPlanner() {
  const meta = useApi(() => reels.meta(), []);
  const saved = useApi(() => reels.plans(), []);
  // null = untouched, so the niche and platform follow the profile prefill until the user types.
  const [typedNiche, setNiche] = React.useState<string | null>(null);
  const [pickedPlatform, setPlatform] = React.useState<ReelPlatform | null>(null);
  const niche = typedNiche ?? meta.data?.niche ?? "";
  const platform = pickedPlatform ?? meta.data?.default_platform ?? "instagram_reels";
  const [duration, setDuration] = React.useState(32);
  const [report, setReport] = React.useState<TrendReport | null>(null);
  const [picked, setPicked] = React.useState<TrendTopic | null>(null);
  const [plan, setPlan] = React.useState<SavedReelPlan | null>(null);
  const [finding, setFinding] = React.useState(false);
  const [planning, setPlanning] = React.useState(false);
  const [redoing, setRedoing] = React.useState<ReelSection | null>(null);
  const [err, setErr] = React.useState<string | null>(null);

  const findTrends = async () => {
    if (!niche.trim()) return toast.error("Type a niche first, for example “AI tools for developers”.");
    setFinding(true);
    setErr(null);
    setReport(null);
    setPicked(null);
    setPlan(null);
    try {
      setReport(await reels.trends({ niche: niche.trim(), platform }));
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setFinding(false);
    }
  };

  const generate = async (topic: TrendTopic) => {
    setPlanning(true);
    setErr(null);
    try {
      const r = await reels.plan({ niche: niche.trim(), platform, topic, duration });
      setPlan(r);
      saved.reload();
      toast.success("Reel plan saved. It's in My reel plans.");
    } catch (e) {
      setErr(errorMessage(e));
    } finally {
      setPlanning(false);
    }
  };

  const regenerate = async (section: ReelSection) => {
    if (!plan) return;
    setRedoing(section);
    try {
      setPlan(await reels.regenerate(plan.id, section));
      toast.success(`New ${SECTION_LABEL[section]}.`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setRedoing(null);
    }
  };

  const open = async (id: number) => {
    setErr(null);
    try {
      const r = await reels.getPlan(id);
      setPlan(r);
      setNiche(r.niche);
      setPlatform(r.platform);
      setPicked((r.topic as TrendTopic) ?? null);
    } catch (e) {
      setErr(errorMessage(e));
    }
  };

  const remove = async (id: number) => {
    try {
      await reels.deletePlan(id);
      if (plan?.id === id) setPlan(null);
      saved.reload();
      toast.success("Deleted.");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const items = saved.data?.items ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] md:min-h-0 md:flex-1">
      <div className="flex flex-col gap-4 md:min-h-0">
        <Panel
          title="Reel Planner"
          what="Pick a niche, see what is getting attention, then turn one topic into a reel you can film today."
          todo={report ? "Choose a topic, then generate the plan." : "Enter your niche and find topics."}
        >
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto_auto] sm:items-end">
            <Field label="Niche" htmlFor="rp-niche" hint={meta.data?.niche ? "Prefilled from your profile. Change it any time." : undefined}>
              <Input id="rp-niche" value={niche} placeholder="e.g. AI tools for Indian developers" onChange={(e) => setNiche(e.target.value)} onKeyDown={(e) => e.key === "Enter" && findTrends()} />
            </Field>
            <Field label="Platform" htmlFor="rp-platform">
              <Select id="rp-platform" value={platform} onChange={(e) => setPlatform(e.target.value as ReelPlatform)} className="sm:w-44">
                {(meta.data?.platforms ?? [{ value: "instagram_reels" as ReelPlatform, label: "Instagram Reels" }]).map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
              </Select>
            </Field>
            <Button onClick={findTrends} disabled={finding} className="h-9 sm:mb-0">
              <Search /> {finding ? "Researching…" : "Find trending topics"}
            </Button>
          </div>
          {meta.data && !meta.data.live_research_available && (
            <p className="mt-3 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-200">
              No live search provider is configured, so topics come from model knowledge only, not live results. Set <code>RESEARCH_API_URL</code> in <code>.env</code> to research the live web.
            </p>
          )}
          {err && <ErrorState message={err} onRetry={findTrends} />}
          {finding && <Loading label="Researching the niche…" />}
          {report && (
            <div className="mt-4">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge tone={report.live_research_performed ? "green" : "amber"}>{report.live_research_performed ? "Live search" : "Model-knowledge only, not live"}</Badge>
                {report.source?.startsWith("template") && <Badge tone="neutral">built-in template (no model configured)</Badge>}
                <span className="text-xs text-muted">{report.topics.length} topics</span>
              </div>
              <p className="mb-3 text-xs text-muted">{report.disclosure}</p>
              <ul className="grid gap-2.5">
                {report.topics.map((t, i) => {
                  const active = picked?.title === t.title;
                  return (
                    <li key={`${t.title}-${i}`}>
                      <button
                        type="button"
                        aria-pressed={active}
                        onClick={() => setPicked(t)}
                        className={cn("w-full rounded-xl border p-3.5 text-left transition-colors", active ? "border-accent bg-accent/10" : "border-line hover:bg-panel-2")}
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-sm font-semibold leading-snug">{t.title}</p>
                          <Badge tone={POTENTIAL_TONE[t.engagement_potential] ?? "neutral"}>{t.engagement_potential}</Badge>
                        </div>
                        <p className="mt-1.5 text-xs text-muted">
                          <span className="font-medium text-fg">Why now:</span> {t.why_trending}
                        </p>
                        <p className="mt-1 text-xs text-muted">
                          <span className="font-medium text-fg">Your angle:</span> {t.angle}
                        </p>
                        <p className="mt-1 text-xs text-muted">{t.potential_reason}</p>
                        {t.sources.length > 0 && (
                          <span className="mt-2 flex flex-wrap gap-2">
                            {t.sources.slice(0, 4).map((s) => (
                              <a key={s.url} href={s.url} target="_blank" rel="noreferrer noopener" onClick={(e) => e.stopPropagation()} className="inline-flex max-w-full items-center gap-1 truncate text-[11px] text-accent underline">
                                <ExternalLink className="size-3 shrink-0" /> {s.title || s.url}
                              </a>
                            ))}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
              <div className="mt-4 flex flex-wrap items-end gap-2">
                <Field label="Target length" htmlFor="rp-dur" className="w-32">
                  <Select id="rp-dur" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
                    {[15, 20, 25, 30, 32, 38, 45].map((d) => (
                      <option key={d} value={d}>
                        {d}s
                      </option>
                    ))}
                  </Select>
                </Field>
                <Button disabled={!picked || planning} onClick={() => picked && generate(picked)}>
                  <Clapperboard /> {planning ? "Writing the reel…" : "Generate reel plan"}
                </Button>
                {!picked && <span className="pb-2 text-xs text-muted">Pick one topic above.</span>}
              </div>
            </div>
          )}
        </Panel>

        {planning && (
          <Panel>
            <Loading label="Writing hooks, script and shot list…" />
          </Panel>
        )}
        {plan && <PlanView plan={plan} onRegenerate={regenerate} redoing={redoing} />}
      </div>

      <Panel title="My reel plans" what="Every plan you generated. Reopen one to copy or redo a section." bodyClassName="md:overflow-y-auto">
        {saved.loading && !saved.data && <Loading />}
        {saved.error && <ErrorState message={saved.error} onRetry={saved.reload} />}
        {saved.data && items.length === 0 && <EmptyState title="No plans yet">Find topics and generate your first reel plan.</EmptyState>}
        <ul className="grid gap-2">
          {items.map((p: ReelPlanSummary) => (
            <li key={p.id} className={cn("rounded-xl border p-3", plan?.id === p.id ? "border-accent bg-accent/10" : "border-line")}>
              <button type="button" aria-label={`Open ${p.title}`} onClick={() => open(p.id)} className="w-full text-left">
                <p className="text-sm font-medium leading-snug">{p.title}</p>
                {p.hook && <p className="mt-1 line-clamp-2 text-xs text-muted">{p.hook}</p>}
                <span className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted">
                  <Badge tone="neutral">{p.niche}</Badge>
                  {p.duration_seconds ? <span>{p.duration_seconds}s</span> : null}
                  {!p.live_research && <Badge tone="amber">not live</Badge>}
                </span>
              </button>
              <div className="mt-2 flex justify-end">
                <Button size="sm" variant="ghost" onClick={() => remove(p.id)} aria-label={`Delete ${p.title}`}>
                  <Trash2 /> Delete
                </Button>
              </div>
            </li>
          ))}
        </ul>
        <div className="mt-4 border-t border-line pt-3">
          <Button variant="outline" disabled title="Not built yet" className="w-full">
            <Upload /> Upload video for auto-edit
          </Button>
          <p className="mt-1.5 text-center text-[11px] text-muted">Coming soon</p>
        </div>
      </Panel>
    </div>
  );
}

function PlanView({ plan, onRegenerate, redoing }: { plan: SavedReelPlan; onRegenerate: (s: ReelSection) => void; redoing: ReelSection | null }) {
  const p = plan.package;
  if (!p?.hooks) return null;
  return (
    <Panel
      title={p.topic}
      what={`One idea: ${p.one_idea}`}
      actions={<CopyButton text={asText(p)} label="Copy whole plan" variant="secondary" />}
      bodyClassName="md:overflow-y-auto"
    >
      <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-muted">
        <Badge tone="blue">{p.total_duration_seconds}s</Badge>
        <Badge tone="neutral">{p.platform.replace(/_/g, " ")}</Badge>
        {plan.source?.startsWith("template") ? <Badge tone="amber">built-in template</Badge> : <Badge tone="neutral">written by {plan.source}</Badge>}
        <span>For: {p.audience}</span>
      </div>

      <div className="grid gap-3">
        <Block title="Hooks — first 1-3 seconds" section="hooks" text={asText(p, "hooks")} onRegenerate={onRegenerate} busy={redoing === "hooks"}>
          <ol className="grid gap-2">
            {p.hooks.map((h, i) => (
              <li key={i} className="rounded-lg border border-line bg-panel p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="text-sm font-medium">{h.text}</p>
                  <Badge tone="violet">{h.hook_type.replace(/_/g, " ")}</Badge>
                </div>
                <p className="mt-1 text-xs text-muted">{h.why_it_works}</p>
              </li>
            ))}
          </ol>
        </Block>

        <Block title="Script — what you say" section="script" text={asText(p, "script")} onRegenerate={onRegenerate} busy={redoing === "script"}>
          <ol className="grid gap-2">
            {p.script.map((s, i) => (
              <li key={i} className="rounded-lg border border-line bg-panel p-3">
                <div className="flex items-center gap-2">
                  <Badge tone="blue">
                    {secs(s.t_start)}–{secs(s.t_end)}
                  </Badge>
                  <span className="text-xs font-semibold uppercase tracking-wide text-muted">{s.section}</span>
                </div>
                <p className="mt-1.5 whitespace-pre-line text-sm leading-relaxed">{s.spoken}</p>
                <p className="mt-1.5 text-xs text-muted">
                  <span className="font-medium text-fg">On screen:</span> {s.on_screen_text}
                </p>
              </li>
            ))}
          </ol>
        </Block>

        <Block title="Shot list — how to film it" section="shots" text={asText(p, "shots")} onRegenerate={onRegenerate} busy={redoing === "shots"}>
          <ol className="grid gap-2">
            {p.shots.map((s) => (
              <li key={s.order} className="rounded-lg border border-line bg-panel p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">
                    Shot {s.order} · {s.shot_type}
                  </p>
                  <Badge tone="neutral">{secs(s.seconds)}</Badge>
                </div>
                <dl className="mt-1.5 grid gap-1 text-xs text-muted sm:grid-cols-2">
                  <div>
                    <dt className="inline font-medium text-fg">Framing: </dt>
                    <dd className="inline">{s.framing}</dd>
                  </div>
                  <div>
                    <dt className="inline font-medium text-fg">Where: </dt>
                    <dd className="inline">{s.location}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="inline font-medium text-fg">Action: </dt>
                    <dd className="inline">{s.action}</dd>
                  </div>
                  <div className="sm:col-span-2">
                    <dt className="inline font-medium text-fg">Delivery: </dt>
                    <dd className="inline">{s.delivery_tone}</dd>
                  </div>
                  {s.b_roll?.length > 0 && (
                    <div className="sm:col-span-2">
                      <dt className="inline font-medium text-fg">B-roll: </dt>
                      <dd className="inline">{s.b_roll.join(" · ")}</dd>
                    </div>
                  )}
                </dl>
              </li>
            ))}
          </ol>
        </Block>

        <Block title="Caption, hashtags and pinned comment" section="caption" text={asText(p, "caption")} onRegenerate={onRegenerate} busy={redoing === "caption"}>
          <p className="whitespace-pre-line rounded-lg border border-line bg-panel p-3 text-sm leading-relaxed">{p.caption}</p>
          <p className="mt-2 flex flex-wrap gap-1.5">
            {p.hashtags.map((h) => (
              <Badge key={h} tone="blue">
                {h}
              </Badge>
            ))}
          </p>
          <p className="mt-2 text-xs text-muted">
            <span className="font-medium text-fg">Pinned comment:</span> {p.pinned_comment}
          </p>
        </Block>

        <Block title="Call to action" section="cta" text={asText(p, "cta")} onRegenerate={onRegenerate} busy={redoing === "cta"}>
          <p className="text-sm">
            <span className="font-medium">Primary:</span> {p.cta_primary}
          </p>
          <p className="mt-1 text-sm text-muted">
            <span className="font-medium text-fg">Alternative:</span> {p.cta_alternative}
          </p>
        </Block>

        <Block title="Audio, timing and the test" text={`Audio: ${p.audio_direction}\nPost at: ${p.best_posting_time}\nA/B test: ${p.ab_test_idea}`}>
          <dl className="grid gap-2 text-sm">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Audio / music</dt>
              <dd>{p.audio_direction}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">Best time to post</dt>
              <dd>{p.best_posting_time}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted">A/B test idea</dt>
              <dd>{p.ab_test_idea}</dd>
            </div>
          </dl>
        </Block>
      </div>
    </Panel>
  );
}
