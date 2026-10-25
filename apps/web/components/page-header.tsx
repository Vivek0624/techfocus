import * as React from "react";

export function PageHeader({ title, description, actions }: { title: string; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold text-fg">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function JsonView({ value }: { value: unknown }) {
  return <pre className="max-h-96 overflow-auto rounded-md border border-line bg-bg p-3 text-xs leading-relaxed text-fg/90">{JSON.stringify(value, null, 2)}</pre>;
}
