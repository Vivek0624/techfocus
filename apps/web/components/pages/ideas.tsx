"use client";
import * as React from "react";
import { toast } from "sonner";
import { ArrowDown, ArrowUp, Copy, Download, Pencil, Plus, Trash2 } from "lucide-react";
import { api, CONTENT_STATUSES, errorMessage, type ContentIdea } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDateTime, fmtSlot, humanize } from "@/lib/utils";
import { Card } from "@/components/ui/card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { ContentForm } from "@/components/content-form";
import { useDataChanged } from "@/components/shell";

const PAGE_SIZE = 20;
type SortKey = "updated" | "created" | "title" | "status";

export function IdeasPage() {
  const [search, setSearch] = React.useState("");
  const [debounced, setDebounced] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [pillar, setPillar] = React.useState("");
  const [sort, setSort] = React.useState<SortKey>("updated");
  const [order, setOrder] = React.useState<"asc" | "desc">("desc");
  const [page, setPage] = React.useState(1);
  const [editing, setEditing] = React.useState<ContentIdea | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleting, setDeleting] = React.useState<ContentIdea | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    const t = setTimeout(() => {
      setDebounced(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(t);
  }, [search]);

  const list = useApi(
    () => api.content({ search: debounced, status, pillar, sort, order, page, page_size: PAGE_SIZE }),
    [debounced, status, pillar, sort, order, page],
  );
  useDataChanged(list.reload);
  const pillars = useApi(() => api.content({ page_size: 100 }).then((p) => Array.from(new Set(p.items.map((i) => i.pillar).filter(Boolean))) as string[]), []);

  const toggleSort = (k: SortKey) => {
    if (sort === k) setOrder(order === "asc" ? "desc" : "asc");
    else {
      setSort(k);
      setOrder(k === "title" ? "asc" : "desc");
    }
  };
  const sortTh = (k: SortKey, children: React.ReactNode) => (
    <Th>
      <button type="button" className="inline-flex items-center gap-1 hover:text-fg" onClick={() => toggleSort(k)} aria-label={`Sort by ${k}`}>
        {children}
        {sort === k && (order === "asc" ? <ArrowUp className="size-3" /> : <ArrowDown className="size-3" />)}
      </button>
    </Th>
  );

  const clone = async (c: ContentIdea) => {
    try {
      await api.contentClone(c.id);
      toast.success("Idea cloned");
      list.reload();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const remove = async () => {
    if (!deleting) return;
    setBusy(true);
    try {
      await api.contentDelete(deleting.id);
      toast.success("Idea deleted");
      setDeleting(null);
      list.reload();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const data = list.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1;

  return (
    <div>
      <PageHeader
        title="Content Ideas"
        description="Your idea library: from rough idea to published reel."
        actions={
          <>
            <a className={buttonVariants({ variant: "outline", size: "sm" })} href={api.contentExportUrl("csv")} download>
              <Download /> CSV
            </a>
            <a className={buttonVariants({ variant: "outline", size: "sm" })} href={api.contentExportUrl("json")} download>
              <Download /> JSON
            </a>
            <Button onClick={() => setCreating(true)}>
              <Plus /> New idea
            </Button>
          </>
        }
      />
      <Card>
        <div className="flex flex-wrap gap-2 border-b border-line p-3">
          <Input aria-label="Search ideas" placeholder="Search title, hook, caption…" value={search} onChange={(e) => setSearch(e.target.value)} className="max-w-xs" />
          <Select aria-label="Filter by status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="w-40">
            <option value="">All statuses</option>
            {CONTENT_STATUSES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </Select>
          <Select aria-label="Filter by pillar" value={pillar} onChange={(e) => { setPillar(e.target.value); setPage(1); }} className="w-52">
            <option value="">All pillars</option>
            {(pillars.data ?? []).map((p) => (
              <option key={p} value={p}>{humanize(p)}</option>
            ))}
          </Select>
        </div>
        {list.loading && !data && <Loading />}
        {list.error && <ErrorState message={list.error} onRetry={list.reload} />}
        {data && data.items.length === 0 && (
          <EmptyState title="No ideas found">
            <p>{debounced || status || pillar ? "Try clearing the filters." : "Create one, or generate a package in Reel Studio."}</p>
          </EmptyState>
        )}
        {data && data.items.length > 0 && (
          <>
            <Table>
              <thead>
                <tr>
                  {sortTh("title", "Title")}
                  <Th>Pillar</Th>
                  <Th>Format</Th>
                  {sortTh("status", "Status")}
                  <Th>Planned</Th>
                  {sortTh("updated", "Updated")}
                  <Th className="text-right">Actions</Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => (
                  <tr key={c.id} className="hover:bg-panel-2/50">
                    <Td className="max-w-sm">
                      <button type="button" className="text-left hover:underline" onClick={() => setEditing(c)}>
                        {c.title}
                      </button>
                      {c.is_demo && <Badge tone="amber" className="ml-2">DEMO</Badge>}
                      {c.recommended_hook && <div className="truncate text-xs text-muted">{c.recommended_hook}</div>}
                    </Td>
                    <Td>{humanize(c.pillar)}</Td>
                    <Td>{humanize(c.format)}</Td>
                    <Td><StatusBadge status={c.status} /></Td>
                    <Td className="whitespace-nowrap text-xs">{fmtSlot(c.planned_at)}</Td>
                    <Td className="whitespace-nowrap text-xs">{fmtDateTime(c.updated_at)}</Td>
                    <Td className="text-right whitespace-nowrap">
                      <Button size="icon" variant="ghost" aria-label={`Edit ${c.title}`} onClick={() => setEditing(c)}><Pencil /></Button>
                      <Button size="icon" variant="ghost" aria-label={`Clone ${c.title}`} onClick={() => clone(c)}><Copy /></Button>
                      <Button size="icon" variant="ghost" aria-label={`Delete ${c.title}`} onClick={() => setDeleting(c)}><Trash2 /></Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
            <div className="flex items-center justify-between p-3 text-sm text-muted">
              <span>{data.total} ideas · page {data.page} of {pages}</span>
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <Button size="sm" variant="outline" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            </div>
          </>
        )}
      </Card>

      <Dialog open={creating} onOpenChange={setCreating} title="New content idea" side="right">
        {creating && (
          <ContentForm
            submitLabel="Create idea"
            onCancel={() => setCreating(false)}
            onSubmit={async (payload) => {
              try {
                await api.contentCreate(payload);
                toast.success("Idea created");
                setCreating(false);
                list.reload();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}
          />
        )}
      </Dialog>

      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)} title={editing ? `Edit: ${editing.title}` : "Edit"} side="right">
        {editing && (
          <ContentForm
            key={editing.id}
            initial={editing}
            onCancel={() => setEditing(null)}
            onSubmit={async (payload) => {
              try {
                await api.contentUpdate(editing.id, payload);
                toast.success("Idea saved");
                setEditing(null);
                list.reload();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}
          />
        )}
      </Dialog>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete idea?"
        description={deleting ? `"${deleting.title}" will be permanently deleted.` : undefined}
        confirmLabel="Delete"
        destructive
        busy={busy}
        onConfirm={remove}
      />
    </div>
  );
}
