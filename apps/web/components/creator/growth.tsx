"use client";
// Own-data growth features: shortlist, segments, fatigue, comment gaps, posting windows, shareability,
// brand voice and the full reel script. Every number comes from the API with its sample size.
import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { AlertTriangle, Clock, MessageCircleQuestion, Repeat2, Share2, Target, Wand2 } from "lucide-react";
import { AUDIENCE_LABEL, errorMessage, v4, type Audience, type ReelScript, type Shareability, type ShortlistItem, type Voice, type VoiceLint } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { catLabel, CONFIDENCE_LABEL } from "@/lib/creator";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Bar, CopyButton, Section } from "./kit";

export const AUDIENCES = Object.keys(AUDIENCE_LABEL);
export const audLabel = (a: string | null | undefined) => (a ? (AUDIENCE_LABEL[a] ?? a) : "—");

function Conf({ c }: { c: string | null | undefined }) {
  const k = c ?? "none";
  const tone = k === "high" ? "green" : k === "medium" ? "blue" : k === "low" ? "amber" : "neutral";
  return <Badge tone={tone}>{CONFIDENCE_LABEL[k] ?? k}</Badge>;
}

function shareTone(score: number) {
  return score >= 65 ? "green" : score >= 45 ? "amber" : "neutral";
}

// ---------- Today: shortlist ----------
export function Shortlist({ items, compact }: { items: ShortlistItem[]; compact?: boolean }) {
  if (!items.length) return null;
  return (
    <section data-testid="shortlist">
      {!compact && (
        <div className="mb-3 flex items-baseline justify-between gap-2">
          <h2 className="text-lg font-semibold">Today&apos;s shortlist</h2>
          <span className="text-xs text-muted">Ranked from your own posts. No follower predictions.</span>
        </div>
      )}
      <ol className="flex flex-col gap-3">
        {items.map((s, i) => (
          <li key={s.idea_id} className={cn("rounded-xl border border-line bg-panel", compact ? "p-3" : "p-4")}>
            <div className="flex items-start justify-between gap-3">
              <p className="font-semibold leading-snug">
                <span className="mr-2 text-muted">{i + 1}.</span>
                {s.title}
              </p>
              <Badge tone={shareTone(s.shareability.score)} title="Shareability estimate from the wording (not a prediction)">
                <Share2 className="size-3" /> {s.shareability.score}
              </Badge>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
              <Badge tone="violet">For: {s.audience.label}</Badge>
              {s.category && <Badge>{catLabel(s.category)}</Badge>}
              {s.status && <Badge>{s.status}</Badge>}
            </div>
            <ul className="mt-2 list-disc pl-5 text-sm text-muted">
              {s.why.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            {s.flags.map((f) => (
              <p key={f.kind} className="mt-2 flex items-start gap-1.5 text-xs text-amber-700 dark:text-amber-300">
                <AlertTriangle className="mt-0.5 size-3.5 shrink-0" /> {f.message}
              </p>
            ))}
            <p className="mt-2 flex items-center gap-1.5 text-xs">
              <Target className="size-3.5" /> Watch: {s.watch.text}
            </p>
            <Link href={`/create?idea=${s.idea_id}`} className="mt-2 inline-block text-xs font-semibold text-accent">
              Open in Create →
            </Link>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ---------- Insights ----------
export function SegmentsSection() {
  const q = useApi(() => v4.segments().catch(() => null), []);
  const d = q.data;
  if (!d || !d.segments.length) return null;
  const max = Math.max(0, ...d.segments.map((s) => s.shares_per_1k ?? 0));
  return (
    <Section title="Who your posts land with" sub={d.note}>
      {d.headline && <p className="mb-3 text-sm font-medium">{d.headline}</p>}
      <ul className="flex flex-col gap-3" data-testid="segments">
        {d.segments.map((s) => (
          <li key={s.segment} className={cn(s.n < 2 && "opacity-60")}>
            <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
              <span>{s.label}</span>
              <span className="tabular-nums text-xs text-muted">
                {s.shares_per_1k ?? "—"} shares · {s.saves_per_1k ?? "—"} saves · {s.views_per_1k_reach ?? "—"} views per 1K reached
              </span>
            </div>
            <Bar value={s.shares_per_1k ?? 0} max={max} dim={s.n < 2} className="mt-1" />
            <p className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
              based on {s.n} post{s.n === 1 ? "" : "s"}
              {s.inferred ? ` (${s.inferred} auto-tagged)` : ""} <Conf c={s.confidence === "too early" ? "none" : s.confidence} />
            </p>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function FatigueSection() {
  const q = useApi(() => v4.fatigue().catch(() => null), []);
  const d = q.data;
  if (!d) return null;
  const items = [...d.repetitive, ...d.declining];
  return (
    <section data-testid="fatigue">
      <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold">
        <Repeat2 className="size-5" /> Getting repetitive
      </h2>
      <p className="mb-3 text-sm text-muted">{d.note}</p>
      {d.ok ? (
        <p className="text-sm text-muted">Nothing repetitive right now. Your recent mix looks varied.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((it) => (
            <li key={`${it.dimension}-${it.group}-${it.headline}`} className="border-b border-line py-3">
              <div className="flex items-start justify-between gap-2">
                <p className="text-sm font-medium">{it.headline}</p>
                {it.confidence && <Conf c={it.confidence} />}
              </div>
              <p className="mt-1 text-sm">
                <span className="text-accent">Try:</span> {it.suggestion}
              </p>
            </li>
          ))}
          {d.near_duplicates.map((n) => (
            <li key={`dup-${n.post_id}-${n.similar_to.id}`} className="border-b border-line py-3 text-sm">
              “{n.title}” is very close to “{n.similar_to.text}”.
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

export function GapsSection() {
  const q = useApi(() => v4.gaps().catch(() => null), []);
  const [added, setAdded] = React.useState<Record<string, number>>({});
  const d = q.data;
  if (!d) return null;
  return (
    <section data-testid="gaps">
      <h2 className="mb-1 flex items-center gap-2 text-lg font-semibold">
        <MessageCircleQuestion className="size-5" /> Questions you haven&apos;t answered yet
      </h2>
      <p className="mb-3 text-sm text-muted">{d.note}</p>
      {d.gaps.length === 0 ? (
        <p className="text-sm text-muted">Every question in your comments is covered by a post or idea. Nice.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {d.gaps.slice(0, 6).map((g) => (
            <li key={g.theme} className="border-b border-line py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold">{g.theme}</p>
                <span className="text-xs text-muted">
                  {g.count} comment{g.count === 1 ? "" : "s"} · {g.likes} likes
                </span>
              </div>
              <ul className="mt-1 text-sm text-muted">
                {g.comments.slice(0, 2).map((c) => (
                  <li key={c.id}>
                    @{c.username}: {c.text}
                  </li>
                ))}
              </ul>
              <div className="mt-2">
                {added[g.theme] ? (
                  <Link href="/ideas" className="text-xs text-accent hover:underline">
                    Added. Open Ideas →
                  </Link>
                ) : (
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      try {
                        const r = await v4.gapToIdea(g.suggested_title, g.comments.map((c) => c.id));
                        setAdded({ ...added, [g.theme]: r.id });
                        toast.success("Added to Ideas");
                      } catch (e) {
                        toast.error(errorMessage(e));
                      }
                    }}
                  >
                    Add to ideas
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {d.covered.length > 0 && <p className="mt-2 text-xs text-muted">{d.covered.length} other question theme(s) are already covered by a post or idea.</p>}
    </section>
  );
}

export function ScheduleSection() {
  const q = useApi(() => v4.schedule().catch(() => null), []);
  const d = q.data;
  if (!d) return null;
  const max = Math.max(0, ...d.windows.map((w) => w.median_multiple));
  return (
    <Section title={<span className="flex items-center gap-2"><Clock className="size-4" /> When to post</span>} sub={d.note}>
      <p className="mb-3 text-sm font-medium" data-testid="schedule-rec">{d.recommendation}</p>
      <ul className="flex flex-col gap-3">
        {d.windows.map((w) => (
          <li key={w.label} className={cn(w.n < 2 && "opacity-60")}>
            <div className="flex justify-between text-sm">
              <span>{w.label}</span>
              <span className="tabular-nums">{w.median_multiple}x usual</span>
            </div>
            <Bar value={w.median_multiple} max={max} dim={w.n < 2} className="mt-1" />
            <p className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
              based on {w.n} post{w.n === 1 ? "" : "s"} <Conf c={w.confidence === "too early" ? "none" : w.confidence} />
            </p>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-xs text-muted">Scheduling and publishing still go through your approval in the calendar.</p>
    </Section>
  );
}

// ---------- Create ----------
export function ShareabilityCard({ text, category, format }: { text: string; category?: string | null; format?: string | null }) {
  const [r, setR] = React.useState<Shareability | null>(null);
  const [busy, setBusy] = React.useState(false);
  const run = async () => {
    if (!text.trim()) return;
    setBusy(true);
    try {
      setR(await v4.shareability({ text: text.trim(), category: category ?? null, format: format ?? null }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Section title="Shareability check" sub="Would people send this to a friend? An estimate from the wording, calibrated against your own shares when there's enough data.">
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 truncate text-sm text-muted">{text ? `“${text}”` : "Pick a hook or type a topic first."}</span>
        <Button size="sm" variant="secondary" onClick={run} disabled={busy || !text.trim()}>
          <Share2 /> {busy ? "Checking…" : "Check shareability"}
        </Button>
      </div>
      {r && (
        <div className="mt-4" data-testid="shareability">
          <div className="flex items-center gap-3">
            <span className="text-3xl font-semibold">{r.score}</span>
            <Badge tone={shareTone(r.score)}>{r.band}</Badge>
            {r.audience && <Badge tone="violet">For: {r.audience.label}</Badge>}
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(r.subscores).map(([k, s]) => (
              <div key={k}>
                <div className="flex justify-between text-xs">
                  <span>{s.label}</span>
                  <span className="text-muted">{s.score}</span>
                </div>
                <Bar value={s.score} className="mt-1" dim={s.score < 50} />
                <p className="mt-0.5 text-[11px] text-muted">{s.reasons.length ? s.reasons.join(", ") : "nothing yet"}</p>
              </div>
            ))}
          </div>
          {r.tip && <p className="mt-3 text-sm"><span className="text-accent">To improve:</span> {r.tip}</p>}
          {r.calibration?.groups.map((g) => (
            <p key={g.by} className="mt-2 flex items-center gap-2 text-sm">
              {g.text} <Conf c={g.confidence} />
            </p>
          ))}
          {!r.calibration && <p className="mt-2 text-xs text-muted">Not enough similar posts yet (need 3) to compare with your own shares.</p>}
          <p className="mt-2 text-xs text-muted">{r.note}</p>
        </div>
      )}
    </Section>
  );
}

export function VoiceCheck({ text }: { text: string }) {
  const [r, setR] = React.useState<VoiceLint | null>(null);
  const [busy, setBusy] = React.useState(false);
  return (
    <div className="rounded-lg border border-line p-3" data-testid="voice-check">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">Brand voice check</p>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || !text.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              setR(await v4.voiceCheck(text));
            } catch (e) {
              toast.error(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Checking…" : "Check voice"}
        </Button>
      </div>
      {r && (
        <div className="mt-2 text-sm">
          <p className={cn("font-medium", r.ok ? "text-emerald-700 dark:text-emerald-300" : "text-amber-700 dark:text-amber-300")}>
            {r.ok ? "Sounds like you" : "A few things to fix"} · {r.score}/100
          </p>
          <ul className="mt-1 flex list-disc flex-col gap-0.5 pl-5 text-muted">
            {r.issues.map((i) => (
              <li key={i.message} className={cn(i.severity === "high" && "text-red-700 dark:text-red-300")}>
                {i.message}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-muted">
            Edit your voice in <Link href="/settings" className="underline">Settings</Link>.
          </p>
        </div>
      )}
    </div>
  );
}

export function ReelScriptBlock({ topic, audience, hook, category }: { topic: string; audience: Audience; hook: string; category: string }) {
  const [duration, setDuration] = React.useState(30);
  const [r, setR] = React.useState<ReelScript | null>(null);
  const [busy, setBusy] = React.useState(false);
  const copy = r
    ? `${r.beats.map((b) => `[${b.start}-${b.end}s] ${b.label}\nSay: ${b.voiceover}\nOn screen: ${b.on_screen}\nVisual: ${b.visual}`).join("\n\n")}\n\nShots:\n${r.shot_list.map((s) => `- ${s}`).join("\n")}\n\nCaption:\n${r.caption}`
    : "";
  return (
    <Section title="Full Reel script" sub="Hook, timed beats, voiceover, on-screen text and b-roll notes. You shoot and edit it; nothing is rendered or posted." actions={r ? <CopyButton text={copy} /> : undefined}>
      <div className="flex flex-wrap items-end gap-2">
        <Field label="Length" htmlFor="rs-dur">
          <Select id="rs-dur" value={String(duration)} onChange={(e) => setDuration(Number(e.target.value))} className="w-28">
            {[15, 30, 45, 60].map((d) => (
              <option key={d} value={d}>
                {d}s
              </option>
            ))}
          </Select>
        </Field>
        <Button
          disabled={busy || !topic}
          onClick={async () => {
            setBusy(true);
            try {
              setR(await v4.reelScript({ topic, audience, hook: hook || null, duration, category }));
            } catch (e) {
              toast.error(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          <Wand2 /> {busy ? "Writing…" : r ? "Rewrite script" : "Write full script"}
        </Button>
      </div>
      {r && (
        <div className="mt-4 overflow-x-auto" data-testid="reel-script">
          <table className="w-full min-w-[640px] text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="py-1 pr-3 font-medium">Time</th>
                <th className="py-1 pr-3 font-medium">Voiceover</th>
                <th className="py-1 pr-3 font-medium">On screen</th>
                <th className="py-1 font-medium">Visual / b-roll</th>
              </tr>
            </thead>
            <tbody>
              {r.beats.map((b) => (
                <tr key={b.start} className="border-t border-line/60 align-top">
                  <td className="whitespace-nowrap py-2 pr-3 text-muted">
                    {b.start}-{b.end}s<span className="block text-[11px]">{b.label}</span>
                  </td>
                  <td className="py-2 pr-3">{b.voiceover}</td>
                  <td className="py-2 pr-3 text-xs font-medium uppercase text-muted">{b.on_screen}</td>
                  <td className="py-2 text-xs text-muted">{b.visual}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs font-medium uppercase tracking-wide text-muted">Shot list</p>
          <ul className="mt-1 list-disc pl-5 text-sm">
            {r.shot_list.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-muted">Written by: {r.source === "bedrock" ? "AI model" : "templates"}</p>
        </div>
      )}
    </Section>
  );
}

// ---------- Settings ----------
const csv = (a: string[]) => a.join(", ");
const list = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export function VoiceSettings() {
  const q = useApi(() => v4.voice().catch(() => null), []);
  if (!q.data) return null;
  return <VoiceForm v={q.data} />;
}

function VoiceForm({ v }: { v: Voice }) {
  const [f, setF] = React.useState({ tone: csv(v.tone_words), banned: csv(v.banned_words), cta: v.preferred_cta ?? "", tags: csv(v.signature_hashtags), emoji: v.emoji_level });
  const [busy, setBusy] = React.useState(false);
  const tags = list(f.tags);
  return (
    <Section title="Your voice" sub="Used by the brand voice check in Create. Signature hashtags: 3-5 at most.">
      <form
        className="grid gap-3 sm:grid-cols-2"
        onSubmit={async (e) => {
          e.preventDefault();
          if (tags.length > 5) return toast.error("Keep signature hashtags to 5 or fewer.");
          setBusy(true);
          try {
            await v4.saveVoice({ tone_words: list(f.tone), banned_words: list(f.banned), preferred_cta: f.cta.trim() || null, signature_hashtags: tags, emoji_level: f.emoji });
            toast.success("Voice saved");
          } catch (err) {
            toast.error(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Tone words" htmlFor="v-tone" hint="Comma separated">
          <Input id="v-tone" value={f.tone} onChange={(e) => setF({ ...f, tone: e.target.value })} />
        </Field>
        <Field label="Words you never use" htmlFor="v-banned" hint="Comma separated">
          <Input id="v-banned" value={f.banned} onChange={(e) => setF({ ...f, banned: e.target.value })} />
        </Field>
        <Field label="Preferred call to action" htmlFor="v-cta">
          <Input id="v-cta" value={f.cta} onChange={(e) => setF({ ...f, cta: e.target.value })} />
        </Field>
        <Field label="Signature hashtags" htmlFor="v-tags" hint={`${tags.length}/5`} error={tags.length > 5 ? "Max 5" : undefined}>
          <Input id="v-tags" value={f.tags} onChange={(e) => setF({ ...f, tags: e.target.value })} />
        </Field>
        <Field label="Emoji level" htmlFor="v-emoji">
          <Select id="v-emoji" value={f.emoji} onChange={(e) => setF({ ...f, emoji: e.target.value })}>
            {["none", "low", "medium", "high"].map((x) => (
              <option key={x} value={x}>
                {x}
              </option>
            ))}
          </Select>
        </Field>
        <div className="sm:col-span-2">
          <Button type="submit" disabled={busy}>
            Save voice
          </Button>
        </div>
      </form>
    </Section>
  );
}
