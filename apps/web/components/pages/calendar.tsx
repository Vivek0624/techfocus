"use client";
import * as React from "react";
import { useForm, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight, ClipboardList, Plus, Send, Trash2 } from "lucide-react";
import { ApiError, api, CONTENT_FORMATS, errorMessage, type Approval, type CalendarCreate, type CalendarItem, type ContentIdea } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { addDays, cn, fmtDateTime, fmtSlot, istWall, todayISO, weekday } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { JsonView, PageHeader } from "@/components/page-header";
import { useDataChanged } from "@/components/shell";

const PRODUCTION = ["planned", "scripting", "production", "ready"];
type View = "day" | "week" | "month";

// ---------- form ----------
const calSchema = z.object({
  title: z.string().trim().min(1, "Title is required").max(200),
  idea_id: z.string(),
  format: z.enum(["", ...CONTENT_FORMATS]),
  scheduled_at: z.string().regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/, "Pick a date and time"),
  caption: z.string().max(2200, "Caption must be 2200 characters or fewer"),
  asset_ref: z.string().max(1000),
  production_status: z.string(),
});
type CalValues = z.infer<typeof calSchema>;

export function calendarPayload(v: CalValues): CalendarCreate {
  return {
    title: v.title.trim(),
    idea_id: v.idea_id ? Number(v.idea_id) : null,
    format: v.format || null,
    // IST wall-clock, sent naive: the API interprets naive times as Asia/Kolkata.
    scheduled_at: v.scheduled_at.length === 16 ? `${v.scheduled_at}:00` : v.scheduled_at,
    caption: v.caption.trim() || null,
    asset_ref: v.asset_ref.trim() || null,
    production_status: v.production_status,
  };
}

export function CalendarForm({
  initial,
  ideas,
  defaultDate,
  onSubmit,
  submitLabel = "Save",
}: {
  initial?: CalendarItem | null;
  ideas: ContentIdea[];
  defaultDate?: string;
  onSubmit: (p: CalendarCreate) => Promise<void> | void;
  submitLabel?: string;
}) {
  const {
    register,
    handleSubmit,
    setValue,
    control,
    formState: { errors, isSubmitting },
  } = useForm<CalValues>({
    resolver: zodResolver(calSchema),
    defaultValues: {
      title: initial?.title ?? "",
      idea_id: initial?.idea_id ? String(initial.idea_id) : "",
      format: (initial?.format as CalValues["format"]) ?? "",
      scheduled_at: istWall(initial?.scheduled_at) ?? (defaultDate ? `${defaultDate}T19:00` : ""),
      caption: initial?.caption ?? "",
      asset_ref: initial?.asset_ref ?? "",
      production_status: initial?.production_status ?? "planned",
    },
  });
  const caption = useWatch({ control, name: "caption" }) ?? "";
  const ideaId = useWatch({ control, name: "idea_id" });
  const fromIdea = (id: string) => {
    setValue("idea_id", id);
    const idea = ideas.find((i) => String(i.id) === id);
    if (!idea) return;
    setValue("title", idea.title, { shouldValidate: true });
    if (idea.format) setValue("format", idea.format);
    if (idea.caption) setValue("caption", idea.caption);
  };
  return (
    <form onSubmit={handleSubmit((v) => onSubmit(calendarPayload(v)))} className="flex flex-col gap-4" noValidate aria-label="Calendar item form">
      {!initial && (
        <Field label="From idea (optional)" htmlFor="idea_id">
          <Select id="idea_id" value={ideaId} onChange={(e) => fromIdea(e.target.value)}>
            <option value="">— none —</option>
            {ideas.map((i) => (
              <option key={i.id} value={i.id}>
                {i.title}
              </option>
            ))}
          </Select>
        </Field>
      )}
      <Field label="Title *" htmlFor="cal-title" error={errors.title?.message}>
        <Input id="cal-title" {...register("title")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Scheduled at (IST) *" htmlFor="scheduled_at" error={errors.scheduled_at?.message}>
          <Input id="scheduled_at" type="datetime-local" {...register("scheduled_at")} />
        </Field>
        <Field label="Format" htmlFor="cal-format">
          <Select id="cal-format" {...register("format")}>
            <option value="">—</option>
            {CONTENT_FORMATS.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </Select>
        </Field>
      </div>
      <Field label="Caption" htmlFor="cal-caption" error={errors.caption?.message} hint={`${caption.length}/2200`}>
        <Textarea id="cal-caption" rows={4} {...register("caption")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Asset reference (public video URL)" htmlFor="asset_ref">
          <Input id="asset_ref" {...register("asset_ref")} />
        </Field>
        <Field label="Production status" htmlFor="production_status">
          <Select id="production_status" {...register("production_status")}>
            {PRODUCTION.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </Select>
        </Field>
      </div>
      <div className="flex justify-end">
        <Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving…" : submitLabel}</Button>
      </div>
    </form>
  );
}

// ---------- page ----------
function rangeFor(view: View, anchor: string): { start: string; end: string; days: string[] } {
  if (view === "day") return { start: anchor, end: addDays(anchor, 1), days: [anchor] };
  if (view === "week") {
    const s = addDays(anchor, -((weekday(anchor) + 6) % 7));
    const days = Array.from({ length: 7 }, (_, i) => addDays(s, i));
    return { start: s, end: addDays(s, 7), days };
  }
  const first = `${anchor.slice(0, 7)}-01`;
  const s = addDays(first, -((weekday(first) + 6) % 7));
  const days = Array.from({ length: 42 }, (_, i) => addDays(s, i));
  return { start: s, end: addDays(s, 42), days };
}

function shift(view: View, anchor: string, dir: number) {
  if (view === "day") return addDays(anchor, dir);
  if (view === "week") return addDays(anchor, 7 * dir);
  const [y, m] = anchor.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + dir, 1));
  return d.toISOString().slice(0, 10);
}

export function CalendarPage() {
  const [view, setView] = React.useState<View>("week");
  const [anchor, setAnchor] = React.useState(todayISO());
  const { start, end, days } = rangeFor(view, anchor);
  const items = useApi(() => api.calendar({ start, end }), [start, end]);
  const ideas = useApi(() => api.content({ page_size: 100 }).then((p) => p.items), []);
  const approvals = useApi(() => api.approvals(), []);
  useDataChanged(() => {
    items.reload();
    approvals.reload();
  });
  const [creating, setCreating] = React.useState<string | null>(null);
  const [selected, setSelected] = React.useState<CalendarItem | null>(null);
  const today = todayISO();

  const byDay = React.useMemo(() => {
    const m: Record<string, CalendarItem[]> = {};
    for (const it of items.data ?? []) {
      const d = (istWall(it.scheduled_at) ?? "").slice(0, 10);
      (m[d] ??= []).push(it);
    }
    return m;
  }, [items.data]);

  const title =
    view === "month"
      ? new Date(`${anchor.slice(0, 7)}-01T00:00:00Z`).toLocaleString("en-IN", { month: "long", year: "numeric", timeZone: "UTC" })
      : view === "week"
        ? `${days[0]} → ${days[6]}`
        : anchor;

  const chip = (it: CalendarItem) => (
    <button
      key={it.id}
      type="button"
      onClick={() => setSelected(it)}
      className="w-full truncate rounded border border-line bg-panel-2 px-1.5 py-1 text-left text-xs hover:border-accent"
      title={it.title}
    >
      <span className="text-muted">{(istWall(it.scheduled_at) ?? "").slice(11, 16)}</span> {it.title}
    </button>
  );

  return (
    <div>
      <PageHeader
        title="Content Calendar"
        description="All times in Asia/Kolkata (IST)."
        actions={
          <Button onClick={() => setCreating(view === "day" ? anchor : today)}>
            <Plus /> New item
          </Button>
        }
      />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line p-3">
          <div className="flex items-center gap-2">
            <Button size="icon" variant="outline" aria-label="Previous" onClick={() => setAnchor(shift(view, anchor, -1))}><ChevronLeft /></Button>
            <Button size="sm" variant="outline" onClick={() => setAnchor(today)}>Today</Button>
            <Button size="icon" variant="outline" aria-label="Next" onClick={() => setAnchor(shift(view, anchor, 1))}><ChevronRight /></Button>
            <span className="ml-2 text-sm font-medium">{title}</span>
          </div>
          <div className="flex gap-1" role="group" aria-label="Calendar view">
            {(["day", "week", "month"] as View[]).map((v) => (
              <Button key={v} size="sm" variant={view === v ? "default" : "outline"} onClick={() => setView(v)}>
                {v[0].toUpperCase() + v.slice(1)}
              </Button>
            ))}
          </div>
        </div>
        {items.loading && !items.data && <Loading />}
        {items.error && <ErrorState message={items.error} onRetry={items.reload} />}
        {items.data && view === "day" && (
          <CardBody>
            {(byDay[anchor] ?? []).length === 0 ? (
              <EmptyState title="Nothing scheduled this day" />
            ) : (
              <div className="flex flex-col gap-2">
                {byDay[anchor].map((it) => (
                  <button key={it.id} type="button" onClick={() => setSelected(it)} className="flex items-center justify-between gap-2 rounded-md border border-line p-3 text-left hover:border-accent">
                    <div>
                      <div className="font-medium">{it.title}</div>
                      <div className="text-xs text-muted">{fmtSlot(it.scheduled_at)} · {it.format ?? "—"}</div>
                    </div>
                    <div className="flex gap-1">
                      <StatusBadge status={it.production_status} />
                      <StatusBadge status={it.approval_status} />
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardBody>
        )}
        {items.data && view !== "day" && (
          <div className="overflow-x-auto">
            <div className="grid min-w-[720px] grid-cols-7">
              {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
                <div key={d} className="border-b border-line px-2 py-1.5 text-xs text-muted">{d}</div>
              ))}
              {days.map((d) => {
                const out = view === "month" && d.slice(0, 7) !== anchor.slice(0, 7);
                return (
                  <div
                    key={d}
                    className={cn("flex flex-col gap-1 border-b border-r border-line/60 p-1.5", view === "week" ? "min-h-48" : "min-h-24", out && "opacity-40")}
                    data-day={d}
                  >
                    <button type="button" className={cn("self-start rounded px-1 text-xs", d === today ? "bg-accent text-white" : "text-muted hover:text-fg")} onClick={() => { setAnchor(d); setView("day"); }}>
                      {Number(d.slice(8))}
                    </button>
                    {(byDay[d] ?? []).map((it) => (
                      chip(it)
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </Card>

      <ApprovalsCard approvals={approvals.data} loading={approvals.loading} error={approvals.error} reload={() => { approvals.reload(); items.reload(); }} />

      <Dialog open={creating !== null} onOpenChange={(o) => !o && setCreating(null)} title="New calendar item" side="right">
        {creating !== null && (
          <CalendarForm
            ideas={ideas.data ?? []}
            defaultDate={creating}
            submitLabel="Create item"
            onSubmit={async (p) => {
              try {
                await api.calendarCreate(p);
                toast.success("Calendar item created");
                setCreating(null);
                items.reload();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}
          />
        )}
      </Dialog>

      {selected && (
        <ItemDialog
          item={selected}
          ideas={ideas.data ?? []}
          onClose={() => setSelected(null)}
          onChanged={() => {
            items.reload();
            approvals.reload();
          }}
        />
      )}
    </div>
  );
}

function ItemDialog({ item, ideas, onClose, onChanged }: { item: CalendarItem; ideas: ContentIdea[]; onClose: () => void; onChanged: () => void }) {
  const [tab, setTab] = React.useState<"details" | "edit">("details");
  const [preview, setPreview] = React.useState<Record<string, unknown> | null>(null);
  const [problems, setProblems] = React.useState<{ message: string; problems: string[] } | null>(null);
  const [checklist, setChecklist] = React.useState<{ item: string; steps: string[]; caption: string | null } | null>(null);
  const [confirmDelete, setConfirmDelete] = React.useState(false);
  const [busy, setBusy] = React.useState(false);

  const requestPublish = async () => {
    setBusy(true);
    setProblems(null);
    setPreview(null);
    try {
      const res = await api.requestPublish(item.id);
      setPreview(res);
      toast.success("Publish approval requested");
      onChanged();
    } catch (e) {
      if (e instanceof ApiError && e.status === 422) setProblems({ message: e.message, problems: e.problems });
      else toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  const loadChecklist = async () => {
    try {
      setChecklist(await api.manualChecklist(item.id));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api.calendarDelete(item.id);
      toast.success("Item deleted");
      onChanged();
      onClose();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()} title={item.title} description={fmtSlot(item.scheduled_at)} side="right">
      <div className="mb-4 flex gap-1">
        <Button size="sm" variant={tab === "details" ? "default" : "outline"} onClick={() => setTab("details")}>Details</Button>
        <Button size="sm" variant={tab === "edit" ? "default" : "outline"} onClick={() => setTab("edit")}>Edit</Button>
      </div>
      {tab === "edit" ? (
        <CalendarForm
          initial={item}
          ideas={ideas}
          onSubmit={async (p) => {
            try {
              await api.calendarUpdate(item.id, { title: p.title, format: p.format, scheduled_at: p.scheduled_at, caption: p.caption, asset_ref: p.asset_ref, production_status: p.production_status });
              toast.success("Item updated");
              onChanged();
              onClose();
            } catch (e) {
              toast.error(errorMessage(e));
            }
          }}
        />
      ) : (
        <div className="flex flex-col gap-4 text-sm">
          <div className="grid grid-cols-3 gap-3">
            <div><div className="text-xs text-muted">Production</div><StatusBadge status={item.production_status} /></div>
            <div><div className="text-xs text-muted">Approval</div><StatusBadge status={item.approval_status} /></div>
            <div><div className="text-xs text-muted">Publishing</div><StatusBadge status={item.publishing_status} /></div>
          </div>
          {item.is_demo && <Badge tone="amber" className="self-start">DEMO item — cannot be published</Badge>}
          <div><div className="text-xs text-muted">Format</div>{item.format ?? "—"}</div>
          <div><div className="text-xs text-muted">Asset</div>{item.asset_ref ?? <span className="text-muted">none attached</span>}</div>
          <div><div className="text-xs text-muted">Caption</div><p className="whitespace-pre-wrap">{item.caption ?? "—"}</p></div>
          {item.published_at && <div><div className="text-xs text-muted">Published</div>{fmtDateTime(item.published_at)} · {item.published_media_id}</div>}
          <div className="flex flex-wrap gap-2 border-t border-line pt-4">
            <Button onClick={requestPublish} disabled={busy}><Send /> Request publish approval</Button>
            <Button variant="outline" onClick={loadChecklist}><ClipboardList /> Manual post checklist</Button>
            <Button variant="destructive" onClick={() => setConfirmDelete(true)}><Trash2 /> Delete</Button>
          </div>
          {problems && <ErrorState message={problems.message} problems={problems.problems} />}
          {preview && (
            <div>
              <p className="mb-1 text-xs font-medium text-muted">Approval requested — preview</p>
              <JsonView value={preview} />
            </div>
          )}
          {checklist && (
            <div className="rounded-md border border-line p-3">
              <p className="mb-2 font-medium">Manual post checklist: {checklist.item}</p>
              <ol className="list-decimal pl-5">
                {checklist.steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
              {checklist.caption && (
                <>
                  <p className="mt-3 text-xs text-muted">Caption to paste</p>
                  <pre className="whitespace-pre-wrap rounded bg-bg p-2 text-xs">{checklist.caption}</pre>
                </>
              )}
            </div>
          )}
        </div>
      )}
      <ConfirmDialog open={confirmDelete} onOpenChange={setConfirmDelete} title="Delete calendar item?" description={`"${item.title}" will be removed from the calendar.`} confirmLabel="Delete" destructive busy={busy} onConfirm={remove} />
    </Dialog>
  );
}

function ApprovalsCard({ approvals, loading, error, reload }: { approvals: Approval[] | null; loading: boolean; error: string | null; reload: () => void }) {
  const [executing, setExecuting] = React.useState<Approval | null>(null);
  const [busy, setBusy] = React.useState(false);
  const decide = async (a: Approval, approve: boolean) => {
    try {
      await api.decide(a.id, approve);
      toast.success(approve ? "Approved" : "Rejected");
      reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const execute = async () => {
    if (!executing) return;
    setBusy(true);
    try {
      await api.executeApproval(executing.id);
      toast.success("Published via Instagram API");
      setExecuting(null);
      reload();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card className="mt-6">
      <CardHeader title="Approvals" description="Nothing is published without an explicit approval." />
      {loading && !approvals && <Loading />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {approvals && approvals.length === 0 && <EmptyState title="No approval requests" />}
      {approvals && approvals.length > 0 && (
        <Table>
          <thead>
            <tr>
              <Th>Request</Th>
              <Th>Action</Th>
              <Th>Status</Th>
              <Th>Created</Th>
              <Th className="text-right">Decision</Th>
            </tr>
          </thead>
          <tbody>
            {approvals.map((a) => (
              <tr key={a.id}>
                <Td className="max-w-md">{a.summary}<div className="text-xs text-muted">{a.target_type} #{a.target_id} · by {a.requested_by}</div></Td>
                <Td>{a.action}</Td>
                <Td><StatusBadge status={a.status} /></Td>
                <Td className="whitespace-nowrap text-xs">{fmtDateTime(a.created_at)}</Td>
                <Td className="whitespace-nowrap text-right">
                  {a.status === "pending" && (
                    <div className="flex justify-end gap-1">
                      <Button size="sm" onClick={() => decide(a, true)}>Approve</Button>
                      <Button size="sm" variant="outline" onClick={() => decide(a, false)}>Reject</Button>
                    </div>
                  )}
                  {a.status === "approved" && <Button size="sm" onClick={() => setExecuting(a)}><Send /> Publish via API</Button>}
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      )}
      <ConfirmDialog
        open={!!executing}
        onOpenChange={(o) => !o && setExecuting(null)}
        title="Publish to Instagram now?"
        description="This posts publicly to your connected Instagram account via the API. It cannot be undone from this app."
        confirmLabel="Yes, publish now"
        busy={busy}
        onConfirm={execute}
      >
        {executing && (
          <div className="text-sm">
            <p className="font-medium">{executing.summary}</p>
            <JsonView value={executing.payload} />
          </div>
        )}
      </ConfirmDialog>
    </Card>
  );
}
