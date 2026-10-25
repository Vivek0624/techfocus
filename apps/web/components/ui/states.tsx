import * as React from "react";
import { AlertTriangle, Inbox, Loader2 } from "lucide-react";
import { Button } from "./button";

export function Loading({ label = "Loading…" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 p-6 text-sm text-muted">
      <Loader2 className="size-4 animate-spin" /> {label}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: React.ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 p-8 text-center text-sm text-muted">
      <Inbox className="size-5" />
      <p className="font-medium text-fg">{title}</p>
      {children}
    </div>
  );
}

export function ErrorState({ message, onRetry, problems }: { message: string; onRetry?: () => void; problems?: string[] }) {
  return (
    <div role="alert" className="m-4 rounded-md border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-700 dark:text-red-200">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div className="flex-1">
          <p className="font-medium">Something went wrong</p>
          <p className="mt-1 text-red-700 dark:text-red-200/90">{message}</p>
          {problems && problems.length > 0 && (
            <ul className="mt-2 list-disc pl-5">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
        </div>
        {onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            Retry
          </Button>
        )}
      </div>
    </div>
  );
}
