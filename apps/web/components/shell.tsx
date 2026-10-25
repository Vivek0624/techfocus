"use client";
import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { BarChart3, Home, Lightbulb, Menu, PlusSquare, UserCircle } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Home", icon: Home },
  { href: "/ideas", label: "Ideas", icon: Lightbulb },
  { href: "/create", label: "Create", icon: PlusSquare },
  { href: "/insights", label: "Insights", icon: BarChart3 },
  { href: "/connect", label: "Profile", icon: UserCircle },
];
export const SETTINGS_NAV = { href: "/settings", label: "Settings", icon: Menu };

/** Fired after a sync / import / data change so pages can reload. */
export const DATA_CHANGED = "growth:data-changed";
export function useDataChanged(cb: () => void) {
  const ref = React.useRef(cb);
  React.useEffect(() => {
    ref.current = cb;
  });
  React.useEffect(() => {
    const h = () => ref.current();
    window.addEventListener(DATA_CHANGED, h);
    return () => window.removeEventListener(DATA_CHANGED, h);
  }, []);
}

export function DemoBanner() {
  return (
    <div role="status" data-testid="demo-banner" className="shrink-0 border-b border-line bg-panel-2/60 px-4 py-1 text-xs text-muted">
      <span className="truncate">
        You&apos;re looking at sample data. <Link href="/connect" className="font-semibold text-accent">Connect Instagram or add your numbers</Link> to see your own account.
      </span>
    </div>
  );
}

function useActive() {
  const path = usePathname() ?? "/";
  return (href: string) => (href === "/" ? path === "/" : path.startsWith(href));
}

export function Brand({ className }: { className?: string }) {
  return <span className={cn("ig-gradient-text text-xl font-semibold tracking-tight", className)}>TechFocus</span>;
}

function RailItem({ href, label, icon: Icon, active }: (typeof NAV)[number] & { active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      className={cn("flex items-center gap-3.5 rounded-xl px-3 py-2.5 text-[15px] hover:bg-panel-2", active ? "bg-panel-2 font-semibold text-fg" : "text-fg")}
    >
      <Icon className={cn("size-6 shrink-0", active ? "stroke-[2.5]" : "stroke-[1.75]")} />
      <span className="hidden xl:inline">{label}</span>
    </Link>
  );
}

function Rail() {
  const isActive = useActive();
  return (
    <aside className="sticky top-0 hidden h-screen w-[72px] shrink-0 flex-col border-r border-line bg-panel px-3 py-6 md:flex xl:w-56">
      <Link href="/" className="mb-8 flex h-10 items-center px-3" aria-label="Home">
        <Brand className="hidden xl:inline" />
        <span className="ig-gradient flex size-7 items-center justify-center rounded-lg text-xs font-bold text-white xl:hidden">TF</span>
      </Link>
      <nav aria-label="Main" className="flex flex-1 flex-col gap-1">
        {NAV.map((n) => (
          <RailItem key={n.href} {...n} active={isActive(n.href)} />
        ))}
      </nav>
      <RailItem {...SETTINGS_NAV} active={isActive(SETTINGS_NAV.href)} />
    </aside>
  );
}

function TabBar() {
  const isActive = useActive();
  return (
    <nav aria-label="Tabs" className="fixed inset-x-0 bottom-0 z-30 grid h-12 grid-cols-5 border-t border-line bg-bg pb-[env(safe-area-inset-bottom)] md:hidden">
      {NAV.map(({ href, label, icon: Icon }) => {
        const active = isActive(href);
        return (
          <Link key={href} href={href} aria-label={label} aria-current={active ? "page" : undefined} className="flex items-center justify-center text-fg">
            <Icon className={cn("size-6", active ? "stroke-[2.5]" : "stroke-[1.5]")} />
          </Link>
        );
      })}
    </nav>
  );
}

export function Shell({ children }: { children: React.ReactNode }) {
  const [mode, setMode] = React.useState<string | null>(null);

  const loadMode = React.useCallback(() => {
    api
      .settings()
      .then((s) => setMode(s.data_mode))
      .catch(() => setMode(null));
  }, []);
  React.useEffect(loadMode, [loadMode]);
  useDataChanged(loadMode);

  return (
    <div className="flex min-h-screen bg-bg text-fg md:h-screen md:overflow-hidden">
      <Rail />
      <div className="flex min-w-0 flex-1 flex-col md:min-h-0">
        <header className="sticky top-0 z-30 flex h-12 items-center justify-between border-b border-line bg-bg px-4 md:hidden">
          <Brand />
          <Link href={SETTINGS_NAV.href} aria-label="Settings" className="text-fg">
            <Menu className="size-6" />
          </Link>
        </header>
        {mode === "demo" && <DemoBanner />}
        <main className="thin-scroll mx-auto w-full max-w-[1480px] flex-1 px-4 pb-20 pt-5 md:min-h-0 md:overflow-y-auto md:px-6 md:pb-5">{children}</main>
      </div>
      <TabBar />
    </div>
  );
}
