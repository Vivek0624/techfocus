"use client";
import * as React from "react";
import { Bookmark, Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { errorMessage, v2, type SaveIn } from "@/lib/api";
import { copyText, verdictLabel, verdictTone } from "@/lib/creator";
import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button, type ButtonProps } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/form";

/** Page title: one line, plain words. */
export function Title({ children, sub, actions }: { children: React.ReactNode; sub?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{children}</h1>
        {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
      </div>
      {actions}
    </div>
  );
}

export function CopyButton({ text, label = "Copy", className, size = "sm", variant = "outline" }: { text: string; label?: string } & Pick<ButtonProps, "className" | "size" | "variant">) {
  const [done, setDone] = React.useState(false);
  return (
    <Button
      size={size}
      variant={variant}
      className={className}
      aria-label={label}
      onClick={async () => {
        const ok = await copyText(text);
        if (ok) {
          setDone(true);
          toast.success("Copied. Paste it into Instagram.");
          setTimeout(() => setDone(false), 1500);
        } else toast.error("Couldn't copy. Select the text and copy it by hand.");
      }}
    >
      {done ? <Check /> : <Copy />}
      {done ? "Copied" : label}
    </Button>
  );
}

export function Chip({ active, onClick, children, className }: { active?: boolean; onClick?: () => void; children: React.ReactNode; className?: string }) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "h-8 rounded-full border px-3 text-xs font-medium transition-colors",
        active ? "border-accent bg-accent/20 text-fg" : "border-line text-muted hover:text-fg",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-lg border border-line bg-panel p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cn("h-8 rounded-md px-3 text-sm", value === o.value ? "bg-panel-2 text-fg shadow" : "text-muted hover:text-fg")}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Verdict({ verdict, score }: { verdict: string | null | undefined; score?: number | null }) {
  return (
    <Badge tone={verdictTone(verdict)} data-testid="verdict">
      {verdictLabel(verdict)}
      {score !== undefined && score !== null ? ` · ${score}` : ""}
    </Badge>
  );
}

export function Bar({ value, max = 100, dim, className }: { value: number; max?: number; dim?: boolean; className?: string }) {
  const pct = Math.max(2, Math.min(100, max ? (value / max) * 100 : 0));
  return (
    <div className={cn("h-2 w-full rounded-full bg-panel-2", className)}>
      <div className={cn("h-2 rounded-full", dim ? "bg-muted/40" : "bg-accent")} style={{ width: `${pct}%` }} />
    </div>
  );
}

/** Light container: a section with generous spacing instead of heavy cards. */
export function Section({ title, sub, children, className, actions }: { title?: React.ReactNode; sub?: React.ReactNode; children: React.ReactNode; className?: string; actions?: React.ReactNode }) {
  return (
    <section className={cn("rounded-xl border border-line bg-panel p-5", className)}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h2 className="text-base font-semibold">{title}</h2>}
            {sub && <p className="mt-0.5 text-sm text-muted">{sub}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * "Save to idea": with an idea id it saves straight into it; without, it asks for a title first.
 */
export function SaveToIdea({ payload, ideaId, defaultTitle, onSaved, label = "Save to idea" }: { payload: SaveIn; ideaId?: number | null; defaultTitle?: string; onSaved?: (id: number | undefined) => void; label?: string }) {
  const [open, setOpen] = React.useState(false);
  const [title, setTitle] = React.useState(defaultTitle ?? "");
  const [busy, setBusy] = React.useState(false);

  const save = async (body: SaveIn) => {
    setBusy(true);
    try {
      const r = await v2.save(body);
      toast.success("Saved to your idea. Find it in Ideas.");
      setOpen(false);
      onSaved?.(typeof r?.id === "number" ? r.id : (body.idea_id ?? undefined));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        disabled={busy}
        onClick={() => {
          if (ideaId) save({ ...payload, idea_id: ideaId });
          else {
            setTitle(defaultTitle ?? "");
            setOpen(true);
          }
        }}
      >
        <Bookmark /> {label}
      </Button>
      <Dialog
        open={open}
        onOpenChange={setOpen}
        title="Save as a new idea"
        description="Give it a short name so you can find it later."
        footer={
          <>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button disabled={busy || !title.trim()} onClick={() => save({ ...payload, title: title.trim() })}>
              {busy ? "Saving…" : "Save idea"}
            </Button>
          </>
        }
      >
        <Field label="Idea title" htmlFor="save-title">
          <Input id="save-title" value={title} onChange={(e) => setTitle(e.target.value)} autoFocus />
        </Field>
      </Dialog>
    </>
  );
}
