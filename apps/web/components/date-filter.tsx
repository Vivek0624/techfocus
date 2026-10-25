"use client";
import * as React from "react";
import type { DateFilter as DF } from "@/lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/form";
import { cn } from "@/lib/utils";

export function DateFilter({ value, onChange }: { value: DF; onChange: (f: DF) => void }) {
  const custom = !value.days;
  const [start, setStart] = React.useState(value.start ?? "");
  const [end, setEnd] = React.useState(value.end ?? "");
  const [showCustom, setShowCustom] = React.useState(custom);
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Date range">
      {[7, 14, 30].map((d) => (
        <Button
          key={d}
          size="sm"
          variant={value.days === d && !showCustom ? "default" : "outline"}
          onClick={() => {
            setShowCustom(false);
            onChange({ days: d });
          }}
        >
          {d} days
        </Button>
      ))}
      <Button size="sm" variant={showCustom ? "default" : "outline"} onClick={() => setShowCustom(true)}>
        Custom
      </Button>
      {showCustom && (
        <form
          className={cn("flex flex-wrap items-center gap-2")}
          onSubmit={(e) => {
            e.preventDefault();
            if (start && end) onChange({ start, end });
          }}
        >
          <Input aria-label="Start date" type="date" value={start} onChange={(e) => setStart(e.target.value)} className="w-40" />
          <Input aria-label="End date" type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="w-40" />
          <Button size="sm" type="submit" disabled={!start || !end || start > end}>
            Apply
          </Button>
        </form>
      )}
    </div>
  );
}
