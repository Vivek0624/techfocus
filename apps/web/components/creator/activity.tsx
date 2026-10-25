"use client";
import * as React from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Heart } from "lucide-react";
import { errorMessage, v3, type Comment, type Comments } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { cn } from "@/lib/utils";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Panel, Screen, Tabs } from "./layout";

const TABS = [
  ["needs_reply", "Needs reply"],
  ["questions", "Questions"],
  ["requests", "Requests"],
  ["all", "All"],
  ["hidden", "Hidden"],
  ["mentions", "Mentions"],
] as const;
type Tab = (typeof TABS)[number][0];

const INTENT: Record<string, [string, BadgeTone]> = {
  question: ["Question", "blue"],
  request: ["Request", "violet"],
  praise: ["Praise", "green"],
  feedback: ["Feedback", "amber"],
  spam: ["Spam", "red"],
};

export function timeAgo(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return "";
  const s = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  if (s < 604800) return `${Math.floor(s / 86400)}d`;
  return `${Math.floor(s / 604800)}w`;
}

export function Avatar({ name, className }: { name: string; className?: string }) {
  return (
    <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-full bg-panel-2 text-sm font-semibold uppercase", className)} aria-hidden>
      {name.replace(/^[^a-z0-9]+/i, "").charAt(0) || "?"}
    </span>
  );
}

/** Heart icon with a red count badge, like Instagram's notifications. */
export function ActivityLink() {
  const q = useApi(() => v3.comments("needs_reply").catch(() => null), []);
  const n = q.data?.counts?.needs_reply ?? 0;
  return (
    <Link href="/activity" aria-label="Activity" className="relative text-fg hover:opacity-70">
      <Heart className="size-6" />
      {n > 0 && (
        <span data-testid="activity-badge" className="absolute -right-1.5 -top-1.5 flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-[#ff3040] px-1 text-[11px] font-semibold text-white">
          {n > 99 ? "99+" : n}
        </span>
      )}
    </Link>
  );
}

export function ActivityPage() {
  const [tab, setTab] = React.useState<Tab>("needs_reply");
  return (
    <Screen title="Activity" sub="Comments on your posts and places you were tagged. Replies are sent only when you press Send.">
      <Panel
        title="Reply to these"
        what="Questions and requests first. Each reply thread includes your earlier answers from Instagram."
        todo="Answer questions within a day: it brings people back to your profile."
        className="md:flex-1"
        actions={<Tabs label="Activity" value={tab} onChange={setTab} items={TABS.map(([k, l]) => [k, l] as [Tab, string])} />}
      >
        {tab === "mentions" ? <Mentions /> : <CommentList filter={tab} />}
      </Panel>
    </Screen>
  );
}

function CommentList({ filter }: { filter: string }) {
  const q = useApi(() => v3.comments(filter), [filter]);
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const d = q.data as Comments;
  return (
    <div>
      {!d.available && <p className="py-3 text-sm text-muted">{d.note ?? "Comments aren't available yet."}</p>}
      {d.items.length === 0 ? (
        <EmptyState title="You're all caught up" />
      ) : (
        <ul className="divide-y divide-line" data-testid="comments">
          {d.items.map((c) => (
            <CommentRow key={c.id} c={c} onChange={q.reload} />
          ))}
        </ul>
      )}
      {d.note && d.available && <p className="mt-4 text-xs text-muted">{d.note}</p>}
    </div>
  );
}

function CommentRow({ c, onChange }: { c: Comment; onChange: () => void }) {
  const [text, setText] = React.useState(c.draft_reply ?? "");
  const [busy, setBusy] = React.useState<string | null>(null);
  const [note, setNote] = React.useState<string | null>(null);
  const [idea, setIdea] = React.useState<number | null>(c.idea_id);
  const [now] = React.useState(() => Date.now());
  const intent = INTENT[c.intent];

  async function run<T>(name: string, fn: () => Promise<T>, ok?: string): Promise<T | null> {
    setBusy(name);
    try {
      const r = await fn();
      if (ok) toast.success(ok);
      return r;
    } catch (e) {
      toast.error(errorMessage(e));
      return null;
    } finally {
      setBusy(null);
    }
  }

  return (
    <li className="flex gap-3 py-4" data-testid={`comment-${c.id}`}>
      <Avatar name={c.username} />
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          <b className="font-semibold">{c.username}</b> {c.text}
        </p>
        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
          <span>{timeAgo(c.commented_at, now)}</span>
          {c.like_count ? <span>{c.like_count} likes</span> : null}
          {c.post_title && <span className="truncate">on “{c.post_title}”</span>}
          {intent && <Badge tone={intent[1]}>{intent[0]}</Badge>}
        </div>
        {c.replies && c.replies.length > 0 && (
          <ul className="mt-2 flex flex-col gap-1.5 border-l-2 border-line pl-3" data-testid="thread">
            {c.replies.map((r) => (
              <li key={r.id} className="text-sm">
                <b className="font-semibold">{r.from_owner ? "You" : r.username}</b> <span className={cn(r.from_owner && "text-muted")}>{r.text}</span>
                <span className="ml-2 text-[11px] text-muted">{timeAgo(r.commented_at, now)}</span>
              </li>
            ))}
          </ul>
        )}
        {c.replied ? (
          !c.replies?.some((r) => r.from_owner) && <p className="mt-2 border-l-2 border-line pl-3 text-sm text-muted">You replied: {c.reply_text}</p>
        ) : (
          !c.hidden && (
            <form
              className="mt-3 flex items-end gap-2"
              onSubmit={async (e) => {
                e.preventDefault();
                if (!text.trim()) return;
                const r = await run("send", () => v3.reply(c.id, text.trim()));
                if (r) {
                  if (r.simulated && r.note) setNote(r.note);
                  else {
                    toast.success("Reply posted");
                    onChange();
                  }
                }
              }}
            >
              <textarea aria-label={`Reply to ${c.username}`} value={text} onChange={(e) => setText(e.target.value)} rows={2} className="min-h-10 flex-1 resize-y rounded-lg border border-line bg-bg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-accent" />
              <button type="submit" disabled={busy !== null || !text.trim()} className="h-9 px-1 text-sm font-semibold text-accent disabled:opacity-40">
                {busy === "send" ? "Sending…" : "Send"}
              </button>
            </form>
          )
        )}
        {note && (
          <p role="status" className="mt-2 text-xs text-muted">
            {note}
          </p>
        )}
        <div className="mt-2 flex flex-wrap gap-4 text-xs font-semibold text-muted">
          <button type="button" className="hover:text-fg" disabled={busy !== null} onClick={async () => (await run("hide", () => v3.hide(c.id, !c.hidden), c.hidden ? "Unhidden" : "Hidden")) !== null && onChange()}>
            {c.hidden ? "Unhide" : "Hide"}
          </button>
          {idea ? (
            <Link href="/ideas" className="text-accent">
              Open in Ideas →
            </Link>
          ) : (
            <button
              type="button"
              className="hover:text-fg"
              disabled={busy !== null}
              onClick={async () => {
                const r = await run("idea", () => v3.toIdea(c.id));
                if (r) {
                  setIdea(r.id);
                  toast.success(r.existing ? "Already in your ideas" : "Added to Ideas");
                }
              }}
            >
              Turn into idea
            </button>
          )}
          {!c.done && (
            <button type="button" className="hover:text-fg" disabled={busy !== null} onClick={async () => (await run("done", () => v3.done(c.id), "Marked done")) !== null && onChange()}>
              Done
            </button>
          )}
        </div>
      </div>
    </li>
  );
}

function Mentions() {
  const q = useApi(() => v3.mentions(), []);
  const [now] = React.useState(() => Date.now());
  if (q.loading && !q.data) return <Loading />;
  if (q.error) return <ErrorState message={q.error} onRetry={q.reload} />;
  const items = q.data?.items ?? [];
  if (!items.length) return <EmptyState title="No mentions yet" />;
  return (
    <ul className="divide-y divide-line" data-testid="mentions">
      {items.map((m) => (
        <li key={m.id} className="flex gap-3 py-4">
          <Avatar name={m.username} />
          <div className="min-w-0 flex-1 text-sm">
            <p>
              <b className="font-semibold">{m.username}</b> mentioned you: {m.caption}
            </p>
            <p className="mt-1 text-xs text-muted">
              {timeAgo(m.posted_at, now)}
              {m.permalink && (
                <>
                  {" · "}
                  <a href={m.permalink} target="_blank" rel="noreferrer" className="font-semibold text-accent">
                    View post
                  </a>
                </>
              )}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
