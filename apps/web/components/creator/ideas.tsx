"use client";
import * as React from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { Archive, ArchiveRestore, ArrowRight, CalendarDays, ChevronLeft, ChevronRight, Copy, Plus, Search, Trash2, X } from "lucide-react";
import { ApiError, errorMessage, v2, v3, v5, type Board, type BoardItem, type ContentIdea, type Similar, type WeekItem } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { CATEGORIES, catLabel, dayName, mondayOf, nextStage, STAGE_LABEL, STAGES } from "@/lib/creator";
import { addDays, cn, fmtDate, fmtSlot, istWall, todayISO } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { AUDIENCES, audLabel } from "./growth";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Explain } from "@/components/ui/explain";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { useDataChanged } from "@/components/shell";
import { Chip } from "./kit";
import { Panel, Screen, Tabs } from "./layout";
import { bestTimeHint } from "./audience";

type View = "list" | "board" | "week";
const UNDO_MS = 5000;

const notesOf = (i: ContentIdea) => i.notes ?? (i.evidence ?? []).join("\n");

export function IdeasPage() {
  const params = useSearchParams();
  const router = useRouter();
  const pv = params?.get("view");
  const view: View = pv === "week" || pv === "board" ? pv : "list";
  const [search, setSearch] = React.useState("");
  const [topic, setTopic] = React.useState("");
  const [stage, setStage] = React.useState("");
  const [showArchived, setShowArchived] = React.useState(false);
  const list = useApi(() => v5.ideas({}), []);
  const board = useApi(() => v2.board(), []);
  // list/board are new objects every render; keep the latest in a ref so reload stays stable (no refetch loop).
  const latest = React.useRef({ list, board });
  latest.current = { list, board };
  const reload = React.useCallback(() => {
    latest.current.list.reload();
    latest.current.board.reload();
  }, []);
  useDataChanged(reload);
  const [open, setOpen] = React.useState<number | null>(null);
  const [hidden, setHidden] = React.useState<Set<number>>(new Set());

  const match = React.useCallback(
    (title: string, extra: string, cat: string | null) =>
      (!search || `${title} ${extra}`.toLowerCase().includes(search.toLowerCase())) && (!topic || cat === topic),
    [search, topic],
  );

  /** Delete with a 5-second Undo. Items vanish at once; the server delete happens only if not undone. */
  const removeWithUndo = React.useCallback(
    (ids: number[]) => {
      setHidden((h) => new Set([...h, ...ids]));
      let undone = false;
      const timer = setTimeout(async () => {
        if (undone) return;
        try {
          await v5.bulkIdeas(ids, "delete");
        } catch (e) {
          toast.error(errorMessage(e));
        }
        reload();
      }, UNDO_MS);
      toast(`Deleted ${ids.length === 1 ? "1 idea" : `${ids.length} ideas`}`, {
        duration: UNDO_MS,
        action: {
          label: "Undo",
          onClick: () => {
            undone = true;
            clearTimeout(timer);
            setHidden((h) => new Set([...h].filter((x) => !ids.includes(x))));
          },
        },
      });
    },
    [reload],
  );

  const ideas = (list.data?.items ?? []).filter(
    (i) => !hidden.has(i.id) && (showArchived ? i.status === "archived" : i.status !== "archived") && (!stage || i.status === stage) && match(i.title, `${notesOf(i)} ${i.recommended_hook ?? ""}`, i.pillar),
  );

  return (
    <Screen
      title="Ideas"
      sub="Your notebook for reel ideas. Jot anything down, try different angles, then move it along: Idea → Script → Recording → Editing → Ready → Published."
      actions={
        <Tabs
          label="View"
          value={view}
          onChange={(v) => router.replace(v === "list" ? "/ideas" : `/ideas?view=${v}`)}
          items={[
            ["list", "List"],
            ["board", "Board"],
            ["week", "Week"],
          ]}
        />
      }
    >
      <div className="grid shrink-0 gap-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <QuickCapture onAdded={reload} />
        <div className="flex flex-wrap items-start gap-2 lg:flex-nowrap">
          <div className="relative min-w-32 flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted" />
            <Input aria-label="Search ideas" placeholder="Search titles, notes, hooks" value={search} onChange={(e) => setSearch(e.target.value)} className="h-9 pl-8" />
          </div>
          <Select aria-label="Filter by topic" value={topic} onChange={(e) => setTopic(e.target.value)} className="h-9 w-32 shrink-0">
            <option value="">All topics</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {catLabel(c)}
              </option>
            ))}
          </Select>
          {view === "list" && (
            <>
              <Select aria-label="Filter by stage" value={stage} onChange={(e) => setStage(e.target.value)} className="h-9 w-28 shrink-0">
                <option value="">All stages</option>
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {STAGE_LABEL[s]}
                  </option>
                ))}
              </Select>
              <Chip active={showArchived} onClick={() => setShowArchived(!showArchived)} className="h-9 shrink-0">
                Archived
              </Chip>
            </>
          )}
        </div>
      </div>
      {(list.loading && !list.data) || (board.loading && !board.data) ? <Loading /> : null}
      {list.error && <ErrorState message={list.error} onRetry={reload} />}
      {list.data && view === "list" && <ListView ideas={ideas} onChange={reload} onDelete={removeWithUndo} archivedView={showArchived} />}
      {board.data && view === "board" && (
        <Panel title="Board" what="Drag a card to another column, or use its stage menu." className="md:flex-1" bodyClassName="md:overflow-hidden">
          <BoardView board={board.data} onChange={reload} onOpen={setOpen} hideFilter search={(i) => !hidden.has(i.id) && match(i.title, i.hook ?? "", i.category)} />
        </Panel>
      )}
      {board.data && view === "week" && (
        <Panel title="Week" what="Plan which day each reel goes out (IST)." className="md:flex-1">
          <WeekView board={board.data} onChange={reload} onOpen={setOpen} />
        </Panel>
      )}
      {open !== null && <IdeaSheet id={open} onClose={() => setOpen(null)} onChange={reload} onDelete={removeWithUndo} />}
    </Screen>
  );
}

// ---------- List view: notes-app style list + editor ----------
function ListView({ ideas, onChange, onDelete, archivedView }: { ideas: ContentIdea[]; onChange: () => void; onDelete: (ids: number[]) => void; archivedView: boolean }) {
  const [sel, setSel] = React.useState<Set<number>>(new Set());
  const [active, setActive] = React.useState<number | null>(null);
  const current = ideas.find((i) => i.id === active) ?? ideas[0] ?? null;
  const selected = [...sel].filter((id) => ideas.some((i) => i.id === id));
  const bulk = async (action: "archive" | "move" | "restore", status?: string) => {
    try {
      const r = await v5.bulkIdeas(selected, action, status);
      toast.success(`${r.affected} updated`);
      setSel(new Set());
      onChange();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const toggle = (id: number) => setSel((s) => (s.has(id) ? new Set([...s].filter((x) => x !== id)) : new Set([...s, id])));
  return (
    <div className="grid gap-4 md:min-h-0 md:flex-1 md:grid-cols-[minmax(0,5fr)_minmax(0,7fr)]">
      <Panel
        title={archivedView ? "Archived ideas" : "All ideas"}
        what={`${ideas.length} idea${ideas.length === 1 ? "" : "s"}. Tick to act on several at once.`}
        actions={
          ideas.length > 0 && (
            <label className="flex items-center gap-1.5 text-xs text-muted">
              <input
                type="checkbox"
                aria-label="Select all"
                checked={selected.length > 0 && selected.length === ideas.length}
                onChange={(e) => setSel(e.target.checked ? new Set(ideas.map((i) => i.id)) : new Set())}
              />
              All
            </label>
          )
        }
        testid="idea-list"
      >
        {selected.length > 0 && (
          <div role="toolbar" aria-label="Bulk actions" className="sticky top-0 z-10 mb-2 flex flex-wrap items-center gap-1.5 rounded-xl bg-panel-2 p-2 text-xs">
            <b className="mr-1">{selected.length} selected</b>
            <Select aria-label="Move selected to" value="" onChange={(e) => e.target.value && bulk("move", e.target.value)} className="h-7 w-auto px-2 text-xs">
              <option value="">Move to…</option>
              {STAGES.map((s) => (
                <option key={s} value={s}>
                  {STAGE_LABEL[s]}
                </option>
              ))}
            </Select>
            {archivedView ? (
              <Button size="sm" variant="ghost" onClick={() => bulk("restore")}>
                <ArchiveRestore /> Restore
              </Button>
            ) : (
              <Button size="sm" variant="ghost" onClick={() => bulk("archive")}>
                <Archive /> Archive
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              className="text-red-600"
              onClick={() => {
                onDelete(selected);
                setSel(new Set());
              }}
            >
              <Trash2 /> Delete
            </Button>
            <Button size="sm" variant="ghost" aria-label="Clear selection" onClick={() => setSel(new Set())}>
              <X />
            </Button>
          </div>
        )}
        {ideas.length === 0 ? (
          <EmptyState title={archivedView ? "Nothing archived" : "No ideas match"}>Add one above, or clear the search.</EmptyState>
        ) : (
          <ul className="-mx-2 flex flex-col">
            {ideas.map((i) => (
              <li key={i.id} className={cn("flex items-start gap-2 rounded-xl px-2 py-2", current?.id === i.id ? "bg-panel-2" : "hover:bg-panel-2/60")}>
                <input type="checkbox" className="mt-1" aria-label={`Select ${i.title}`} checked={sel.has(i.id)} onChange={() => toggle(i.id)} />
                <button type="button" onClick={() => setActive(i.id)} className="min-w-0 flex-1 text-left">
                  <span className="block truncate text-sm font-medium">{i.title}</span>
                  <span className="block truncate text-xs text-muted">{notesOf(i) || i.recommended_hook || "No notes yet"}</span>
                </button>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge tone={i.status === "ready" ? "green" : i.status === "idea" ? "neutral" : "blue"}>{STAGE_LABEL[i.status] ?? i.status}</Badge>
                  <span className="text-[10px] text-muted">{fmtDate(i.updated_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
      {current ? <IdeaEditor key={current.id} idea={current} onChange={onChange} onDelete={onDelete} /> : <Panel title="Pick an idea" what="Select an idea on the left to edit it." />}
    </div>
  );
}

/** Inline editor: every field saves when you leave it. */
function IdeaEditor({ idea, onChange, onDelete, inSheet }: { idea: ContentIdea; onChange: () => void; onDelete: (ids: number[]) => void; inSheet?: boolean }) {
  const [f, setF] = React.useState({
    title: idea.title,
    notes: notesOf(idea),
    pillar: idea.pillar ?? "",
    audience: idea.audience ?? "",
    hook: idea.recommended_hook ?? "",
    status: idea.status,
    when: istWall(idea.planned_at) ?? "",
  });
  const [saved, setSaved] = React.useState<string | null>(null);
  const patch = async (body: Parameters<typeof v2.updateIdea>[1], label = "Saved") => {
    try {
      await v2.updateIdea(idea.id, body);
      setSaved(label);
      onChange();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const onBlur = (k: "title" | "notes" | "hook", orig: string) => () => {
    const v = f[k].trim();
    if (v === orig.trim()) return;
    if (k === "title") {
      if (!v) return setF({ ...f, title: idea.title });
      patch({ title: v });
    } else if (k === "notes") patch({ notes: v || null });
    else patch({ recommended_hook: v || null });
  };
  const next = nextStage(f.status);
  const body = (
    <div className="flex flex-col gap-3">
      <Input aria-label="Title" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} onBlur={onBlur("title", idea.title)} className="h-11 border-transparent bg-transparent px-0 text-xl font-semibold focus:ring-0" />
      <Field label="Notes (anything: links, angles, what to try)" htmlFor={`n-${idea.id}`}>
        <Textarea id={`n-${idea.id}`} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} onBlur={onBlur("notes", notesOf(idea))} className="min-h-28" placeholder="e.g. try the chai-stall analogy; compare with the bank example" />
      </Field>
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="Stage" htmlFor={`s-${idea.id}`}>
          <Select
            id={`s-${idea.id}`}
            value={f.status}
            onChange={(e) => {
              setF({ ...f, status: e.target.value });
              patch({ status: e.target.value }, `Moved to ${STAGE_LABEL[e.target.value] ?? e.target.value}`);
            }}
          >
            {[...STAGES, "archived"].map((s) => (
              <option key={s} value={s}>
                {STAGE_LABEL[s]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Topic" htmlFor={`t-${idea.id}`}>
          <Select
            id={`t-${idea.id}`}
            value={f.pillar}
            onChange={(e) => {
              setF({ ...f, pillar: e.target.value });
              patch({ pillar: e.target.value || null });
            }}
          >
            <option value="">No topic</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {catLabel(c)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Who it's for" htmlFor={`a-${idea.id}`}>
          <Select
            id={`a-${idea.id}`}
            value={f.audience}
            onChange={(e) => {
              setF({ ...f, audience: e.target.value });
              patch({ audience: e.target.value || null });
            }}
          >
            <option value="">Guess for me</option>
            {AUDIENCES.map((a) => (
              <option key={a} value={a}>
                {audLabel(a)}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Hook: the first line people hear (stops the scroll)" htmlFor={`h-${idea.id}`}>
        <Textarea id={`h-${idea.id}`} value={f.hook} onChange={(e) => setF({ ...f, hook: e.target.value })} onBlur={onBlur("hook", idea.recommended_hook ?? "")} className="min-h-14" placeholder="e.g. Your ₹20 chai order already explains APIs." />
      </Field>
      <Field label="Plan a day (IST)" htmlFor={`w-${idea.id}`} hint="You'll get a reminder on Home 1 hour before.">
        <Input
          id={`w-${idea.id}`}
          type="datetime-local"
          value={f.when}
          onChange={(e) => setF({ ...f, when: e.target.value })}
          onBlur={async () => {
            if (f.when && f.when !== istWall(idea.planned_at)) {
              try {
                await v2.plan(idea.id, `${f.when.slice(0, 16)}:00`);
                setSaved("Planned");
                onChange();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }
          }}
        />
      </Field>
      <div className="flex flex-wrap items-center gap-2 border-t border-line pt-3">
        <Link href={`/create?idea=${idea.id}`} className="ig-gradient inline-flex h-9 items-center gap-1.5 rounded-xl px-3.5 text-sm font-semibold text-white">
          Write script <ArrowRight className="size-4" />
        </Link>
        {next && f.status !== "archived" && (
          <Button
            variant="secondary"
            onClick={() => {
              setF({ ...f, status: next });
              patch({ status: next }, `Moved to ${STAGE_LABEL[next]}`);
            }}
          >
            Done → {STAGE_LABEL[next]}
          </Button>
        )}
        <span className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            variant="ghost"
            onClick={async () => {
              try {
                await v5.cloneIdea(idea.id);
                toast.success("Duplicated. Try a different angle on the copy.");
                onChange();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}
          >
            <Copy /> Duplicate
          </Button>
          {f.status === "archived" ? (
            <Button size="sm" variant="ghost" onClick={() => patch({ status: "idea" }, "Restored")}>
              <ArchiveRestore /> Restore
            </Button>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => patch({ status: "archived" }, "Archived")}>
              <Archive /> Archive
            </Button>
          )}
          <Button size="sm" variant="ghost" className="text-red-600" onClick={() => onDelete([idea.id])}>
            <Trash2 /> Delete
          </Button>
        </span>
      </div>
      <p className="text-[11px] text-muted" aria-live="polite">
        {saved ? `${saved} ✓` : "Changes save when you click away."} · Last edited {fmtDate(idea.updated_at)}
      </p>
    </div>
  );
  if (inSheet) return body;
  return (
    <Panel title="Edit idea" what={<>Trial and error is the point: duplicate it to try another <Explain term="hook" iconOnly /> or angle.</>} testid="idea-editor">
      {body}
    </Panel>
  );
}

// ---------- Quick capture ----------
export function QuickCapture({ onAdded }: { onAdded: () => void }) {
  const [title, setTitle] = React.useState("");
  const [note, setNote] = React.useState("");
  const [category, setCategory] = React.useState<string | null>(null);
  const [similar, setSimilar] = React.useState<Similar[]>([]);
  const [blocked, setBlocked] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    if (title.trim().length < 4) return;
    let alive = true;
    const t = setTimeout(() => {
      v2.checkDuplicate({ title: title.trim(), note: note || null })
        .then((r) => alive && setSimilar(r.similar ?? []))
        .catch(() => {});
    }, 400);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [title, note]);

  const shown = title.trim().length < 4 && !blocked ? [] : similar;
  const submit = async (force: boolean) => {
    if (!title.trim()) return;
    setBusy(true);
    try {
      await v2.quickIdea({ title: title.trim(), note: note.trim() || null, category, force });
      toast.success("Idea saved");
      setTitle("");
      setNote("");
      setSimilar([]);
      setBlocked(false);
      onAdded();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        const body = e.body as { error?: { similar?: Similar[] } } | null;
        setSimilar(body?.error?.similar ?? []);
        setBlocked(true);
      } else toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="relative">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          submit(false);
        }}
        className="flex flex-col gap-2"
      >
        <div className="flex gap-2">
          <Input
            aria-label="Idea title"
            placeholder="Quick add: saw something while scrolling? Drop it here"
            value={title}
            onChange={(e) => {
              setTitle(e.target.value);
              setBlocked(false);
            }}
            className="h-9"
          />
          <Button type="submit" className="h-9" disabled={busy || !title.trim()}>
            <Plus /> Add
          </Button>
        </div>
        {title && (
          <div className="z-20 flex flex-col gap-2 rounded-xl border border-line bg-panel p-2 shadow-lg md:absolute md:inset-x-0 md:top-11">
            <Input aria-label="Note" placeholder="Optional note (link, angle, example)" value={note} onChange={(e) => setNote(e.target.value)} />
            <div className="flex flex-wrap gap-1.5">
              {CATEGORIES.map((c) => (
                <Chip key={c} active={category === c} onClick={() => setCategory(category === c ? null : c)}>
                  {catLabel(c)}
                </Chip>
              ))}
            </div>
            {shown.length > 0 && (
              <div role="alert" className="rounded-md border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-100">
                <p className="font-medium">{blocked ? "Looks similar to something you already have:" : "Similar:"}</p>
                <ul className="mt-1 list-disc pl-5 text-amber-700 dark:text-amber-100/90">
                  {shown.slice(0, 3).map((s) => (
                    <li key={`${s.kind}-${s.id}`}>
                      {s.text.length > 90 ? s.text.slice(0, 90) + "…" : s.text} <span className="text-xs text-amber-700 dark:text-amber-200/70">({s.kind === "post" ? "already posted" : "in your ideas"})</span>
                    </li>
                  ))}
                </ul>
                {blocked && (
                  <Button size="sm" variant="outline" className="mt-2 border-amber-500/40" onClick={() => submit(true)} disabled={busy}>
                    Add anyway
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </form>
    </div>
  );
}

// ---------- Board ----------
function useMove(onChange: () => void) {
  return React.useCallback(
    async (id: number, status: string) => {
      try {
        await v2.updateIdea(id, { status });
        toast.success(`Moved to ${STAGE_LABEL[status] ?? status}`);
        onChange();
      } catch (e) {
        toast.error(errorMessage(e));
      }
    },
    [onChange],
  );
}

export function BoardView({ board, onChange, onOpen, hideFilter, search }: { board: Board; onChange: () => void; onOpen: (id: number) => void; hideFilter?: boolean; search?: (i: BoardItem) => boolean }) {
  const [filter, setFilter] = React.useState<string | null>(null);
  const [over, setOver] = React.useState<string | null>(null);
  const move = useMove(onChange);
  const cols = STAGES.map((s) => board.columns.find((c) => c.status === s) ?? { status: s, items: [] });
  return (
    <div className="flex flex-col md:h-full md:min-h-0">
      <div className={cn("mb-4 flex flex-wrap gap-1.5", hideFilter && "hidden")} aria-label="Filter by topic">
        <Chip active={!filter} onClick={() => setFilter(null)}>
          All
        </Chip>
        {(board.categories.length ? board.categories : [...CATEGORIES]).map((c) => (
          <Chip key={c} active={filter === c} onClick={() => setFilter(filter === c ? null : c)}>
            {catLabel(c)}
          </Chip>
        ))}
      </div>
      <div className="thin-scroll -mx-4 flex snap-x gap-3 overflow-x-auto px-4 pb-2 md:mx-0 md:min-h-0 md:flex-1 md:px-0">
        {cols.map((col) => {
          const items = col.items.filter((i) => (!filter || i.category === filter) && (!search || search(i)));
          return (
            <div
              key={col.status}
              data-testid={`col-${col.status}`}
              onDragOver={(e) => {
                e.preventDefault();
                setOver(col.status);
              }}
              onDragLeave={() => setOver(null)}
              onDrop={(e) => {
                e.preventDefault();
                setOver(null);
                const id = Number(e.dataTransfer.getData("text/plain"));
                const from = cols.find((c) => c.items.some((i) => i.id === id))?.status;
                if (id && from !== col.status) move(id, col.status);
              }}
              className={cn("thin-scroll flex w-60 shrink-0 snap-start flex-col gap-2 rounded-2xl border border-line bg-panel-2/50 p-2 md:min-h-0 md:overflow-y-auto", over === col.status && "border-accent bg-accent/5")}
            >
              <div className="flex items-center justify-between px-1.5 py-1">
                <h3 className="text-sm font-medium">{STAGE_LABEL[col.status]}</h3>
                <span className="text-xs text-muted">{items.length}</span>
              </div>
              {items.map((it) => (
                <IdeaCard key={it.id} item={it} status={col.status} onOpen={() => onOpen(it.id)} onMove={move} />
              ))}
              {items.length === 0 && <p className="px-1.5 py-4 text-center text-xs text-muted/70">Drop here</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function IdeaCard({ item, status, onOpen, onMove }: { item: BoardItem; status: string; onOpen: () => void; onMove: (id: number, s: string) => void }) {
  const next = nextStage(status);
  return (
    <article
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(item.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      className="group shrink-0 cursor-grab rounded-xl border border-line bg-panel p-3 shadow-sm active:cursor-grabbing"
    >
      <button type="button" onClick={onOpen} className="block w-full text-left">
        <p className="text-sm font-medium leading-snug">{item.title}</p>
        {item.hook && item.hook !== item.title && <p className="mt-1 line-clamp-2 text-xs text-muted">“{item.hook}”</p>}
      </button>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {item.category && <Badge>{catLabel(item.category)}</Badge>}
        {item.audience && <Badge tone="violet" title={item.audience_inferred ? "Auto-tagged from the topic; change it in the idea" : "Set by you"}>{audLabel(item.audience)}</Badge>}
        {item.shareability != null && (
          <Badge tone={item.shareability >= 65 ? "green" : item.shareability >= 45 ? "amber" : "neutral"} title="Shareability: how 'send-to-a-friend' the wording is (an estimate, not a prediction)">
            Share {item.shareability}
          </Badge>
        )}
        {item.planned_at && (
          <span className="inline-flex items-center gap-1 text-[11px] text-muted">
            <CalendarDays className="size-3" />
            {fmtSlot(item.planned_at).replace(" IST", "")}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-center justify-between gap-1">
        <Select aria-label={`Stage for ${item.title}`} value={status} onChange={(e) => onMove(item.id, e.target.value)} className="h-7 w-auto px-2 text-xs">
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {STAGE_LABEL[s]}
            </option>
          ))}
        </Select>
        {next && (
          <Button size="sm" variant="ghost" aria-label={`Move ${item.title} to ${STAGE_LABEL[next]}`} onClick={() => onMove(item.id, next)}>
            {STAGE_LABEL[next]} <ArrowRight />
          </Button>
        )}
      </div>
    </article>
  );
}

// ---------- Week ----------
function WeekView({ board, onChange, onOpen }: { board: Board; onChange: () => void; onOpen: (id: number) => void }) {
  const [start, setStart] = React.useState(() => mondayOf(todayISO()));
  const week = useApi(() => v2.week(start), [start]);
  const [pickDay, setPickDay] = React.useState<string | null>(null);
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  const byDay = (d: string) => (week.data?.items ?? []).filter((i) => istWall(i.scheduled_at)?.slice(0, 10) === d);
  const today = todayISO();

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Button size="icon" variant="ghost" aria-label="Previous week" onClick={() => setStart(addDays(start, -7))}>
          <ChevronLeft />
        </Button>
        <span className="text-sm font-medium">Week of {dayName(start)}</span>
        <Button size="icon" variant="ghost" aria-label="Next week" onClick={() => setStart(addDays(start, 7))}>
          <ChevronRight />
        </Button>
      </div>
      <p className="mb-4 text-xs text-muted">You&apos;ll get a reminder on Home 1 hour before each planned post.</p>
      {week.error && <ErrorState message={week.error} onRetry={week.reload} />}
      <div className="grid gap-2 md:grid-cols-7">
        {days.map((d) => {
          const items = byDay(d);
          return (
            <div key={d} className={cn("min-h-28 rounded-xl border border-line bg-panel p-2", d === today && "border-accent/60")}>
              <p className={cn("mb-2 text-xs", d === today ? "font-semibold text-accent" : "text-muted")}>{dayName(d)}</p>
              {items.map((i: WeekItem) => (
                <button key={i.id} type="button" onClick={() => i.idea_id && onOpen(i.idea_id)} className="mb-1.5 block w-full rounded-md bg-panel-2 p-2 text-left text-xs hover:ring-1 hover:ring-accent/60">
                  <span className="text-muted">{istWall(i.scheduled_at)?.slice(11)}</span> {i.title}
                  <span className="mt-1 block text-[10px] text-muted">{i.published ? "Published" : STAGE_LABEL[i.status] ?? i.status}</span>
                </button>
              ))}
              {items.length === 0 && (
                <button type="button" onClick={() => setPickDay(d)} className="w-full rounded-md border border-dashed border-line py-2 text-xs text-muted hover:text-fg">
                  + plan
                </button>
              )}
            </div>
          );
        })}
      </div>
      {pickDay && (
        <PlanPicker
          day={pickDay}
          board={board}
          onClose={() => setPickDay(null)}
          onDone={() => {
            setPickDay(null);
            week.reload();
            onChange();
          }}
        />
      )}
    </div>
  );
}

function PlanList({ items, onPick }: { items: (BoardItem & { status: string })[]; onPick: (id: number) => void }) {
  return (
    <ul className="flex flex-col gap-1.5">
      {items.map((i) => (
        <li key={i.id}>
          <button type="button" onClick={() => onPick(i.id)} className="flex w-full items-center justify-between gap-2 rounded-md border border-line p-2 text-left text-sm hover:border-accent">
            <span>{i.title}</span>
            <Badge>{STAGE_LABEL[i.status]}</Badge>
          </button>
        </li>
      ))}
    </ul>
  );
}

function PlanPicker({ day, board, onClose, onDone }: { day: string; board: Board; onClose: () => void; onDone: () => void }) {
  const aud = useApi(() => v3.audience().catch(() => null), []);
  const timeHint = bestTimeHint(aud.data);
  const best = aud.data?.best_times?.[0]?.hour;
  const [time, setTime] = React.useState<string | null>(null);
  const when = time ?? (best !== undefined ? `${String((best + 23) % 24).padStart(2, "0")}:30` : "19:00");
  const candidates = board.columns.filter((c) => c.status === "ready" || c.status === "editing").flatMap((c) => c.items.map((i) => ({ ...i, status: c.status })));
  const others = board.columns.filter((c) => ["idea", "script", "recording"].includes(c.status)).flatMap((c) => c.items.map((i) => ({ ...i, status: c.status })));
  const plan = async (id: number) => {
    try {
      await v2.plan(id, `${day}T${when}:00`);
      toast.success(`Planned for ${dayName(day)}, ${when}`);
      onDone();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={`Plan a post for ${dayName(day)}`} description="Pick an idea that's nearly done.">
      {timeHint && <p className="mb-3 text-xs text-muted" data-testid="plan-best-time">{timeHint}</p>}
      <Field label="Time (IST)" htmlFor="plan-time" className="mb-4">
        <Input id="plan-time" type="time" value={when} onChange={(e) => setTime(e.target.value)} />
      </Field>
      {candidates.length ? <PlanList items={candidates} onPick={plan} /> : <p className="text-sm text-muted">Nothing is in Editing or Ready yet.</p>}
      {others.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs text-muted">Earlier-stage ideas</summary>
          <div className="mt-2">
            <PlanList items={others} onPick={plan} />
          </div>
        </details>
      )}
    </Dialog>
  );
}

// ---------- Side sheet (board / week) ----------
function IdeaSheet({ id, onClose, onChange, onDelete }: { id: number; onClose: () => void; onChange: () => void; onDelete: (ids: number[]) => void }) {
  const q = useApi(() => v2.idea(id), [id]);
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} side="right" title={q.data?.title ?? "Idea"} className="max-w-lg">
      {q.loading && !q.data && <Loading />}
      {q.error && <ErrorState message={q.error} onRetry={q.reload} />}
      {q.data && (
        <IdeaEditor
          idea={q.data}
          inSheet
          onChange={onChange}
          onDelete={(ids) => {
            onDelete(ids);
            onClose();
          }}
        />
      )}
    </Dialog>
  );
}
