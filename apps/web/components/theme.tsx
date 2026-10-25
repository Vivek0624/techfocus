"use client";
import * as React from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { cn } from "@/lib/utils";

export type ThemePref = "system" | "light" | "dark";
export const THEME_KEY = "tf-theme";

/** Inline, pre-hydration script so the page never flashes the wrong theme. */
export const THEME_SCRIPT = `(function(){try{var p=localStorage.getItem("${THEME_KEY}")||"system";var d=p==="dark"||(p==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);var r=document.documentElement;r.classList.toggle("dark",d);r.dataset.theme=d?"dark":"light";}catch(e){}})();`;

function systemDark() {
  return typeof window !== "undefined" && !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;
}

export function applyTheme(pref: ThemePref) {
  const dark = pref === "dark" || (pref === "system" && systemDark());
  const r = document.documentElement;
  r.classList.toggle("dark", dark);
  r.dataset.theme = dark ? "dark" : "light";
}

function readPref(): ThemePref {
  try {
    const v = localStorage.getItem(THEME_KEY);
    return v === "light" || v === "dark" ? v : "system";
  } catch {
    return "system";
  }
}

export function ThemeToggle({ className }: { className?: string }) {
  const [pref, setPref] = React.useState<ThemePref>("system");
  React.useEffect(() => {
    const p = readPref();
    // eslint-disable-next-line react-hooks/set-state-in-effect -- sync with localStorage after mount
    setPref(p);
    applyTheme(p);
    const mq = window.matchMedia?.("(prefers-color-scheme: dark)");
    const h = () => readPref() === "system" && applyTheme("system");
    mq?.addEventListener?.("change", h);
    return () => mq?.removeEventListener?.("change", h);
  }, []);
  const choose = (p: ThemePref) => {
    setPref(p);
    try {
      if (p === "system") localStorage.removeItem(THEME_KEY);
      else localStorage.setItem(THEME_KEY, p);
    } catch {
      /* private mode */
    }
    applyTheme(p);
  };
  const opts: [ThemePref, string, React.ComponentType<{ className?: string }>][] = [
    ["system", "System", Monitor],
    ["light", "Light", Sun],
    ["dark", "Dark", Moon],
  ];
  return (
    <div role="radiogroup" aria-label="Appearance" className={cn("inline-flex rounded-lg border border-line p-0.5", className)}>
      {opts.map(([v, l, Icon]) => (
        <button key={v} type="button" role="radio" aria-checked={pref === v} onClick={() => choose(v)} className={cn("flex h-8 items-center gap-1.5 rounded-md px-3 text-sm", pref === v ? "bg-panel-2 text-fg" : "text-muted hover:text-fg")}>
          <Icon className="size-4" /> {l}
        </button>
      ))}
    </div>
  );
}
