import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium leading-none whitespace-nowrap", {
  variants: {
    tone: {
      neutral: "bg-panel-2 text-muted border border-line",
      blue: "bg-blue-500/15 text-blue-700 dark:text-blue-300",
      violet: "bg-violet-500/15 text-violet-700 dark:text-violet-300",
      green: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
      amber: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
      red: "bg-red-500/15 text-red-700 dark:text-red-300",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export type BadgeTone = NonNullable<VariantProps<typeof badge>["tone"]>;

export function Badge({ className, tone, ...p }: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) {
  return <span className={cn(badge({ tone }), className)} {...p} />;
}

export function statusTone(s: string | null | undefined): BadgeTone {
  switch (s) {
    case "succeeded":
    case "approved":
    case "published":
    case "complete":
    case "verified":
    case "ok":
    case "executed":
      return "green";
    case "failed":
    case "rejected":
    case "error":
      return "red";
    case "running":
    case "queued":
    case "scheduled":
    case "inferred":
      return "blue";
    case "cancelling":
    case "pending":
    case "hypothesis":
    case "insufficient_data":
      return "amber";
    default:
      return "neutral";
  }
}

export function StatusBadge({ status }: { status: string | null | undefined }) {
  return <Badge tone={statusTone(status)}>{status ?? "—"}</Badge>;
}
