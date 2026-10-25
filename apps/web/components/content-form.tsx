"use client";
import * as React from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CONTENT_FORMATS, CONTENT_STATUSES, EFFORTS, type ContentIdea, type ContentIdeaFields } from "@/lib/api";
import { istWall, splitLines, splitList } from "@/lib/utils";
import { Field, Input, Select, Textarea } from "./ui/form";
import { Button } from "./ui/button";
import { JsonView } from "./page-header";

const optStr = z.string().trim();

function isJsonArray(s: string) {
  if (!s.trim()) return true;
  try {
    const v = JSON.parse(s);
    return Array.isArray(v) && v.every((x) => x && typeof x === "object" && !Array.isArray(x));
  } catch {
    return false;
  }
}

export const contentSchema = z.object({
  title: z.string().trim().min(1, "Title is required").max(200, "Max 200 characters"),
  pillar: optStr.max(80, "Max 80 characters"),
  audience_segment: optStr.max(80, "Max 80 characters"),
  audience_problem: optStr,
  format: z.enum(["", ...CONTENT_FORMATS]),
  hook_options: optStr,
  recommended_hook: optStr,
  script: optStr,
  storyboard: z.string().refine(isJsonArray, "Storyboard must be a JSON array of objects"),
  on_screen_text: optStr,
  visual_direction: optStr,
  duration_seconds: z
    .string()
    .trim()
    .refine((v) => v === "" || (/^\d+$/.test(v) && +v >= 3 && +v <= 900), "Duration must be a whole number between 3 and 900"),
  caption: z.string().max(2200, "Caption must be 2200 characters or fewer"),
  keywords: optStr,
  hashtags: optStr,
  cta: optStr,
  effort: z.enum(["", ...EFFORTS]),
  evidence: z.string().refine((v) => splitLines(v).every((u) => /^https?:\/\/\S+$/i.test(u)), "Each evidence line must be an http(s) URL"),
  hypothesis: optStr,
  status: z.enum(CONTENT_STATUSES),
  planned_at: optStr,
  lessons: optStr,
});

export type ContentFormValues = z.infer<typeof contentSchema>;

export function toFormValues(c?: Partial<ContentIdea> | null): ContentFormValues {
  return {
    title: c?.title ?? "",
    pillar: c?.pillar ?? "",
    audience_segment: c?.audience_segment ?? "",
    audience_problem: c?.audience_problem ?? "",
    format: (c?.format as ContentFormValues["format"]) ?? "",
    hook_options: (c?.hook_options ?? []).join("\n"),
    recommended_hook: c?.recommended_hook ?? "",
    script: c?.script ?? "",
    storyboard: c?.storyboard?.length ? JSON.stringify(c.storyboard, null, 2) : "",
    on_screen_text: (c?.on_screen_text ?? []).join("\n"),
    visual_direction: c?.visual_direction ?? "",
    duration_seconds: c?.duration_seconds != null ? String(c.duration_seconds) : "",
    caption: c?.caption ?? "",
    keywords: (c?.keywords ?? []).join(", "),
    hashtags: (c?.hashtags ?? []).join(" "),
    cta: c?.cta ?? "",
    effort: (c?.effort as ContentFormValues["effort"]) ?? "",
    evidence: (c?.evidence ?? []).join("\n"),
    hypothesis: c?.hypothesis ?? "",
    status: (CONTENT_STATUSES as readonly string[]).includes(c?.status ?? "") ? (c!.status as ContentFormValues["status"]) : "idea",
    planned_at: istWall(c?.planned_at) ?? "",
    lessons: c?.lessons ?? "",
  };
}

const nul = (s: string) => (s.trim() ? s.trim() : null);

export function toPayload(v: ContentFormValues): Partial<ContentIdeaFields> & { title: string } {
  return {
    title: v.title.trim(),
    pillar: nul(v.pillar),
    audience_segment: nul(v.audience_segment),
    audience_problem: nul(v.audience_problem),
    format: v.format ? v.format : null,
    hook_options: splitLines(v.hook_options),
    recommended_hook: nul(v.recommended_hook),
    script: nul(v.script),
    storyboard: v.storyboard.trim() ? JSON.parse(v.storyboard) : [],
    on_screen_text: splitLines(v.on_screen_text),
    visual_direction: nul(v.visual_direction),
    duration_seconds: v.duration_seconds ? Number(v.duration_seconds) : null,
    caption: nul(v.caption),
    keywords: splitList(v.keywords),
    hashtags: v.hashtags.split(/[\s,]+/).map((h) => h.trim()).filter(Boolean),
    cta: nul(v.cta),
    effort: v.effort ? v.effort : null,
    evidence: splitLines(v.evidence),
    hypothesis: nul(v.hypothesis),
    status: v.status,
    planned_at: v.planned_at ? (v.planned_at.length === 16 ? `${v.planned_at}:00` : v.planned_at) : null,
    lessons: nul(v.lessons),
  };
}

export function ContentForm({
  initial,
  onSubmit,
  submitLabel = "Save",
  onCancel,
}: {
  initial?: ContentIdea | null;
  onSubmit: (payload: ReturnType<typeof toPayload>) => Promise<void> | void;
  submitLabel?: string;
  onCancel?: () => void;
}) {
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<ContentFormValues>({ resolver: zodResolver(contentSchema), defaultValues: toFormValues(initial) });
  const caption = useWatch({ control, name: "caption" }) ?? "";

  return (
    <form onSubmit={handleSubmit((v) => onSubmit(toPayload(v)))} className="flex flex-col gap-4" noValidate aria-label="Content idea form">
      <Field label="Title *" htmlFor="title" error={errors.title?.message}>
        <Input id="title" {...register("title")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Pillar" htmlFor="pillar" error={errors.pillar?.message}>
          <Input id="pillar" {...register("pillar")} />
        </Field>
        <Field label="Audience segment" htmlFor="audience_segment" error={errors.audience_segment?.message}>
          <Input id="audience_segment" {...register("audience_segment")} />
        </Field>
      </div>
      <Field label="Audience problem" htmlFor="audience_problem">
        <Textarea id="audience_problem" rows={2} {...register("audience_problem")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Format" htmlFor="format">
          <Select id="format" {...register("format")}>
            <option value="">—</option>
            {CONTENT_FORMATS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Duration (s)" htmlFor="duration_seconds" error={errors.duration_seconds?.message}>
          <Input id="duration_seconds" inputMode="numeric" {...register("duration_seconds")} />
        </Field>
        <Field label="Effort" htmlFor="effort">
          <Select id="effort" {...register("effort")}>
            <option value="">—</option>
            {EFFORTS.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Hook options (one per line)" htmlFor="hook_options">
        <Textarea id="hook_options" rows={3} {...register("hook_options")} />
      </Field>
      <Field label="Recommended hook" htmlFor="recommended_hook">
        <Input id="recommended_hook" {...register("recommended_hook")} />
      </Field>
      <Field label="Script" htmlFor="script">
        <Textarea id="script" rows={5} {...register("script")} />
      </Field>
      <Field label="Storyboard (JSON array of scenes)" htmlFor="storyboard" error={errors.storyboard?.message}>
        <Textarea id="storyboard" rows={4} className="font-mono text-xs" placeholder='[{"t_start":0,"t_end":3,"visual":"…","voiceover":"…","on_screen_text":"…"}]' {...register("storyboard")} />
      </Field>
      <Field label="On-screen text (one per line)" htmlFor="on_screen_text">
        <Textarea id="on_screen_text" rows={3} {...register("on_screen_text")} />
      </Field>
      <Field label="Visual direction" htmlFor="visual_direction">
        <Textarea id="visual_direction" rows={2} {...register("visual_direction")} />
      </Field>
      <Field
        label="Caption"
        htmlFor="caption"
        error={errors.caption?.message}
        hint={
          <span className={caption.length > 2200 ? "text-red-400" : ""} data-testid="caption-counter">
            {caption.length}/2200
          </span>
        }
      >
        <Textarea id="caption" rows={4} {...register("caption")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Keywords (comma separated)" htmlFor="keywords">
          <Input id="keywords" {...register("keywords")} />
        </Field>
        <Field label="Hashtags (space separated)" htmlFor="hashtags">
          <Input id="hashtags" {...register("hashtags")} />
        </Field>
      </div>
      <Field label="CTA" htmlFor="cta">
        <Input id="cta" {...register("cta")} />
      </Field>
      <Field label="Evidence URLs (one per line)" htmlFor="evidence" error={errors.evidence?.message}>
        <Textarea id="evidence" rows={2} {...register("evidence")} />
      </Field>
      <Field label="Hypothesis" htmlFor="hypothesis">
        <Textarea id="hypothesis" rows={2} {...register("hypothesis")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Status" htmlFor="status">
          <Select id="status" {...register("status")}>
            {CONTENT_STATUSES.map((f) => (
              <option key={f} value={f}>
                {f}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Planned time (IST)" htmlFor="planned_at">
          <Input id="planned_at" type="datetime-local" {...register("planned_at")} />
        </Field>
      </div>
      <Field label="Lessons" htmlFor="lessons">
        <Textarea id="lessons" rows={2} {...register("lessons")} />
      </Field>
      {initial && (
        <div>
          <p className="mb-1 text-xs font-medium text-muted">Performance (read-only)</p>
          <JsonView value={initial.performance ?? {}} />
        </div>
      )}
      <div className="flex justify-end gap-2 border-t border-line pt-4">
        {onCancel && (
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Saving…" : submitLabel}
        </Button>
      </div>
    </form>
  );
}
