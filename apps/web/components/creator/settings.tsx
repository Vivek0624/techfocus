"use client";
import * as React from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Ban, Check, Server } from "lucide-react";
import { api, errorMessage, v5, type Settings, type TargetProgress } from "@/lib/api";
import { GLOSSARY } from "@/lib/glossary";
import { useApi } from "@/lib/hooks";
import { todayISO } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { DATA_CHANGED } from "@/components/shell";
import { ThemeToggle } from "@/components/theme";
import { Section } from "./kit";
import { VoiceSettings } from "./growth";
import { ImportPanel } from "./interests";
import { Panel, Screen, Tabs } from "./layout";

const ADVANCED = [
  ["/analytics", "Growth analytics", "Charts and date ranges"],
  ["/studio", "Reel studio", "Agent-written full reel packages"],
  ["/calendar", "Content calendar", "Approvals and publishing queue"],
  ["/audience", "Audience", "Personas and questions"],
  ["/experiments", "Experiments", "A/B tests on hooks and formats"],
  ["/agents", "AI agents", "Run and inspect agents"],
  ["/aws", "AWS / Bedrock", "Model-written content setup"],
  ["/instagram", "Instagram (old page)", "Now lives in Connect"],
] as const;

type SetTab = "general" | "import" | "instagram" | "words" | "advanced";
const SET_TABS: [SetTab, string][] = [
  ["general", "General"],
  ["import", "Import my data"],
  ["instagram", "What Instagram allows"],
  ["words", "Words explained"],
  ["advanced", "Advanced"],
];

export function SettingsPageV2() {
  const params = useSearchParams();
  const initial = params?.get("tab") as SetTab | null;
  const [tab, setTab] = React.useState<SetTab>(initial && SET_TABS.some(([k]) => k === initial) ? initial : "general");
  const settings = useApi(() => api.settings(), []);
  const target = useApi(() => api.target(), []);
  return (
    <Screen title="Settings" actions={<Tabs label="Settings" value={tab} onChange={setTab} items={SET_TABS} />}>
      {tab === "general" && (
        <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-2">
          <div className="thin-scroll flex flex-col gap-4 md:min-h-0 md:overflow-y-auto [&>section]:rounded-2xl">
            <Section title="Appearance" sub="Follow your computer's setting, or pick one.">
              <ThemeToggle />
            </Section>
            {target.loading && !target.data && <Loading />}
            {target.error && <ErrorState message={target.error} onRetry={target.reload} />}
            {target.data && <Goal t={target.data} onSaved={target.reload} />}
            {settings.loading && !settings.data && <Loading />}
            {settings.error && <ErrorState message={settings.error} onRetry={settings.reload} />}
            {settings.data && <Brand s={settings.data} onSaved={settings.setData} />}
          </div>
          <div className="thin-scroll md:min-h-0 md:overflow-y-auto [&>section]:rounded-2xl">
            <VoiceSettings />
          </div>
        </div>
      )}
      {tab === "import" && <ImportPanel />}
      {tab === "instagram" && <Capabilities />}
      {tab === "words" && <Glossary />}
      {tab === "advanced" && (
        <Panel title="Advanced tools" what="Power-user pages. You don't need these to grow." className="md:flex-1">
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {ADVANCED.map(([href, label, sub]) => (
              <li key={href}>
                <Link href={href} className="block rounded-xl border border-line px-3 py-2 hover:border-accent">
                  <span>{label}</span>
                  <span className="block text-xs text-muted">{sub}</span>
                </Link>
              </li>
            ))}
          </ul>
        </Panel>
      )}
    </Screen>
  );
}

const CAP_GROUPS: [string, string, string][] = [
  ["used", "Used by this app", "Read-only unless you press a button. Nothing is ever posted on its own."],
  ["needs_server", "Possible, but needs a public server", "Instagram has to reach your computer over the internet (webhooks). This app runs only on your laptop."],
  ["not_possible", "Not possible with Instagram's API", "Instagram simply doesn't share these with any app."],
  ["not_used", "Possible, deliberately not used", "Left out on purpose."],
];

function Capabilities() {
  const q = useApi(() => v5.capabilities(), []);
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const caps = q.data ?? [];
  return (
    <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-2 md:grid-rows-2" data-testid="capabilities">
      {CAP_GROUPS.map(([k, title, what]) => {
        const items = caps.filter((c) => c.status === k);
        if (!items.length) return null;
        return (
          <Panel key={k} title={title} what={what} className={k === "used" ? "md:row-span-2" : undefined}>
            <ul className="flex flex-col gap-2.5">
              {items.map((c) => (
                <li key={c.what} className="text-sm">
                  <p className="flex items-center gap-1.5 font-medium">
                    {k === "used" ? <Check className="size-4 text-emerald-500" /> : k === "needs_server" ? <Server className="size-4 text-amber-500" /> : <Ban className="size-4 text-muted" />}
                    {c.what}
                  </p>
                  <p className="pl-5.5 text-xs text-muted">{c.plain}</p>
                  {c.why && <p className="pl-5.5 text-xs">{c.why}</p>}
                </li>
              ))}
            </ul>
          </Panel>
        );
      })}
    </div>
  );
}

function Glossary() {
  const [q, setQ] = React.useState("");
  const rows = Object.entries(GLOSSARY).filter(([, t]) => !q || `${t.label} ${t.ig ?? ""} ${t.short}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <Panel
      title="Words explained"
      what="Instagram's words in plain language. Look for the (i) next to any number in the app."
      className="md:flex-1"
      actions={<Input aria-label="Search words" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} className="h-8 w-48" />}
    >
      <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="glossary">
        {rows.map(([k, t]) => (
          <div key={k}>
            <dt className="text-sm font-semibold">
              {t.label}
              {t.ig && <span className="font-normal text-muted"> · Instagram: {t.ig}</span>}
            </dt>
            <dd className="text-xs text-muted">{t.short}</dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

function Goal({ t, onSaved }: { t: TargetProgress; onSaved: () => void }) {
  const [f, setF] = React.useState({
    target: String(t.config?.target ?? 10000),
    days: String(t.config?.days ?? 90),
    start_followers: String(t.config?.start_followers ?? t.current ?? 340),
    start_date: t.config?.start_date ?? todayISO(),
  });
  const [busy, setBusy] = React.useState(false);
  return (
    <Section title="Your goal" sub="How many followers, by when. We use it to tell you if you're on pace.">
      <form
        className="grid gap-3 sm:grid-cols-4"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api.setTarget({ target: Number(f.target), days: Number(f.days), start_followers: Number(f.start_followers), start_date: f.start_date });
            toast.success("Goal saved");
            onSaved();
          } catch (err) {
            toast.error(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Followers goal" htmlFor="g-target">
          <Input id="g-target" type="number" min={1} value={f.target} onChange={(e) => setF({ ...f, target: e.target.value })} />
        </Field>
        <Field label="In how many days" htmlFor="g-days">
          <Input id="g-days" type="number" min={1} max={365} value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} />
        </Field>
        <Field label="Followers at start" htmlFor="g-start">
          <Input id="g-start" type="number" min={0} value={f.start_followers} onChange={(e) => setF({ ...f, start_followers: e.target.value })} />
        </Field>
        <Field label="Start date" htmlFor="g-date">
          <Input id="g-date" type="date" value={f.start_date} onChange={(e) => setF({ ...f, start_date: e.target.value })} />
        </Field>
        <div className="sm:col-span-4">
          <Button type="submit" disabled={busy}>
            Save goal
          </Button>
        </div>
      </form>
    </Section>
  );
}

function Brand({ s, onSaved }: { s: Settings; onSaved: (s: Settings) => void }) {
  const [f, setF] = React.useState({ handle: s.brand.handle, posts: String(s.brand.posts_per_week), hours: String(s.brand.hours_per_week) });
  const [busy, setBusy] = React.useState(false);
  return (
    <Section title="You" sub="Used for your weekly target and time-aware suggestions.">
      <form
        className="grid gap-3 sm:grid-cols-3"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            onSaved(await api.updateSettings({ brand: { handle: f.handle.trim().replace(/^@/, ""), posts_per_week: Number(f.posts), hours_per_week: Number(f.hours) } }));
            toast.success("Saved");
            window.dispatchEvent(new Event(DATA_CHANGED));
          } catch (err) {
            toast.error(errorMessage(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label="Instagram handle" htmlFor="b-handle">
          <Input id="b-handle" value={f.handle} onChange={(e) => setF({ ...f, handle: e.target.value })} />
        </Field>
        <Field label="Posts per week" htmlFor="b-posts">
          <Input id="b-posts" type="number" min={0} max={50} value={f.posts} onChange={(e) => setF({ ...f, posts: e.target.value })} />
        </Field>
        <Field label="Hours per week for content" htmlFor="b-hours">
          <Input id="b-hours" type="number" min={0} max={100} value={f.hours} onChange={(e) => setF({ ...f, hours: e.target.value })} />
        </Field>
        <div className="sm:col-span-3">
          <Button type="submit" disabled={busy}>
            Save
          </Button>
        </div>
      </form>
    </Section>
  );
}
