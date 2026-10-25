"use client";
import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Pencil, Play, Plus, Trash2 } from "lucide-react";
import { api, errorMessage, EVIDENCE_LEVELS, type Persona, type PersonaIn } from "@/lib/api";
import { useApi, useRunPoller } from "@/lib/hooks";
import { splitList } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { JsonView, PageHeader } from "@/components/page-header";
import { useDataChanged } from "@/components/shell";
import { RunStatusLine } from "./agents";

const LEVEL_INFO: Record<string, { title: string; note: string; tone: "green" | "blue" | "amber" }> = {
  verified: { title: "Verified", note: "Backed by observed data (e.g. comments, DMs, your own insights).", tone: "green" },
  inferred: { title: "Inferred", note: "Inferred from content performance and comments — NOT Instagram demographics.", tone: "blue" },
  hypothesis: { title: "Hypothesis", note: "A guess to test — NOT Instagram demographics and not yet supported by data.", tone: "amber" },
};

const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(120),
  evidence_level: z.enum(EVIDENCE_LEVELS),
  interests: z.string(),
  problems: z.string(),
  angles: z.string(),
  notes: z.string(),
});
type V = z.infer<typeof schema>;

function PersonaForm({ initial, onSubmit }: { initial?: Persona | null; onSubmit: (p: PersonaIn) => Promise<void> }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<V>({
    resolver: zodResolver(schema),
    defaultValues: {
      name: initial?.name ?? "",
      evidence_level: (initial?.evidence_level as V["evidence_level"]) ?? "hypothesis",
      interests: (initial?.interests ?? []).join(", "),
      problems: (initial?.problems ?? []).join(", "),
      angles: (initial?.angles ?? []).join(", "),
      notes: initial?.notes ?? "",
    },
  });
  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={handleSubmit((v) =>
        onSubmit({ name: v.name.trim(), evidence_level: v.evidence_level, interests: splitList(v.interests), problems: splitList(v.problems), angles: splitList(v.angles), notes: v.notes.trim() || null }),
      )}
    >
      <Field label="Name *" htmlFor="p-name" error={errors.name?.message}><Input id="p-name" {...register("name")} /></Field>
      <Field label="Evidence level" htmlFor="p-level" hint="Only 'verified' should be backed by real data. Instagram does not give you persona demographics.">
        <Select id="p-level" {...register("evidence_level")}>
          {EVIDENCE_LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
        </Select>
      </Field>
      <Field label="Interests (comma separated)" htmlFor="p-int"><Input id="p-int" {...register("interests")} /></Field>
      <Field label="Problems (comma separated)" htmlFor="p-prob"><Input id="p-prob" {...register("problems")} /></Field>
      <Field label="Angles (comma separated)" htmlFor="p-ang"><Input id="p-ang" {...register("angles")} /></Field>
      <Field label="Notes" htmlFor="p-notes"><Textarea id="p-notes" rows={3} {...register("notes")} /></Field>
      <div className="flex justify-end"><Button type="submit" disabled={isSubmitting}>{isSubmitting ? "Saving…" : "Save persona"}</Button></div>
    </form>
  );
}

export function AudiencePage() {
  const personas = useApi(() => api.personas(), []);
  useDataChanged(personas.reload);
  const [editing, setEditing] = React.useState<Persona | null>(null);
  const [creating, setCreating] = React.useState(false);
  const [deleting, setDeleting] = React.useState<Persona | null>(null);
  const poller = useRunPoller((r) => {
    if (r.status === "failed") toast.error(r.error ?? "Audience Intelligence failed");
  });

  const groups = EVIDENCE_LEVELS.map((lvl) => ({ lvl, items: (personas.data ?? []).filter((p) => p.evidence_level === lvl) }));

  return (
    <div>
      <PageHeader
        title="Audience Intelligence"
        description="Who you're making content for. Only 'verified' personas are backed by observed data."
        actions={
          <>
            <Button variant="outline" onClick={() => poller.start("audience_intelligence", {})} disabled={poller.active}>
              <Play /> {poller.active ? "Analysing…" : "Run audience analysis"}
            </Button>
            <Button onClick={() => setCreating(true)}><Plus /> New persona</Button>
          </>
        }
      />

      {(poller.run || poller.error) && (
        <Card className="mb-6">
          <CardHeader title="Audience insights" actions={poller.run && <RunStatusLine status={poller.status} run={poller.run} />} />
          <CardBody>
            {poller.error && <ErrorState message={poller.error} />}
            {poller.run?.status === "failed" && <ErrorState message={poller.run.error ?? "Run failed"} />}
            {poller.run?.status === "succeeded" && (
              <div className="flex flex-col gap-3">
                {poller.run.output_summary && <p className="text-sm">{poller.run.output_summary}</p>}
                <Insights output={poller.run.output} />
              </div>
            )}
            {poller.active && <p className="text-sm text-muted">Waiting for the agent…</p>}
          </CardBody>
        </Card>
      )}

      {personas.loading && !personas.data && <Loading />}
      {personas.error && <ErrorState message={personas.error} onRetry={personas.reload} />}
      {personas.data && personas.data.length === 0 && <Card><EmptyState title="No personas yet" /></Card>}
      {personas.data && personas.data.length > 0 && (
        <div className="flex flex-col gap-6">
          {groups.map(({ lvl, items }) => (
            <section key={lvl}>
              <div className="mb-2 flex items-center gap-2">
                <Badge tone={LEVEL_INFO[lvl].tone}>{LEVEL_INFO[lvl].title}</Badge>
                <span className="text-xs text-muted">{LEVEL_INFO[lvl].note}</span>
              </div>
              {items.length === 0 ? (
                <p className="text-sm text-muted">None.</p>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                  {items.map((p) => (
                    <Card key={p.id}>
                      <div className="flex items-start justify-between gap-2 border-b border-line px-4 py-3">
                        <div>
                          <h3 className="text-sm font-semibold">{p.name}</h3>
                          <div className="mt-1 flex gap-1"><StatusBadge status={p.evidence_level} />{p.is_demo && <Badge tone="amber">DEMO</Badge>}</div>
                        </div>
                        <div className="flex">
                          <Button size="icon" variant="ghost" aria-label={`Edit ${p.name}`} onClick={() => setEditing(p)}><Pencil /></Button>
                          <Button size="icon" variant="ghost" aria-label={`Delete ${p.name}`} onClick={() => setDeleting(p)}><Trash2 /></Button>
                        </div>
                      </div>
                      <CardBody className="flex flex-col gap-2 text-sm">
                        <Row k="Interests" v={p.interests} />
                        <Row k="Problems" v={p.problems} />
                        <Row k="Angles" v={p.angles} />
                        {p.notes && <p className="text-xs text-muted">{p.notes}</p>}
                      </CardBody>
                    </Card>
                  ))}
                </div>
              )}
            </section>
          ))}
        </div>
      )}

      <Dialog open={creating} onOpenChange={setCreating} title="New persona">
        {creating && (
          <PersonaForm
            onSubmit={async (p) => {
              try {
                await api.personaCreate(p);
                toast.success("Persona created");
                setCreating(false);
                personas.reload();
              } catch (e) {
                toast.error(errorMessage(e));
              }
            }}
          />
        )}
      </Dialog>
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)} title={`Edit ${editing?.name ?? ""}`}>
        {editing && (
          <PersonaForm
            initial={editing}
            onSubmit={async (p) => {
              try {
                await api.personaUpdate(editing.id, p);
                toast.success("Persona saved");
                setEditing(null);
                personas.reload();
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
        title="Delete persona?"
        description={deleting?.name}
        destructive
        confirmLabel="Delete"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await api.personaDelete(deleting.id);
            toast.success("Persona deleted");
            setDeleting(null);
            personas.reload();
          } catch (e) {
            toast.error(errorMessage(e));
          }
        }}
      />
    </div>
  );
}

function Row({ k, v }: { k: string; v: string[] }) {
  return (
    <div>
      <span className="text-xs text-muted">{k}: </span>
      {v.length ? v.join(", ") : <span className="text-muted">—</span>}
    </div>
  );
}

function Insights({ output }: { output: Record<string, unknown> }) {
  const entries = Object.entries(output ?? {});
  if (!entries.length) return <p className="text-sm text-muted">No insights returned.</p>;
  return (
    <div className="flex flex-col gap-3 text-sm">
      {entries.map(([k, v]) => (
        <div key={k}>
          <p className="text-xs font-medium uppercase tracking-wide text-muted">{k.replace(/_/g, " ")}</p>
          {typeof v === "string" ? (
            <p>{v}</p>
          ) : Array.isArray(v) && v.every((x) => typeof x === "string") ? (
            <ul className="list-disc pl-5">{(v as string[]).map((x, i) => <li key={i}>{x}</li>)}</ul>
          ) : (
            <JsonView value={v} />
          )}
        </div>
      ))}
    </div>
  );
}
