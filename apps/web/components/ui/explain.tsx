"use client";
import * as React from "react";
import { Info } from "lucide-react";
import { term } from "@/lib/glossary";
import { cn } from "@/lib/utils";
import { Tooltip } from "./tooltip";

/**
 * A plain-language label with a small (i). Hover or focus shows a one-line explanation; tapping toggles it
 * (touch screens don't hover).
 *   <Explain term="reach" />                 -> "People reached (i)"
 *   <Explain term="reach">Reached</Explain>  -> custom label, same explanation
 */
export function Explain({ term: key, children, className, iconOnly }: { term: string; children?: React.ReactNode; className?: string; iconOnly?: boolean }) {
  const t = term(key);
  const [open, setOpen] = React.useState(false);
  const body = (
    <span className="block max-w-64">
      <b className="font-semibold">{t.label}</b>
      {t.ig && <span className="text-muted"> (Instagram: {t.ig})</span>}
      <span className="mt-0.5 block">{t.short}</span>
    </span>
  );
  return (
    <span className={cn("inline-flex items-center gap-1", className)}>
      {!iconOnly && (children ?? t.label)}
      <Tooltip content={body} open={open || undefined} onOpenChange={(o) => !o && setOpen(false)}>
        <button
          type="button"
          aria-label={`What is ${t.label}?`}
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setOpen((o) => !o);
          }}
          className="inline-flex size-4 shrink-0 items-center justify-center rounded-full text-muted hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
        >
          <Info className="size-3.5" />
        </button>
      </Tooltip>
    </span>
  );
}
