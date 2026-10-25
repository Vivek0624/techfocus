"use client";
import * as React from "react";
import { useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, Link2, RefreshCw, Unplug, X } from "lucide-react";
import { api, errorMessage, type ManualSnapshotIn } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { fmtDateTime, todayISO } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Badge } from "@/components/ui/badge";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ErrorState, Loading } from "@/components/ui/states";
import { PageHeader } from "@/components/page-header";
import { DATA_CHANGED, useDataChanged } from "@/components/shell";

function YesNo({ ok, label }: { ok: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {ok ? <Check className="size-4 text-emerald-400" /> : <X className="size-4 text-red-400" />}
      {label}
    </div>
  );
}

export function InstagramPage() {
  const params = useSearchParams();
  const status = useApi(() => api.instagramStatus(), []);
  useDataChanged(status.reload);
  const [connectErr, setConnectErr] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState<string | null>(null);
  const [confirmDisconnect, setConfirmDisconnect] = React.useState(false);
  const connected = params.get("connected") === "1";
  const qError = params.get("error");

  const connect = async () => {
    setBusy("connect");
    setConnectErr(null);
    try {
      const { authorize_url } = await api.instagramConnect();
      window.location.assign(authorize_url);
    } catch (e) {
      setConnectErr(errorMessage(e));
      setBusy(null);
    }
  };
  const sync = async () => {
    setBusy("sync");
    try {
      await api.instagramSync();
      toast.success("Sync complete");
      status.reload();
      window.dispatchEvent(new Event(DATA_CHANGED));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };
  const disconnect = async () => {
    setBusy("disconnect");
    try {
      await api.instagramDisconnect();
      toast.success("Disconnected");
      setConfirmDisconnect(false);
      status.reload();
      window.dispatchEvent(new Event(DATA_CHANGED));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const s = status.data;
  return (
    <div>
      <PageHeader title="Instagram Connection" description={s?.auth_flow ?? "Connect your professional account to pull real insights."} />
      {connected && <div role="status" className="mb-4 rounded-md border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm text-emerald-700 dark:text-emerald-200">Instagram connected. Run a sync to pull your data.</div>}
      {qError && <ErrorState message={`Instagram connection failed: ${qError.replace(/_/g, " ")}`} />}
      {status.loading && !s && <Loading />}
      {status.error && <ErrorState message={status.error} onRetry={status.reload} />}
      {s && (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader
              title="Status"
              actions={<Badge tone={s.connected ? "green" : "neutral"}>{s.connected ? "Connected" : "Not connected"}</Badge>}
            />
            <CardBody className="flex flex-col gap-3">
              <YesNo ok={s.app_configured} label="Meta app configured (META_APP_ID / SECRET)" />
              <YesNo ok={s.encryption_key_set} label="Token encryption key set" />
              <YesNo ok={s.connected} label="Account connected" />
              <dl className="mt-2 grid grid-cols-2 gap-3 text-sm">
                <div><dt className="text-xs text-muted">Username</dt><dd>{s.username ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted">Account type</dt><dd>{s.account_type ?? "—"}</dd></div>
                <div><dt className="text-xs text-muted">Token</dt><dd><Badge tone={s.token.state === "valid" ? "green" : s.token.state === "missing" ? "neutral" : "amber"}>{s.token.state}</Badge></dd></div>
                <div><dt className="text-xs text-muted">Token expiry</dt><dd>{s.token.expires_at ? fmtDateTime(String(s.token.expires_at)) : "—"}</dd></div>
                <div><dt className="text-xs text-muted">Last sync</dt><dd>{fmtDateTime(s.last_sync_at)}</dd></div>
              </dl>
              {s.last_error && <ErrorState message={s.last_error} />}
              <div className="flex flex-wrap gap-2 border-t border-line pt-3">
                <Button onClick={connect} disabled={busy !== null}><Link2 /> {s.connected ? "Reconnect" : "Connect Instagram"}</Button>
                <Button variant="outline" onClick={sync} disabled={!s.connected || busy !== null}><RefreshCw /> {busy === "sync" ? "Syncing…" : "Sync now"}</Button>
                <Button variant="outline" onClick={() => setConfirmDisconnect(true)} disabled={!s.connected || busy !== null}><Unplug /> Disconnect</Button>
              </div>
              {connectErr && <ErrorState message={connectErr} />}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Permissions" />
            <CardBody className="flex flex-col gap-2">
              {s.permissions.map((p) => (
                <div key={p.scope} className="flex items-start gap-2 text-sm">
                  {p.granted ? <Check className="mt-0.5 size-4 text-emerald-400" /> : <X className="mt-0.5 size-4 text-muted" />}
                  <div><code className="text-xs">{p.scope}</code><div className="text-xs text-muted">{p.purpose}</div></div>
                </div>
              ))}
              <p className="mt-3 text-xs font-medium text-muted">Requirements</p>
              <ul className="list-disc pl-5 text-sm text-muted">{s.requirements.map((r) => <li key={r}>{r}</li>)}</ul>
            </CardBody>
          </Card>
        </div>
      )}
      <div className="mt-6"><ManualEntry /></div>
      <ConfirmDialog open={confirmDisconnect} onOpenChange={setConfirmDisconnect} title="Disconnect Instagram?" description="The stored token will be removed. Synced data stays." destructive confirmLabel="Disconnect" busy={busy === "disconnect"} onConfirm={disconnect} />
    </div>
  );
}

const optInt = z.string().trim().refine((v) => v === "" || /^\d+$/.test(v), "Whole number ≥ 0, or leave blank");
const manualSchema = z.object({
  snapshot_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Pick a date"),
  followers: optInt,
  reach: optInt,
  views: optInt,
  follows: optInt,
  unfollows: optInt,
});
type MV = z.infer<typeof manualSchema>;

function ManualEntry() {
  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<MV>({
    resolver: zodResolver(manualSchema),
    defaultValues: { snapshot_date: todayISO(), followers: "", reach: "", views: "", follows: "", unfollows: "" },
  });
  const n = (v: string) => (v === "" ? null : Number(v));
  const submit = async (v: MV) => {
    const body: ManualSnapshotIn = { snapshot_date: v.snapshot_date, followers: n(v.followers), reach: n(v.reach), views: n(v.views), follows: n(v.follows), unfollows: n(v.unfollows) };
    try {
      await api.manualSnapshot(body);
      toast.success("Snapshot saved");
      reset({ ...v, followers: "", reach: "", views: "", follows: "", unfollows: "" });
      window.dispatchEvent(new Event(DATA_CHANGED));
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };
  const fields: [keyof MV, string][] = [["followers", "Followers"], ["reach", "Reach"], ["views", "Views"], ["follows", "Follows"], ["unfollows", "Unfollows"]];
  return (
    <Card>
      <CardHeader title="Manual data entry" description="No API connection? Copy numbers from the Instagram app. Blank = unavailable (not zero)." />
      <CardBody>
        <form onSubmit={handleSubmit(submit)} noValidate className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6 lg:items-end">
          <Field label="Date *" htmlFor="m-date" error={errors.snapshot_date?.message}><Input id="m-date" type="date" {...register("snapshot_date")} /></Field>
          {fields.map(([k, label]) => (
            <Field key={k} label={label} htmlFor={`m-${k}`} error={errors[k]?.message}><Input id={`m-${k}`} inputMode="numeric" {...register(k)} /></Field>
          ))}
          <Button type="submit" disabled={isSubmitting} className="lg:col-span-6 lg:justify-self-end">Save snapshot</Button>
        </form>
      </CardBody>
    </Card>
  );
}
