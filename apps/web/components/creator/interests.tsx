"use client";
// "What you're into": built from the user's own Instagram data download and notes they type in.
// Nothing here fetches a link or reads other accounts.
import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { FileUp, Trash2 } from "lucide-react";
import { errorMessage, v5, type ImportResult, type InterestProfile } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDate } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Explain } from "@/components/ui/explain";
import { Input } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { DATA_CHANGED, useDataChanged } from "@/components/shell";
import { Bar } from "./kit";
import { Panel } from "./layout";

export function useInterests() {
  const q = useApi(() => v5.interests(), []);
  useDataChanged(q.reload);
  return q;
}

function Guessed() {
  return (
    <Badge tone="amber" title="Worked out from keywords, not told to us by Instagram">
      <Explain term="inferred" />
    </Badge>
  );
}

/** Compact version for Home: top topics + top creators. */
export function InterestsSummary({ p }: { p: InterestProfile }) {
  if (p.total === 0) return <InterestsEmpty />;
  return (
    <div className="flex flex-col gap-4" data-testid="interests-summary">
      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-muted">Topics you save and like</p>
          <Guessed />
        </div>
        <ul className="flex flex-col gap-2">
          {p.categories.slice(0, 4).map((c) => (
            <li key={c.category}>
              <div className="flex justify-between text-sm">
                <span>{c.label}</span>
                <span className="tabular-nums text-muted">{c.share}%</span>
              </div>
              <Bar value={c.share} className="mt-1 h-1.5" />
            </li>
          ))}
          {p.categories.length === 0 && <li className="text-sm text-muted">No topic matched yet. Add a note on why you liked a reel.</li>}
        </ul>
      </div>
      {p.top_creators.length > 0 && (
        <div>
          <p className="mb-1.5 text-xs font-medium text-muted">Creators you save from most</p>
          <div className="flex flex-wrap gap-1.5">
            {p.top_creators.slice(0, 6).map((c) => (
              <span key={c.creator} className="rounded-full bg-panel-2 px-2.5 py-1 text-xs">
                @{c.creator} <span className="text-muted">· {c.n}</span>
              </span>
            ))}
          </div>
        </div>
      )}
      <p className="text-[11px] text-muted">
        From {p.counts.saved} saved, {p.counts.liked} liked and {p.counts.manual} noted items.{" "}
        <Link href="/settings?tab=import" className="text-accent">Update</Link>
      </p>
    </div>
  );
}

function InterestsEmpty() {
  return (
    <div className="flex flex-col items-start gap-2 text-sm" data-testid="interests-empty">
      <p className="text-muted">Instagram doesn&apos;t share what you save or like through its API. You can add it yourself:</p>
      <ul className="list-disc pl-5 text-muted">
        <li>import your Instagram data download (2 minutes), or</li>
        <li>paste a reel link and say why you liked it.</li>
      </ul>
      <Link href="/settings?tab=import" className="ig-gradient mt-1 inline-flex h-9 items-center rounded-xl px-3.5 text-sm font-semibold text-white">
        Import my likes &amp; saves
      </Link>
    </div>
  );
}

/** Insights tab: the full profile in a grid of panels. */
export function InterestsDetail() {
  const q = useInterests();
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const p = q.data!;
  if (p.total === 0)
    return (
      <Panel title="What you're into" what="Built from your own saves, likes and notes.">
        <InterestsEmpty />
      </Panel>
    );
  const maxMonth = Math.max(1, ...p.monthly.map((m) => m.saved + m.liked));
  return (
    <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-3 md:grid-rows-2">
      <Panel title="Topics you're into" what="Guessed from collection names, your notes and creator names." todo="Your next-reel picks lean toward these." className="md:row-span-2">
        <div className="mb-3 flex items-center gap-2"><Guessed /><span className="text-[11px] text-muted">{p.total} items</span></div>
        <ul className="flex flex-col gap-4">
          {p.categories.map((c) => (
            <li key={c.category}>
              <div className="flex justify-between text-sm font-medium">
                <span>{c.label}</span>
                <span className="tabular-nums">{c.share}%</span>
              </div>
              <Bar value={c.share} className="mt-1" />
              <p className="mt-1 text-[11px] text-muted">
                {c.matches} matches · e.g. {c.evidence.slice(0, 2).join(", ")}
              </p>
            </li>
          ))}
        </ul>
        <p className="mt-4 text-[11px] text-muted">{p.inferred_note}</p>
      </Panel>
      <Panel title="Creators you save from" what="Accounts whose posts you save or like most." todo="Study their first 2 seconds, then do it your way.">
        <ul className="flex flex-col divide-y divide-line">
          {p.top_creators.map((c) => (
            <li key={c.creator} className="flex items-center justify-between py-2 text-sm">
              <span>@{c.creator}</span>
              <span className="text-xs text-muted">{Object.entries(c.sources).map(([k, v]) => `${v} ${k}`).join(" · ")}</span>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="Your collections" what={<>Folders of saved posts (<Explain term="collection" iconOnly />).</>}>
        {p.collections.length === 0 ? (
          <p className="text-sm text-muted">No collections in your download.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {p.collections.map((c) => (
              <li key={c.name} className="flex items-center justify-between gap-2 text-sm">
                <span className="truncate">{c.name}</span>
                <span className="shrink-0 text-xs text-muted">{c.n} saved</span>
              </li>
            ))}
          </ul>
        )}
        {p.topics.length > 0 && (
          <>
            <p className="mb-1 mt-4 text-xs font-medium text-muted">Topics Instagram thinks you like (from your download)</p>
            <div className="flex flex-wrap gap-1.5">
              {p.topics.map((t) => (
                <span key={t} className="rounded-full bg-panel-2 px-2 py-0.5 text-xs">{t}</span>
              ))}
            </div>
          </>
        )}
      </Panel>
      <Panel title="Saves & likes over time" what="How many posts you saved and liked each month.">
        {p.monthly.length === 0 ? (
          <p className="text-sm text-muted">No dates in your data.</p>
        ) : (
          <ul className="flex flex-col gap-1.5">
            {p.monthly.map((m) => (
              <li key={m.month} className="grid grid-cols-[64px_1fr_56px] items-center gap-2 text-xs">
                <span className="text-muted">{m.month}</span>
                <Bar value={m.saved + m.liked} max={maxMonth} className="h-1.5" />
                <span className="text-right tabular-nums text-muted">{m.saved}s · {m.liked}l</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      <Panel title="Your notes" what="Reels you noted, and why you liked them." todo="Add one whenever a reel stops your scroll.">
        <NoteForm onAdded={q.reload} />
        <ul className="mt-3 flex flex-col gap-2">
          {p.notes.map((n) => (
            <li key={n.id} className="group flex items-start justify-between gap-2 text-sm">
              <span>
                {n.note}
                <span className="block text-[11px] text-muted">
                  {n.creator ? `@${n.creator} · ` : ""}
                  {fmtDate(n.at)}
                </span>
              </span>
              <button
                type="button"
                aria-label="Delete note"
                className="text-muted opacity-0 hover:text-fg group-hover:opacity-100"
                onClick={async () => {
                  try {
                    await v5.deleteInterest(n.id);
                    q.reload();
                  } catch (e) {
                    toast.error(errorMessage(e));
                  }
                }}
              >
                <Trash2 className="size-4" />
              </button>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}

/** Paste a reel link + one line on why you liked it. The link is stored, never opened. */
export function NoteForm({ onAdded }: { onAdded?: () => void }) {
  const [url, setUrl] = React.useState("");
  const [note, setNote] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  return (
    <form
      className="flex flex-col gap-2"
      onSubmit={async (e) => {
        e.preventDefault();
        if (!note.trim()) return;
        setBusy(true);
        try {
          await v5.addInterest({ url: url.trim() || null, note: note.trim() });
          toast.success("Noted. It now feeds your next-reel picks.");
          setUrl("");
          setNote("");
          onAdded?.();
          window.dispatchEvent(new Event(DATA_CHANGED));
        } catch (err) {
          toast.error(errorMessage(err));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Input aria-label="Reel link (optional)" placeholder="Reel link (optional) https://www.instagram.com/reel/…" value={url} onChange={(e) => setUrl(e.target.value)} />
      <div className="flex gap-2">
        <Input aria-label="Why I liked it" placeholder="Why I liked it, e.g. great hook about interview fear" value={note} onChange={(e) => setNote(e.target.value)} />
        <Button type="submit" disabled={busy || !note.trim()}>
          Add
        </Button>
      </div>
    </form>
  );
}

export const EXPORT_STEPS = [
  "Open Instagram (app or instagram.com) → your profile → ☰ menu → Accounts Center.",
  "Tap “Your information and permissions” → “Download your information” (sometimes called “Export your information”).",
  "Choose “Download or transfer information” → pick your Instagram account → “Some of your information”.",
  "Tick “Saved”, “Likes” and “Followers and following” (optional: “Ads information” for Instagram's topic list).",
  "Choose “Download to device”, Date range “All time”, and Format: JSON (not HTML). Media quality doesn't matter.",
  "Instagram emails you when it's ready (minutes to a few hours). Download the .zip.",
  "Upload the .zip here (or just saved_posts.json, saved_collections.json and liked_posts.json).",
];

/** Settings: import the Instagram data download. */
export function ImportPanel() {
  const [files, setFiles] = React.useState<File[]>([]);
  const [busy, setBusy] = React.useState(false);
  const [res, setRes] = React.useState<ImportResult | null>(null);
  const prof = useInterests();
  return (
    <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-2">
      <Panel title="Get your data from Instagram" what="Instagram's API can't see your saved or liked posts, but you can download them yourself." todo="Follow these steps once; repeat every month or two.">
        <ol className="flex list-decimal flex-col gap-2 pl-5 text-sm">
          {EXPORT_STEPS.map((s) => (
            <li key={s}>{s}</li>
          ))}
        </ol>
        <p className="mt-3 text-xs text-muted">
          The file stays on this computer. We read only saved, liked, following and topic files and skip everything else (messages, photos, personal info). Links are stored as text and never opened.
        </p>
      </Panel>
      <div className="flex flex-col gap-4 md:min-h-0">
        <Panel title="Upload" what="A .zip from Instagram, or the JSON files inside it." todo="Choose the file, then press Import." className="shrink-0">
          <div className="flex flex-col gap-3">
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-line p-4 text-sm hover:border-accent">
              <FileUp className="size-5 text-muted" />
              <span className="min-w-0 flex-1 truncate">{files.length ? files.map((f) => f.name).join(", ") : "Choose .zip or .json files"}</span>
              <input
                type="file"
                aria-label="Instagram data files"
                accept=".zip,.json,application/zip,application/json"
                multiple
                className="sr-only"
                onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
              />
            </label>
            <Button
              disabled={busy || files.length === 0}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await v5.importInterests(files);
                  setRes(r);
                  if (r.added_total) toast.success(`Imported ${r.added_total} items`);
                  window.dispatchEvent(new Event(DATA_CHANGED));
                  prof.reload();
                } catch (e) {
                  toast.error(errorMessage(e));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? "Reading…" : "Import"}
            </Button>
            {res && (
              <div data-testid="import-result" className="rounded-xl bg-panel-2 p-3 text-sm">
                <p className="font-medium">
                  Added {res.added_total} new item{res.added_total === 1 ? "" : "s"}
                  {Object.keys(res.added).length > 0 && `: ${Object.entries(res.added).map(([k, v]) => `${v} ${k}`).join(", ")}`}.
                </p>
                {res.hint && <p className="mt-1 text-amber-700 dark:text-amber-300">{res.hint}</p>}
                {res.errors.length > 0 && <p className="mt-1 text-xs text-red-700 dark:text-red-300">{res.errors.join(" · ")}</p>}
                <p className="mt-1 text-xs text-muted">Re-importing the same file adds nothing twice.</p>
              </div>
            )}
          </div>
        </Panel>
        <Panel title="Or add one by hand" what="Paste a reel you liked and one line on why." todo="Your note counts more than a like when we pick topics.">
          <NoteForm onAdded={prof.reload} />
          {prof.data && prof.data.total > 0 && (
            <p className="mt-3 text-xs text-muted">
              You have {prof.data.counts.saved} saved, {prof.data.counts.liked} liked, {prof.data.counts.following} following, {prof.data.counts.manual} notes.
              {prof.data.last_import_at && ` Last import ${fmtDate(prof.data.last_import_at)}.`} <Link href="/insights?tab=interests" className="text-accent">See what you&apos;re into</Link>
            </p>
          )}
        </Panel>
      </div>
    </div>
  );
}
