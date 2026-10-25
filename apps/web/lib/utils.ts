import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export const TZ = "Asia/Kolkata";

const HAS_TZ = /(Z|[+-]\d{2}:?\d{2})$/;

/** Backend audit timestamps are UTC; some come back naive, so naive => UTC. */
export function parseDate(s: string | null | undefined): Date | null {
  if (!s) return null;
  const d = new Date(/^\d{4}-\d{2}-\d{2}T/.test(s) && !HAS_TZ.test(s) ? `${s}Z` : s);
  return Number.isNaN(d.getTime()) ? null : d;
}

export function fmtDateTime(s: string | null | undefined, tz = TZ): string {
  const d = parseDate(s);
  if (!d) return "—";
  return d.toLocaleString("en-IN", { timeZone: tz, day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

export function fmtDate(s: string | null | undefined): string {
  const d = parseDate(s);
  if (!d) return "—";
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtNum(n: number | null | undefined, digits = 0): string | null {
  if (n === null || n === undefined || Number.isNaN(n)) return null;
  return n.toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
}

export function todayISO(tz = TZ): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: tz, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date());
}

export function splitList(s: string): string[] {
  return s
    .split(/\n|,/)
    .map((x) => x.trim())
    .filter(Boolean);
}

export function splitLines(s: string): string[] {
  return s
    .split("\n")
    .map((x) => x.trim())
    .filter(Boolean);
}

export function humanize(s: string | null | undefined): string {
  if (!s) return "—";
  return s.replace(/_/g, " ");
}

/**
 * Calendar slots (scheduled_at, planned_at) are IST wall-clock times. The API returns them
 * naive ("2026-10-23T19:00:00") or with +05:30. Normalise to the IST wall-clock "YYYY-MM-DDTHH:mm".
 */
export function istWall(s: string | null | undefined): string | null {
  if (!s) return null;
  if (!HAS_TZ.test(s)) return s.slice(0, 16);
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return null;
  const p = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(d);
  const g = (t: string) => p.find((x) => x.type === t)?.value ?? "00";
  return `${g("year")}-${g("month")}-${g("day")}T${g("hour")}:${g("minute")}`;
}

/** Display an IST wall-clock slot, e.g. "23 Oct, 19:00 IST". */
export function fmtSlot(s: string | null | undefined): string {
  const w = istWall(s);
  if (!w) return "—";
  const [date, time] = w.split("T");
  const [y, m, d] = date.split("-").map(Number);
  const month = new Date(Date.UTC(y, m - 1, d)).toLocaleString("en-IN", { month: "short", timeZone: "UTC" });
  return `${String(d).padStart(2, "0")} ${month}, ${time} IST`;
}

/** Date-only arithmetic on "YYYY-MM-DD" strings (timezone-free). */
export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + n));
  return dt.toISOString().slice(0, 10);
}
export function weekday(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).getUTCDay();
}
