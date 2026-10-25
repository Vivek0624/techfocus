"use client";
import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Plus, Trash2 } from "lucide-react";
import { api, errorMessage, EXPERIMENT_METRICS, EXPERIMENT_STATUSES, EXPERIMENT_VARIABLES, type Experiment, type ExperimentIn } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtNum, humanize } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { ConfirmDialog, Dialog } from "@/components/ui/dialog";
import { EmptyState, ErrorState, Loading } from "@/components/ui/states";
import { Table, Td, Th } from "@/components/ui/table";
import { PageHeader } from "@/components/page-header";
import { NumOrNA } from "@/components/metric";
import { useDataChanged } from "@/components/shell";

const schema = z.object({
  name: z.string().trim().min(1, "Name is required").max(200),
  hypothesis: z.string().trim().min(1, "Hypothesis is required"),
  variable: z.enum(EXPERIMENT_VARIABLES),
  control: z.string().trim().min(1, "Describe the control"),
  variant: z.string().trim().min(1, "Describe the variant"),
  primary_metric: z.enum(EXPERIMENT_METRICS),
  observation_days: z.coerce.number().int().min(1).max(60),
  min_samples_per_arm: z.coerce.number().int().min(2).max(50),
});

function CreateForm({ onSubmit }: { onSubmit: (v: ExperimentIn) => Promise<void> }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { name: "", hypothesis: "", variable: "hook_style", control: "", variant: "", primary_metric: "views", observation_days: 7, min_samples_per_arm: 3 },
  });
  return (
    <form className="flex flex-col gap-4" noValidate onSubmit={handleSubmit((v) => onSubmit(v))}>
      <Field label="Name *" htmlFor="e-name" error={errors.name?.message}><Input id="e-name" {...register("name")} /></Field>
      <Field label="Hypothesis *" htmlFor="e-hyp" error={errors.hypothesis?.message}><Textarea id="e-hyp" rows={2} {...register("hypothesis")} /></Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Variable" htmlFor="e-var">
          <Select id="e-var" {...register("variable")}>{EXPERIMENT_VARIABLES.map((v) => <option key={v} value={v}>{v}</option>)}</Select>
        </Field>
        <Field label="Primary metric" htmlFor="e-metric">
          <Select id="e-metric" {...register("primary_metric")}>{EXPERIMENT_METRICS.map((v) => <option key={v} value={v}>{v}</option>)}</Select>
        </Field>
        <Field label="Control *" htmlFor="e-control" error={errors.control?.message}><Input id="e-control" {...register("control")} /></Field>
        <Field label="Variant *" htmlFor="e-variant" error={errors.variant?.message}><Input id="e-variant" {...register("variant")} /></Field>
        <Field label="Observation days (1-60)" htmlFor="e-days" error={errors.observation_days?.message}><Input id="e-days" type="number" {...register("observation_days")} /></Field>
        <Field label="Min samples per arm (2-50)" htmlFor="e-min" error={errors.min_samples_per_arm?.message}><Input id="e-min" type="number" {...register("min_samples_per_arm")} /></Field>
      </div>
      <div className="flex justify-end"><Button type="submit" disabled={isSubmitting}>Create experiment</Button></div>
    </form>
  );
}

export function ExperimentsPage() {
  const exps = useApi(() => api.experiments(), []);
  useDataChanged(exps.reload);
  const [creating, setCreating] = React.useState(false);
  const [deleting, setDeleting] = React.useState<Experiment | null>(null);

  const replace = (e: Experiment) => exps.setData((exps.data ?? []).map((x) => (x.id === e.id ? e : x)));

  return (
    <div>
      <PageHeader title="Growth Experiments" description="One variable at a time. Results are evidence, not proof." actions={<Button onClick={() => setCreating(true)}><Plus /> New experiment</Button>} />
      {exps.loading && !exps.data && <Loading />}
      {exps.error && <ErrorState message={exps.error} onRetry={exps.reload} />}
      {exps.data && exps.data.length === 0 && <Card><EmptyState title="No experiments yet" /></Card>}
      <div className="flex flex-col gap-6">
        {exps.data?.map((e) => <ExperimentCard key={e.id} e={e} onChange={replace} onReload={exps.reload} onDelete={() => setDeleting(e)} />)}
      </div>
      <Dialog open={creating} onOpenChange={setCreating} title="New experiment">
        {creating && (
          <CreateForm
            onSubmit={async (v) => {
              try {
                await api.experimentCreate(v);
                toast.success("Experiment created");
                setCreating(false);
                exps.reload();
              } catch (err) {
                toast.error(errorMessage(err));
              }
            }}
          />
        )}
      </Dialog>
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(o) => !o && setDeleting(null)}
        title="Delete experiment?"
        description={deleting ? `"${deleting.name}" and its observations will be deleted.` : undefined}
        destructive
        confirmLabel="Delete"
        onConfirm={async () => {
          if (!deleting) return;
          try {
            await api.experimentDelete(deleting.id);
            toast.success("Experiment deleted");
            setDeleting(null);
            exps.reload();
          } catch (err) {
            toast.error(errorMessage(err));
          }
        }}
      />
    </div>
  );
}

function ExperimentCard({ e, onChange, onReload, onDelete }: { e: Experiment; onChange: (e: Experiment) => void; onReload: () => void; onDelete: () => void }) {
  const r = e.result ?? {};
  const [arm, setArm] = React.useState("control");
  const [value, setValue] = React.useState("");
  const [mediaRef, setMediaRef] = React.useState("");
  const [status, setStatus] = React.useState(e.status);
  const [decision, setDecision] = React.useState(e.decision ?? "");
  const [nextTest, setNextTest] = React.useState(e.next_test ?? "");
  const [obsErr, setObsErr] = React.useState<string | null>(null);

  const addObs = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const n = Number(value);
    if (value.trim() === "" || !Number.isFinite(n)) return setObsErr("Enter a numeric value");
    setObsErr(null);
    try {
      const updated = await api.addObservation(e.id, { arm, value: n, media_ref: mediaRef.trim() || null });
      if (updated && typeof updated === "object" && "id" in updated) onChange(updated);
      else onReload();
      setValue("");
      setMediaRef("");
      toast.success("Observation added");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const save = async () => {
    try {
      const updated = await api.experimentUpdate(e.id, { status, decision: decision.trim() || null, next_test: nextTest.trim() || null });
      if (updated && typeof updated === "object" && "id" in updated) onChange(updated);
      else onReload();
      toast.success("Experiment updated");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <Card>
      <CardHeader
        title={e.name}
        description={`${humanize(e.variable)} · metric: ${e.primary_metric} · ${e.observation_days} days · min ${e.min_samples_per_arm}/arm`}
        actions={
          <>
            <StatusBadge status={e.status} />
            {e.is_demo && <Badge tone="amber">DEMO</Badge>}
            <Button size="icon" variant="ghost" aria-label={`Delete ${e.name}`} onClick={onDelete}><Trash2 /></Button>
          </>
        }
      />
      <CardBody className="grid gap-6 lg:grid-cols-2">
        <div className="flex flex-col gap-3 text-sm">
          <p><span className="text-muted">Hypothesis: </span>{e.hypothesis}</p>
          <div className="grid grid-cols-2 gap-2">
            <div className="rounded-md border border-line p-2"><div className="text-xs text-muted">Control</div>{e.control}</div>
            <div className="rounded-md border border-line p-2"><div className="text-xs text-muted">Variant</div>{e.variant}</div>
          </div>
          <div className="rounded-md border border-line p-3">
            <div className="mb-2 flex items-center gap-2"><span className="text-xs font-medium text-muted">Result</span><StatusBadge status={r.status} /><Badge tone="neutral">confidence: {r.confidence ?? "none"}</Badge></div>
            <dl className="grid grid-cols-3 gap-2 text-sm">
              <div><dt className="text-xs text-muted">n control / variant</dt><dd>{r.n_control ?? 0} / {r.n_variant ?? 0}</dd></div>
              <div><dt className="text-xs text-muted">Median control</dt><dd><NumOrNA value={r.median_control ?? null} /></dd></div>
              <div><dt className="text-xs text-muted">Median variant</dt><dd><NumOrNA value={r.median_variant ?? null} /></dd></div>
              <div><dt className="text-xs text-muted">Lift</dt><dd>{r.lift_pct == null ? <NumOrNA value={null} /> : `${fmtNum(r.lift_pct, 1)}%`}</dd></div>
              <div><dt className="text-xs text-muted">p-value</dt><dd><NumOrNA value={r.p_value ?? null} digits={3} /></dd></div>
            </dl>
            {r.note && <p className="mt-2 text-xs text-muted">{r.note}</p>}
          </div>
          {e.observations.length > 0 && (
            <Table>
              <thead><tr><Th>Arm</Th><Th className="text-right">Value</Th><Th>Media</Th><Th>Source</Th></tr></thead>
              <tbody>
                {e.observations.map((o) => (
                  <tr key={o.id}><Td>{o.arm}</Td><Td className="text-right tabular-nums">{fmtNum(o.value, 2)}</Td><Td className="text-xs">{o.media_ref ?? "—"}</Td><Td className="text-xs">{o.source}</Td></tr>
                ))}
              </tbody>
            </Table>
          )}
        </div>
        <div className="flex flex-col gap-5">
          <form onSubmit={addObs} className="flex flex-col gap-2" aria-label={`Add observation to ${e.name}`}>
            <p className="text-xs font-medium text-muted">Add observation</p>
            <div className="grid grid-cols-[auto_1fr_1fr_auto] gap-2">
              <Select aria-label="Arm" value={arm} onChange={(x) => setArm(x.target.value)} className="w-28">
                <option value="control">control</option>
                <option value="variant">variant</option>
              </Select>
              <Input aria-label="Value" placeholder={e.primary_metric} inputMode="decimal" value={value} onChange={(x) => setValue(x.target.value)} />
              <Input aria-label="Media reference" placeholder="media ref (optional)" value={mediaRef} onChange={(x) => setMediaRef(x.target.value)} />
              <Button type="submit" size="sm" className="h-9">Add</Button>
            </div>
            {obsErr && <p role="alert" className="text-xs text-red-400">{obsErr}</p>}
          </form>
          <div className="flex flex-col gap-2">
            <p className="text-xs font-medium text-muted">Status & decision</p>
            <Select aria-label="Status" value={status} onChange={(x) => setStatus(x.target.value)}>
              {EXPERIMENT_STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
            <Textarea aria-label="Decision" placeholder="Decision (what you'll do based on this)" rows={2} value={decision} onChange={(x) => setDecision(x.target.value)} />
            <Input aria-label="Next test" placeholder="Next test" value={nextTest} onChange={(x) => setNextTest(x.target.value)} />
            <Button variant="secondary" className="self-end" onClick={save}>Save</Button>
          </div>
        </div>
      </CardBody>
    </Card>
  );
}
