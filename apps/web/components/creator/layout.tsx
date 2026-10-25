"use client";
import * as React from "react";
import { cn } from "@/lib/utils";

/**
 * Desktop pages fit the window (no page scroll): a header row and a content area that fills the rest.
 * Long content scrolls inside its own Panel. Below 768px everything stacks and the page scrolls normally.
 */
export function Screen({ title, sub, actions, children, className }: { title: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <div className="flex flex-col gap-4 md:h-full md:min-h-0">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-[26px] font-semibold leading-tight tracking-tight">{title}</h1>
          {sub && <p className="mt-0.5 text-sm text-muted">{sub}</p>}
        </div>
        {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
      </header>
      <div className={cn("flex flex-col gap-4 md:min-h-0 md:flex-1", className)}>{children}</div>
    </div>
  );
}

/**
 * A card that says WHAT it is (title + one line) and WHAT TO DO (todo). Its body scrolls on its own.
 */
export function Panel({
  title,
  what,
  todo,
  actions,
  children,
  className,
  bodyClassName,
  testid,
  tone,
}: {
  title?: React.ReactNode;
  what?: React.ReactNode;
  todo?: React.ReactNode;
  actions?: React.ReactNode;
  children?: React.ReactNode;
  className?: string;
  bodyClassName?: string;
  testid?: string;
  tone?: "hero";
}) {
  return (
    <section
      data-testid={testid}
      className={cn(
        "flex flex-col overflow-hidden rounded-2xl border border-line bg-panel shadow-[0_1px_2px_rgba(0,0,0,0.04)] md:min-h-0",
        tone === "hero" && "border-transparent ring-1 ring-line",
        className,
      )}
    >
      {(title || actions) && (
        <div className="flex shrink-0 items-start justify-between gap-2 px-5 pb-2 pt-4">
          <div className="min-w-0">
            {title && <h2 className="text-[15px] font-semibold leading-snug">{title}</h2>}
            {what && <p className="mt-0.5 text-xs text-muted">{what}</p>}
            {todo && <p className="mt-1 text-xs font-medium text-accent">{todo}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </div>
      )}
      <div className={cn("thin-scroll px-5 pb-4 md:min-h-0 md:flex-1 md:overflow-y-auto", !title && !actions && "pt-4", bodyClassName)}>{children}</div>
    </section>
  );
}

/** Tabs that switch the content of one area (keeps pages short instead of long). */
export function Tabs<T extends string>({ value, onChange, items, label, className }: { value: T; onChange: (v: T) => void; items: [T, string][]; label: string; className?: string }) {
  return (
    <div role="tablist" aria-label={label} className={cn("inline-flex shrink-0 rounded-xl bg-panel-2 p-0.5", className)}>
      {items.map(([k, l]) => (
        <button
          key={k}
          role="tab"
          type="button"
          aria-selected={value === k}
          onClick={() => onChange(k)}
          className={cn("h-8 rounded-[10px] px-3.5 text-sm transition-colors", value === k ? "bg-panel font-semibold text-fg shadow-sm" : "text-muted hover:text-fg")}
        >
          {l}
        </button>
      ))}
    </div>
  );
}
