"use client";
import * as React from "react";
import { Badge, type BadgeTone } from "./ui/badge";
import { Tooltip } from "./ui/tooltip";
import { cn, fmtDateTime, fmtNum } from "@/lib/utils";

const SOURCE_LABEL: Record<string, { label: string; tone: BadgeTone }> = {
  instagram_api: { label: "instagram_api", tone: "blue" },
  manual: { label: "manual", tone: "violet" },
  calculated: { label: "calculated", tone: "neutral" },
  demo: { label: "DEMO", tone: "amber" },
};

export function SourceBadge({ source }: { source: string | null | undefined }) {
  const s = SOURCE_LABEL[source ?? ""] ?? { label: source || "unknown", tone: "neutral" as BadgeTone };
  return (
    <Badge tone={s.tone} title={`Source: ${s.label}`} data-testid="source-badge">
      {s.label}
    </Badge>
  );
}

export function Unavailable({ reason }: { reason?: string }) {
  return (
    <Tooltip content={reason ?? "Instagram returned no value for this metric (not zero). It may be below a threshold, still processing, or not granted."}>
      <span tabIndex={0} className="cursor-help text-muted underline decoration-dotted underline-offset-4">
        unavailable
      </span>
    </Tooltip>
  );
}

/** Render a nullable number; null => "unavailable" (never 0). */
export function NumOrNA({ value, digits = 0, suffix = "" }: { value: number | null | undefined; digits?: number; suffix?: string }) {
  const f = fmtNum(value, digits);
  if (f === null) return <Unavailable />;
  return (
    <>
      {f}
      {suffix}
    </>
  );
}

export function Metric({
  label,
  value,
  source,
  refreshed,
  digits = 0,
  suffix = "",
  hint,
  className,
}: {
  label: string;
  value: number | null | undefined;
  source: string | null | undefined;
  refreshed?: string | null;
  digits?: number;
  suffix?: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col gap-1 rounded-md border border-line bg-bg/40 p-3", className)} data-testid={`metric-${label}`}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs text-muted" title={hint}>
          {label}
        </span>
        <SourceBadge source={source} />
      </div>
      <div className="text-xl font-semibold tabular-nums text-fg">
        <NumOrNA value={value} digits={digits} suffix={suffix} />
      </div>
      <div className="text-[11px] text-muted">Refreshed {refreshed ? fmtDateTime(refreshed) : "never"}</div>
    </div>
  );
}
