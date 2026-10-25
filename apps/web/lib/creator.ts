// Plain-language labels and small helpers for the creator screens.
import { TZ } from "./utils";

export const CATEGORIES = ["ai", "tech_concepts", "career", "skills", "relatable_learning"] as const;
export const CATEGORY_LABEL: Record<string, string> = {
  ai: "AI",
  tech_concepts: "Tech concepts",
  career: "Career",
  skills: "Skills",
  relatable_learning: "Relatable learning",
};
export const catLabel = (c: string | null | undefined) => (c ? (CATEGORY_LABEL[c] ?? c.replace(/_/g, " ")) : "No topic");

export const FORMATS = ["talking_head", "motion_graphics", "screen_recording", "carousel", "mixed"] as const;
export const FORMAT_LABEL: Record<string, string> = {
  talking_head: "Talking head",
  motion_graphics: "Motion graphics",
  screen_recording: "Screen recording",
  carousel: "Carousel",
  mixed: "Mixed",
};
export const fmtLabel = (f: string | null | undefined) => (f ? (FORMAT_LABEL[f] ?? f.replace(/_/g, " ")) : "—");

export const STAGES = ["idea", "script", "recording", "editing", "ready", "published"] as const;
export const STAGE_LABEL: Record<string, string> = {
  idea: "Idea",
  script: "Script",
  recording: "Recording",
  editing: "Editing",
  ready: "Ready",
  published: "Published",
  archived: "Archived",
};
export function nextStage(s: string | null | undefined): string | null {
  const i = STAGES.indexOf((s ?? "") as (typeof STAGES)[number]);
  return i >= 0 && i < STAGES.length - 1 ? STAGES[i + 1] : null;
}

export const CONFIDENCE_LABEL: Record<string, string> = { low: "early hunch", medium: "likely", high: "strong", none: "info" };

export function verdictTone(v: string | null | undefined): "green" | "amber" | "red" | "neutral" {
  const s = (v ?? "").toUpperCase();
  if (s === "STRONG") return "green";
  if (s === "OK") return "amber";
  if (s === "WEAK") return "red";
  return "neutral";
}
export const verdictLabel = (v: string | null | undefined) => {
  const s = (v ?? "").toUpperCase();
  return s === "STRONG" ? "Strong" : s === "OK" ? "OK" : s === "WEAK" ? "Weak" : v ?? "";
};

/** Compact Indian-style number: 1,39,248 → "1.4L", 20723 → "20.7K". */
export function big(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "unavailable";
  if (Math.abs(n) >= 100000) return `${(n / 100000).toFixed(1).replace(/\.0$/, "")}L`;
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}K`;
  return String(Math.round(n * 10) / 10);
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

/** Monday (YYYY-MM-DD) of the IST week containing `iso`. */
export function mondayOf(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  const dow = (dt.getUTCDay() + 6) % 7;
  dt.setUTCDate(dt.getUTCDate() - dow);
  return dt.toISOString().slice(0, 10);
}

export function dayName(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short", timeZone: "UTC" });
}

/** "in 5h" / "tomorrow 19:00" style relative label in IST. */
export function whenLabel(iso: string, now = new Date()): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const time = d.toLocaleTimeString("en-IN", { timeZone: TZ, hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const day = (x: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(x);
  const tomorrow = new Date(now.getTime() + 86400000);
  if (day(d) === day(now)) return `today ${time}`;
  if (day(d) === day(tomorrow)) return `tomorrow ${time}`;
  return `${d.toLocaleDateString("en-IN", { timeZone: TZ, weekday: "short", day: "numeric", month: "short" })} ${time}`;
}
