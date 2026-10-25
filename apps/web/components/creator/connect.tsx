"use client";
import * as React from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { CheckCircle2, Circle, Download } from "lucide-react";
import { api, errorMessage, v2, type InstagramStatus, type PostIn } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { CATEGORIES, catLabel, FORMATS, fmtLabel } from "@/lib/creator";
import { cn, fmtDateTime, todayISO } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { DATA_CHANGED } from "@/components/shell";
import { Section, Segmented } from "./kit";
import { Screen } from "./layout";

export function ConnectPage() {
  const params = useSearchParams();
  const status = useApi(() => api.instagramStatus(), []);
  const justConnected = params?.get("connected") === "1";
  const err = params?.get("error");
  return (
    <Screen title="Profile" sub="Your Instagram connection and your numbers.">
      {justConnected && <div role="status" className="shrink-0 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-200">Instagram connected. Tap “Update now” to pull your posts.</div>}
      {err && <div role="alert" className="shrink-0 rounded-xl border border-red-500/30 bg-red-500/10 p-3 text-sm text-red-700 dark:text-red-200">Instagram said: {err}</div>}
      <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-2">
        <div className="thin-scroll md:min-h-0 md:overflow-y-auto [&>section]:rounded-2xl">
          {status.loading && !status.data && <Loading />}
          {status.error && <ErrorState message={status.error} onRetry={status.reload} />}
          {status.data && <Steps s={status.data} reload={status.reload} />}
        </div>
        <div className="thin-scroll md:min-h-0 md:overflow-y-auto [&>section]:rounded-2xl">
          <Manual />
        </div>
      </div>
    </Screen>
  );
}

function Step({ n, done, title, children, testid }: { n: number; done: boolean; title: string; children: React.ReactNode; testid: string }) {
  return (
    <li data-testid={testid} data-done={done} className="flex gap-4">
      <div className="flex flex-col items-center">
        {done ? <CheckCircle2 className="size-6 text-emerald-400" aria-label="done" /> : <Circle className="size-6 text-muted" aria-label="to do" />}
      </div>
      <div className="min-w-0 flex-1 pb-6">
        <p className={cn("font-medium", done && "text-muted")}>
          {n}. {title} <span className="ml-1 text-xs font-normal text-muted">{done ? "Done" : "To do"}</span>
        </p>
        <div className="mt-1 text-sm text-muted">{children}</div>
      </div>
    </li>
  );
}

function Steps({ s, reload }: { s: InstagramStatus; reload: () => void }) {
  const [busy, setBusy] = React.useState<string | null>(null);
  const [confirm, setConfirm] = React.useState(false);
  const keys = s.app_configured && s.encryption_key_set;
  const creator = s.connected && (!s.account_type || /CREATOR|BUSINESS/i.test(s.account_type));
  const redirect = s.requirements.join(" ").match(/https?:\/\/\S+\/callback/)?.[0] ?? "http://localhost:8001/api/instagram/callback";

  const act = async (name: string, fn: () => Promise<unknown>, ok: string) => {
    setBusy(name);
    try {
      await fn();
      toast.success(ok);
      window.dispatchEvent(new Event(DATA_CHANGED));
      reload();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <Section title="Connect Instagram" sub="You log in on instagram.com. This app never sees your password.">
      <ol>
        <Step n={1} done={creator} title="Use a Creator account" testid="step-creator">
          Instagram app → Settings → Account type and tools → Switch to professional account → <b className="text-fg">Creator</b>. It&apos;s free and unlocks insights.
        </Step>
        <Step n={2} done={keys} title="Add your Meta app keys" testid="step-keys">
          {keys ? (
            "Keys are set on the server."
          ) : (
            <>
              <p>Create a Meta app (Instagram API with Instagram Login), then put these in the project&apos;s <code>.env</code> and restart with <code>./stop.sh &amp;&amp; ./dev.sh</code>:</p>
              <pre className="mt-2 overflow-x-auto rounded-md bg-bg p-3 text-xs text-fg">
                {[!s.app_configured && "META_APP_ID=<Instagram app ID>", !s.app_configured && "META_APP_SECRET=<Instagram app secret>", !s.encryption_key_set && "TOKEN_ENCRYPTION_KEY=<output of scripts/gen_key.py>", `META_REDIRECT_URI=${redirect}`]
                  .filter(Boolean)
                  .join("\n")}
              </pre>
              <p className="mt-2">
                In the Meta app, add this exact redirect URI: <code className="text-fg">{redirect}</code>. Add <b className="text-fg">vivek_techfocus</b> as an Instagram tester while the app is in Development mode. Full guide: <code>docs/instagram-setup.md</code>.
              </p>
            </>
          )}
        </Step>
        <Step n={3} done={s.connected} title="Connect your account" testid="step-connect">
          {s.connected ? (
            <div className="flex flex-col gap-3">
              <p>
                Connected as <b className="text-fg">@{s.username}</b>
                {s.token.expires_at ? ` · login valid until ${fmtDateTime(s.token.expires_at as string)}` : ""}
                {s.last_sync_at ? ` · last updated ${fmtDateTime(s.last_sync_at)}` : ""}
              </p>
              {s.auto_sync && (
                <p className="text-xs">
                  {s.auto_sync.enabled ? "Updates automatically every day at 06:30 IST while the app is running (read-only)." : "Daily auto-update is off (ENABLE_LOCAL_SCHEDULER=false)."}
                  {s.auto_sync.last && ` Last automatic update: ${fmtDateTime(s.auto_sync.last.at)}${s.auto_sync.last.ok ? "" : ` (failed: ${s.auto_sync.last.error})`}.`}
                </p>
              )}
              <ul className="flex flex-col gap-1">
                {s.permissions.map((p) => (
                  <li key={p.scope} className="flex items-center gap-2 text-xs">
                    {p.granted ? <CheckCircle2 className="size-3.5 text-emerald-400" /> : <Circle className="size-3.5" />}
                    {p.purpose}
                  </li>
                ))}
              </ul>
              {s.last_error && <p className="text-xs text-red-700 dark:text-red-300">Last error: {s.last_error}</p>}
              <div className="flex gap-2">
                <Button disabled={busy !== null} onClick={() => act("sync", () => api.instagramSync(), "Updated. Your latest numbers are in.")}>
                  {busy === "sync" ? "Updating…" : "Update now"}
                </Button>
                <Button variant="ghost" disabled={busy !== null} onClick={() => setConfirm(true)}>
                  Disconnect
                </Button>
              </div>
            </div>
          ) : (
            <Button
              className="mt-2"
              disabled={!keys || busy !== null}
              onClick={async () => {
                setBusy("connect");
                try {
                  const { authorize_url } = await api.instagramConnect();
                  window.location.assign(authorize_url);
                } catch (e) {
                  toast.error(errorMessage(e));
                  setBusy(null);
                }
              }}
            >
              {busy === "connect" ? "Opening Instagram…" : "Connect Instagram"}
            </Button>
          )}
        </Step>
      </ol>
      <ConfirmDialog
        open={confirm}
        onOpenChange={setConfirm}
        title="Disconnect Instagram?"
        description="This deletes the saved login from this app. Your posts and numbers stay."
        confirmLabel="Disconnect"
        destructive
        busy={busy === "disconnect"}
        onConfirm={() => act("disconnect", () => api.instagramDisconnect(), "Disconnected").then(() => setConfirm(false))}
      />
    </Section>
  );
}

// ---------- Manual data ----------
type ManualTab = "post" | "csv" | "followers";

async function announce() {
  window.dispatchEvent(new Event(DATA_CHANGED));
  try {
    const s = await api.settings();
    if (s.data_mode !== "demo") toast.success("The app switched from demo data to your real numbers.");
  } catch {
    /* ignore */
  }
}

function Manual() {
  const [tab, setTab] = React.useState<ManualTab>("post");
  return (
    <Section title="No API yet? Add your numbers" sub="Copy them from Instagram → your reel → View insights. Takes a minute per post.">
      <div className="mb-5">
        <Segmented
          label="Add data"
          value={tab}
          onChange={setTab}
          options={[
            { value: "post", label: "Add a post" },
            { value: "csv", label: "Import CSV" },
            { value: "followers", label: "Follower count" },
          ]}
        />
      </div>
      {tab === "post" && <PostForm />}
      {tab === "csv" && <CsvImport />}
      {tab === "followers" && <Followers />}
    </Section>
  );
}

const NUMS: [keyof PostIn, string][] = [
  ["views", "Plays (Instagram: Views)"],
  ["reach", "People reached (Accounts reached)"],
  ["likes", "Likes"],
  ["comments", "Comments"],
  ["shares", "Shares"],
  ["saves", "Saves"],
  ["avg_watch_seconds", "Average watch time (s)"],
  ["length_seconds", "Reel length (s)"],
];

function PostForm() {
  const empty = { title: "", date: todayISO(), link: "", hook: "", category: "", format: "", nums: {} as Record<string, string> };
  const [f, setF] = React.useState(empty);
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState<string | null>(null);
  return (
    <form
      className="grid gap-4 sm:grid-cols-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!f.title.trim()) return setErr("Give the post a title.");
        setBusy(true);
        setErr(null);
        const body: PostIn = {
          title: f.title.trim(),
          published_at: `${f.date}T12:00:00+05:30`,
          permalink: f.link || null,
          hook_text: f.hook || null,
          category: f.category || null,
          format_style: f.format || null,
        };
        for (const [k] of NUMS) {
          const v = f.nums[k];
          if (v !== undefined && v !== "") (body as unknown as Record<string, number>)[k] = Number(v);
        }
        try {
          await v2.addPost(body);
          toast.success("Post added");
          setF(empty);
          await announce();
        } catch (e2) {
          setErr(errorMessage(e2));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label="Title" htmlFor="p-title" className="sm:col-span-2">
        <Input id="p-title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="What the reel was about" />
      </Field>
      <Field label="Posted on" htmlFor="p-date">
        <Input id="p-date" type="date" value={f.date} onChange={(e) => setF({ ...f, date: e.target.value })} />
      </Field>
      <Field label="Link (optional)" htmlFor="p-link">
        <Input id="p-link" value={f.link} onChange={(e) => setF({ ...f, link: e.target.value })} placeholder="https://instagram.com/reel/…" />
      </Field>
      <Field label="Hook (first line)" htmlFor="p-hook" className="sm:col-span-2">
        <Input id="p-hook" value={f.hook} onChange={(e) => setF({ ...f, hook: e.target.value })} />
      </Field>
      <Field label="Topic" htmlFor="p-cat">
        <Select id="p-cat" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>
          <option value="">—</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {catLabel(c)}
            </option>
          ))}
        </Select>
      </Field>
      <Field label="Format" htmlFor="p-fmt">
        <Select id="p-fmt" value={f.format} onChange={(e) => setF({ ...f, format: e.target.value })}>
          <option value="">—</option>
          {FORMATS.map((x) => (
            <option key={x} value={x}>
              {fmtLabel(x)}
            </option>
          ))}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3 sm:col-span-2 sm:grid-cols-4">
        {NUMS.map(([k, l]) => (
          <Field key={k} label={l} htmlFor={`p-${k}`}>
            <Input id={`p-${k}`} type="number" min={0} step={k === "avg_watch_seconds" ? "0.1" : "1"} inputMode="decimal" value={f.nums[k] ?? ""} onChange={(e) => setF({ ...f, nums: { ...f.nums, [k]: e.target.value } })} />
          </Field>
        ))}
      </div>
      {err && <p role="alert" className="text-sm text-red-400 sm:col-span-2">{err}</p>}
      <div className="sm:col-span-2">
        <Button type="submit" disabled={busy}>
          {busy ? "Adding…" : "Add post"}
        </Button>
      </div>
    </form>
  );
}

function CsvImport() {
  const tpl = useApi(() => v2.csvTemplate(), []);
  const [text, setText] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  const [result, setResult] = React.useState<{ added: number; errors: string[] } | null>(null);
  const href = tpl.data ? `data:text/csv;charset=utf-8,${encodeURIComponent(`${tpl.data.columns.join(",")}\n${tpl.data.example}\n`)}` : undefined;
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {href && (
          <a href={href} download="posts-template.csv" className="inline-flex items-center gap-1.5 text-accent hover:underline">
            <Download className="size-4" /> Download template
          </a>
        )}
        <label className="cursor-pointer text-accent hover:underline">
          Choose a .csv file
          <input
            type="file"
            accept=".csv,text/csv"
            className="sr-only"
            aria-label="CSV file"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (file) setText(await file.text());
            }}
          />
        </label>
      </div>
      {tpl.data && <p className="text-xs text-muted">Columns: {tpl.data.columns.join(", ")}</p>}
      <Textarea aria-label="CSV text" value={text} onChange={(e) => setText(e.target.value)} className="min-h-40 font-mono text-xs" placeholder="date,title,views,reach,…" />
      <div>
        <Button
          disabled={busy || !text.trim()}
          onClick={async () => {
            setBusy(true);
            try {
              const r = await v2.importCsv(text);
              const res = { added: Number(r.added ?? 0), errors: (r.errors ?? []).map(String) };
              setResult(res);
              if (res.added > 0) await announce();
            } catch (e) {
              toast.error(errorMessage(e));
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Importing…" : "Import"}
        </Button>
      </div>
      {result && (
        <div role="status" data-testid="csv-result" className="rounded-md border border-line bg-bg p-3 text-sm">
          <p className="font-medium">Added {result.added} post{result.added === 1 ? "" : "s"}.</p>
          {result.errors.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-red-700 dark:text-red-300">
              {result.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}

function Followers() {
  const [n, setN] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  return (
    <form
      className="flex max-w-sm flex-col gap-3"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!n) return;
        setBusy(true);
        try {
          await api.manualSnapshot({ snapshot_date: todayISO(), followers: Number(n) });
          toast.success("Follower count saved for today");
          setN("");
          await announce();
        } catch (e2) {
          toast.error(errorMessage(e2));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field label="Followers today" htmlFor="f-n" hint="Add it once a day (or whenever you remember) to track your goal.">
        <Input id="f-n" type="number" min={0} inputMode="numeric" value={n} onChange={(e) => setN(e.target.value)} className="h-11 text-lg" />
      </Field>
      <div>
        <Button type="submit" disabled={busy || !n}>
          Save
        </Button>
      </div>
    </form>
  );
}
