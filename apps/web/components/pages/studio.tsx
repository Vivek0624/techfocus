"use client";
import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Library, Sparkles } from "lucide-react";
import { api, errorMessage, type ContentIdeaFields } from "@/lib/api";
import { useRunPoller } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { ErrorState } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { RunStatusLine } from "./agents";

const schema = z.object({
  topic: z.string().trim().min(2, "Enter a topic"),
  audience_segment: z.string().trim(),
  format: z.enum(["talking_head", "motion_graphics", "mixed"]),
  options: z.coerce.number().int().min(1).max(3),
});
type FormIn = z.input<typeof schema>;
type FormOut = z.output<typeof schema>;

export interface TimelineScene {
  t_start: number;
  t_end: number;
  visual?: string;
  voiceover?: string;
  on_screen_text?: string;
}

export interface ReelOption {
  title?: string;
  audience_segment?: string;
  audience_problem?: string;
  format?: string;
  hook_options?: string[];
  recommended_hook?: string;
  hook_reasoning?: string;
  script?: string;
  timeline?: TimelineScene[];
  on_screen_text?: string[];
  visual_direction?: string;
  sound_direction?: string;
  caption?: string;
  keywords?: string[];
  hashtags?: string[];
  cta?: string;
  hypothesis?: string;
  success_metrics?: string[];
  follow_up_experiment?: string;
  duration_seconds?: number;
}

const FORMATS = ["talking_head", "motion_graphics", "carousel", "mixed"];

export function optionToContent(o: ReelOption, topic: string): Partial<ContentIdeaFields> & { title: string } {
  return {
    title: o.title || topic,
    audience_segment: o.audience_segment?.slice(0, 80) ?? null,
    audience_problem: o.audience_problem ?? null,
    format: (FORMATS.includes(o.format ?? "") ? o.format : null) as ContentIdeaFields["format"],
    hook_options: o.hook_options ?? [],
    recommended_hook: o.recommended_hook ?? null,
    script: o.script ?? null,
    storyboard: (o.timeline ?? []) as unknown as Record<string, unknown>[],
    on_screen_text: o.on_screen_text ?? [],
    visual_direction: [o.visual_direction, o.sound_direction ? `Sound: ${o.sound_direction}` : null].filter(Boolean).join("\n") || null,
    duration_seconds: o.duration_seconds && o.duration_seconds >= 3 && o.duration_seconds <= 900 ? Math.round(o.duration_seconds) : null,
    caption: o.caption ? o.caption.slice(0, 2200) : null,
    keywords: o.keywords ?? [],
    hashtags: o.hashtags ?? [],
    cta: o.cta ?? null,
    hypothesis: o.hypothesis ?? null,
    status: "idea",
    package: o as unknown as Record<string, unknown>,
  };
}

export function StudioPage() {
  const poller = useRunPoller((r) => {
    if (r.status === "failed") toast.error(`Reel Creative failed: ${r.error ?? "unknown error"}`);
    else if (r.status === "succeeded") toast.success("Reel package ready");
  });
  const [lastTopic, setLastTopic] = React.useState("");
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormIn, unknown, FormOut>({
    resolver: zodResolver(schema),
    defaultValues: { topic: "", audience_segment: "", format: "talking_head", options: 3 },
  });

  const onSubmit = (v: FormOut) => {
    setLastTopic(v.topic);
    poller.start("reel_creative", { topic: v.topic, audience_segment: v.audience_segment || undefined, format: v.format, options: v.options });
  };

  const run = poller.run;
  const output = (run?.status === "succeeded" ? run.output : null) as { options?: ReelOption[]; generated_by?: string } | null;

  return (
    <div>
      <PageHeader title="Reel Studio" description="Generate complete reel packages with the Reel Creative agent." />
      <Card>
        <CardBody>
          <form onSubmit={handleSubmit(onSubmit)} className="grid gap-4 md:grid-cols-[2fr_1.5fr_1fr_0.7fr_auto] md:items-end" noValidate>
            <Field label="Topic *" htmlFor="topic" error={errors.topic?.message}>
              <Input id="topic" placeholder="e.g. How UPI handles festival traffic" {...register("topic")} />
            </Field>
            <Field label="Audience segment" htmlFor="audience_segment">
              <Input id="audience_segment" placeholder="e.g. Beginner developers" {...register("audience_segment")} />
            </Field>
            <Field label="Format" htmlFor="format">
              <Select id="format" {...register("format")}>
                <option value="talking_head">talking_head</option>
                <option value="motion_graphics">motion_graphics</option>
                <option value="mixed">mixed</option>
              </Select>
            </Field>
            <Field label="Options" htmlFor="options">
              <Select id="options" {...register("options")}>
                <option value={1}>1</option>
                <option value={2}>2</option>
                <option value={3}>3</option>
              </Select>
            </Field>
            <Button type="submit" disabled={poller.active}>
              <Sparkles /> {poller.active ? "Generating…" : "Generate"}
            </Button>
          </form>
          {run && (
            <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
              <RunStatusLine status={poller.status} run={run} />
              {poller.active && poller.status !== "cancelling" && (
                <Button size="sm" variant="outline" onClick={poller.cancel}>
                  Cancel
                </Button>
              )}
              {run.status === "failed" || run.status === "cancelled" ? (
                <Button size="sm" variant="outline" onClick={poller.retry}>
                  Retry
                </Button>
              ) : null}
            </div>
          )}
        </CardBody>
      </Card>

      {poller.error && <ErrorState message={poller.error} />}
      {run?.status === "failed" && <ErrorState message={run.error ?? "The agent run failed."} />}

      {output?.generated_by && (
        <p className="mt-4 rounded-md border border-line bg-panel px-3 py-2 text-xs text-muted">
          Note: generated by {output.generated_by}
        </p>
      )}
      <div className="mt-6 flex flex-col gap-6">
        {output?.options?.map((o, i) => <OptionCard key={i} o={o} index={i} topic={lastTopic} />)}
        {output && !output.options?.length && <ErrorState message="The agent returned no options." />}
      </div>
    </div>
  );
}

function List({ items }: { items?: string[] }) {
  if (!items?.length) return <span className="text-muted">—</span>;
  return (
    <ul className="list-disc pl-5">
      {items.map((x, i) => (
        <li key={i}>{x}</li>
      ))}
    </ul>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-muted">{label}</h3>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function OptionCard({ o, index, topic }: { o: ReelOption; index: number; topic: string }) {
  const [saving, setSaving] = React.useState(false);
  const [savedId, setSavedId] = React.useState<number | null>(null);
  const save = async () => {
    setSaving(true);
    try {
      const c = await api.contentCreate(optionToContent(o, topic));
      setSavedId(c.id);
      toast.success(`Saved "${c.title}" to the idea library`);
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setSaving(false);
    }
  };
  return (
    <Card>
      <CardHeader
        title={`Option ${index + 1}: ${o.title ?? "Untitled"}`}
        description={[o.format, o.duration_seconds ? `${o.duration_seconds}s` : null].filter(Boolean).join(" · ")}
        actions={
          <Button size="sm" onClick={save} disabled={saving || savedId !== null}>
            <Library /> {savedId ? "Saved" : saving ? "Saving…" : "Save to library"}
          </Button>
        }
      />
      <CardBody className="flex flex-col gap-5">
        <div className="grid gap-4 md:grid-cols-2">
          <Section label="Audience">{o.audience_segment ?? "—"}</Section>
          <Section label="Problem">{o.audience_problem ?? "—"}</Section>
        </div>
        <Section label="Hooks">
          <div className="grid gap-3 md:grid-cols-3">
            {(o.hook_options ?? []).map((h, i) => {
              const rec = h === o.recommended_hook;
              return (
                <div key={i} className={cn("rounded-md border p-3", rec ? "border-accent bg-accent/10" : "border-line bg-bg/40")} data-recommended={rec}>
                  <div className="mb-1 flex items-center gap-2 text-xs text-muted">
                    Hook {i + 1} {rec && <Badge tone="blue">Recommended</Badge>}
                  </div>
                  <p>{h}</p>
                </div>
              );
            })}
          </div>
          {o.hook_reasoning && <p className="mt-2 text-xs text-muted">Why: {o.hook_reasoning}</p>}
        </Section>
        <Section label="Script">
          <p className="whitespace-pre-wrap">{o.script ?? "—"}</p>
        </Section>
        <Section label="Scene timeline">
          {o.timeline?.length ? (
            <Table>
              <thead>
                <tr>
                  <Th>Time</Th>
                  <Th>Visual</Th>
                  <Th>Voiceover</Th>
                  <Th>On-screen</Th>
                </tr>
              </thead>
              <tbody>
                {o.timeline.map((s, i) => (
                  <tr key={i}>
                    <Td className="whitespace-nowrap tabular-nums">
                      {s.t_start}s–{s.t_end}s
                    </Td>
                    <Td>{s.visual ?? "—"}</Td>
                    <Td>{s.voiceover ?? "—"}</Td>
                    <Td>{s.on_screen_text ?? "—"}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          ) : (
            "—"
          )}
        </Section>
        <div className="grid gap-4 md:grid-cols-2">
          <Section label="On-screen text"><List items={o.on_screen_text} /></Section>
          <div className="flex flex-col gap-4">
            <Section label="Visual direction">{o.visual_direction ?? "—"}</Section>
            <Section label="Sound direction">{o.sound_direction ?? "—"}</Section>
          </div>
        </div>
        <Section label={`Caption (${o.caption?.length ?? 0}/2200)`}>
          <p className="whitespace-pre-wrap rounded-md border border-line bg-bg/40 p-3">{o.caption ?? "—"}</p>
        </Section>
        <div className="grid gap-4 md:grid-cols-3">
          <Section label="Keywords">{o.keywords?.join(", ") || "—"}</Section>
          <Section label="Hashtags">{o.hashtags?.join(" ") || "—"}</Section>
          <Section label="CTA">{o.cta ?? "—"}</Section>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          <Section label="Hypothesis">{o.hypothesis ?? "—"}</Section>
          <Section label="Success metrics"><List items={o.success_metrics} /></Section>
          <Section label="Follow-up experiment">{o.follow_up_experiment ?? "—"}</Section>
        </div>
      </CardBody>
    </Card>
  );
}

