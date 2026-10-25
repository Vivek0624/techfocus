"use client";
import * as React from "react";
import { v3, type AudienceData, type FollowerDay, type Share } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn, fmtNum } from "@/lib/utils";
import { ErrorState, Loading } from "@/components/ui/states";
import { Segmented } from "./kit";

const GENDER: Record<string, string> = { M: "Men", F: "Women", U: "Unknown" };

export function countryName(code: string): string {
  try {
    return new Intl.DisplayNames(["en"], { type: "region" }).of(code) ?? code;
  } catch {
    return code;
  }
}

export function hourLabel(h: number): string {
  const ap = h < 12 ? "AM" : "PM";
  return `${h % 12 === 0 ? 12 : h % 12} ${ap}`;
}

/** "Your followers peak around 7 PM — post at 6:30 PM." */
export function bestTimeHint(a: AudienceData | null | undefined): string | null {
  const b = a?.best_times?.[0];
  if (!b) return null;
  const h = (b.hour + 23) % 24;
  return `Your followers peak around ${b.label}. Post at ${h % 12 === 0 ? 12 : h % 12}:30 ${h < 12 ? "AM" : "PM"}.`;
}

function Bars({ rows, label }: { rows: Share[]; label: (s: string) => string }) {
  return (
    <ul className="flex flex-col gap-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="flex justify-between text-sm">
            <span>{label(r.label)}</span>
            <span className="tabular-nums">{r.share}%</span>
          </div>
          <div className="mt-1 h-1.5 rounded-full bg-panel-2">
            <div className="h-1.5 rounded-full bg-accent" style={{ width: `${Math.max(1, r.share)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function H({ children }: { children: React.ReactNode }) {
  return <h3 className="mb-3 text-base font-semibold">{children}</h3>;
}

export function AudienceTab() {
  const q = useApi(() => v3.audience(), []);
  const [loc, setLoc] = React.useState<"cities" | "countries">("cities");
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const a = q.data!;
  if (!a.available)
    return (
      <section data-testid="audience-tab" className="flex flex-col gap-2 text-sm">
        {a.recommendation && <p>{a.recommendation}</p>}
        {a.note && <p className="text-muted">{a.note}</p>}
      </section>
    );
  const maxH = Math.max(1, ...a.most_active_hours.map((h) => h.value));
  const best = new Set(a.best_times.map((b) => b.hour));
  return (
    <div data-testid="audience-tab" className="flex flex-col divide-y divide-line">
      <section className="pb-6">
        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-base font-semibold">Top locations</h3>
          <Segmented label="Locations" value={loc} onChange={setLoc} options={[{ value: "cities", label: "Cities" }, { value: "countries", label: "Countries" }]} />
        </div>
        <Bars rows={loc === "cities" ? a.cities : a.countries} label={loc === "cities" ? (s) => s : countryName} />
      </section>
      <section className="py-6">
        <H>Age range</H>
        <Bars rows={[...a.age].sort((x, y) => x.label.localeCompare(y.label))} label={(s) => s} />
      </section>
      <section className="py-6">
        <H>Gender</H>
        <div className="flex h-2.5 overflow-hidden rounded-full bg-panel-2" aria-hidden>
          {a.gender.map((g, i) => (
            <div key={g.label} className={i === 0 ? "bg-accent" : i === 1 ? "bg-[#d62976]" : "bg-muted/40"} style={{ width: `${g.share}%` }} />
          ))}
        </div>
        <ul className="mt-3 flex flex-wrap gap-5 text-sm">
          {a.gender.map((g) => (
            <li key={g.label}>
              {GENDER[g.label] ?? g.label} <b className="font-semibold">{g.share}%</b>
            </li>
          ))}
        </ul>
      </section>
      <section className="pt-6">
        <H>Most active times</H>
        <div className="flex h-28 items-end gap-0.5" data-testid="active-hours">
          {a.most_active_hours.map((h) => (
            <div key={h.hour} title={`${hourLabel(h.hour)}: ${h.value}`} className={cn("flex-1 rounded-t-sm", best.has(h.hour) ? "ig-gradient" : "bg-panel-2")} style={{ height: `${Math.max(3, (h.value / maxH) * 100)}%` }} />
          ))}
        </div>
        <div className="mt-1 flex justify-between text-[10px] text-muted">
          <span>12 AM</span>
          <span>6 AM</span>
          <span>12 PM</span>
          <span>6 PM</span>
          <span>11 PM</span>
        </div>
        {a.recommendation && <p className="mt-4 text-sm">{a.recommendation}</p>}
        {a.note && <p className="mt-1 text-xs text-muted">{a.note}</p>}
      </section>
    </div>
  );
}

export function FollowersSection({ history }: { history: FollowerDay[] }) {
  if (!history.length) return null;
  const follows = history.reduce((s, d) => s + (d.follows ?? 0), 0);
  const unfollows = history.reduce((s, d) => s + (d.unfollows ?? 0), 0);
  const withF = history.filter((d) => d.followers !== null);
  const net = withF.length > 1 ? (withF.at(-1)!.followers ?? 0) - (withF[0].followers ?? 0) : follows - unfollows;
  const maxBar = Math.max(1, ...history.map((d) => Math.max(d.follows ?? 0, d.unfollows ?? 0)));
  const fs = withF.map((d) => d.followers as number);
  const lo = Math.min(...fs);
  const hi = Math.max(...fs);
  const pts = fs.map((v, i) => `${(i / Math.max(1, fs.length - 1)) * 100},${hi === lo ? 50 : 100 - ((v - lo) / (hi - lo)) * 100}`).join(" ");
  return (
    <section data-testid="followers-section">
      <h2 className="mb-1 text-lg font-semibold">Followers</h2>
      <p className="mb-4 text-xs text-muted">Last {history.length} days</p>
      <dl className="grid grid-cols-3 gap-4">
        <div>
          <dt className="text-xs text-muted">Net growth</dt>
          <dd className="text-2xl font-semibold tabular-nums">{net > 0 ? "+" : ""}{fmtNum(net)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Follows</dt>
          <dd className="text-2xl font-semibold tabular-nums" data-testid="follows-total">{fmtNum(follows)}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted">Unfollows</dt>
          <dd className="text-2xl font-semibold tabular-nums" data-testid="unfollows-total">{fmtNum(unfollows)}</dd>
        </div>
      </dl>
      {fs.length > 1 && (
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" className="mt-4 h-20 w-full" aria-label="Followers over time">
          <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth="2" vectorEffect="non-scaling-stroke" />
        </svg>
      )}
      <div className="mt-3 flex h-16 items-end gap-px" aria-label="Follows vs unfollows per day">
        {history.map((d) => (
          <div key={d.date} className="flex flex-1 items-end gap-px" title={`${d.date}: ${d.follows ?? 0} follows, ${d.unfollows ?? 0} unfollows`}>
            <div className="flex-1 rounded-t-sm bg-accent" style={{ height: `${((d.follows ?? 0) / maxBar) * 100}%` }} />
            <div className="flex-1 rounded-t-sm bg-[#d62976]" style={{ height: `${((d.unfollows ?? 0) / maxBar) * 100}%` }} />
          </div>
        ))}
      </div>
      <div className="mt-2 flex gap-4 text-xs text-muted">
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-accent" />Follows</span>
        <span className="flex items-center gap-1.5"><span className="size-2 rounded-full bg-[#d62976]" />Unfollows</span>
      </div>
    </section>
  );
}
