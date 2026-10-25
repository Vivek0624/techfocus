"use client";
import * as React from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { api, errorMessage, type Settings, type TargetProgress } from "@/lib/api";
import { useApi } from "@/lib/hooks";
import { todayISO } from "@/lib/utils";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ErrorState, Loading } from "@/components/ui/states";
import { PageHeader } from "@/components/page-header";
import { DATA_CHANGED } from "@/components/shell";

const brandSchema = z.object({
  prefer_real_data: z.boolean(),
  handle: z.string().trim().min(1, "Handle is required").max(60),
  posts_per_week: z.coerce.number().int().min(0).max(50),
  hours_per_week: z.coerce.number().min(0).max(100),
});

const targetSchema = z.object({
  target: z.coerce.number().int().min(1, "Target must be at least 1").max(100000000),
  days: z.coerce.number().int().min(1, "1-365 days").max(365, "1-365 days"),
  start_followers: z.coerce.number().int().min(0, "Must be ≥ 0"),
  start_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/, "Pick a date"),
});

export function SettingsPage() {
  const settings = useApi(() => api.settings(), []);
  const target = useApi(() => api.target(), []);
  return (
    <div>
      <PageHeader title="Settings" description="Secrets live only in the backend .env; this page shows whether they are set." />
      <div className="flex flex-col gap-6">
        <div id="target">
          {target.loading && !target.data && <Loading />}
          {target.error && <ErrorState message={target.error} onRetry={target.reload} />}
          {target.data && <TargetForm t={target.data} onSaved={target.reload} />}
        </div>
        {settings.loading && !settings.data && <Loading />}
        {settings.error && <ErrorState message={settings.error} onRetry={settings.reload} />}
        {settings.data && (
          <>
            <BrandForm s={settings.data} onSaved={settings.setData} />
            <Secrets s={settings.data} />
          </>
        )}
      </div>
    </div>
  );
}

function TargetForm({ t, onSaved }: { t: TargetProgress; onSaved: () => void }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.input<typeof targetSchema>, unknown, z.output<typeof targetSchema>>({
    resolver: zodResolver(targetSchema),
    defaultValues: {
      target: t.config?.target ?? 10000,
      days: t.config?.days ?? 90,
      start_followers: t.config?.start_followers ?? t.current ?? 0,
      start_date: t.config?.start_date ?? todayISO(),
    },
  });
  return (
    <Card className={t.configured ? "" : "border-accent/50"}>
      <CardHeader title="Growth target" description={t.configured ? "Change your follower goal and timeline." : "Start here: set the follower goal you're working towards."} />
      <CardBody>
        <form
          noValidate
          className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 lg:items-end"
          onSubmit={handleSubmit(async (v) => {
            try {
              await api.setTarget(v);
              toast.success("Target saved");
              onSaved();
              window.dispatchEvent(new Event(DATA_CHANGED));
            } catch (e) {
              toast.error(errorMessage(e));
            }
          })}
        >
          <Field label="Target followers" htmlFor="t-target" error={errors.target?.message}><Input id="t-target" type="number" {...register("target")} /></Field>
          <Field label="Days" htmlFor="t-days" error={errors.days?.message}><Input id="t-days" type="number" {...register("days")} /></Field>
          <Field label="Starting followers" htmlFor="t-start" error={errors.start_followers?.message}><Input id="t-start" type="number" {...register("start_followers")} /></Field>
          <Field label="Start date" htmlFor="t-date" error={errors.start_date?.message}><Input id="t-date" type="date" {...register("start_date")} /></Field>
          <Button type="submit" disabled={isSubmitting}>Save target</Button>
        </form>
      </CardBody>
    </Card>
  );
}

function BrandForm({ s, onSaved }: { s: Settings; onSaved: (s: Settings) => void }) {
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm<z.input<typeof brandSchema>, unknown, z.output<typeof brandSchema>>({
    resolver: zodResolver(brandSchema),
    defaultValues: { prefer_real_data: s.prefer_real_data, handle: s.brand.handle, posts_per_week: s.brand.posts_per_week, hours_per_week: s.brand.hours_per_week },
  });
  return (
    <Card>
      <CardHeader title="Preferences" description={`Data mode: ${s.data_mode}`} />
      <CardBody>
        <form
          noValidate
          className="flex flex-col gap-4"
          onSubmit={handleSubmit(async (v) => {
            try {
              const res = await api.updateSettings({ prefer_real_data: v.prefer_real_data, brand: { handle: v.handle, posts_per_week: v.posts_per_week, hours_per_week: v.hours_per_week } });
              if (res && typeof res === "object" && "data_mode" in res) onSaved(res);
              else onSaved({ ...s, prefer_real_data: v.prefer_real_data, brand: { handle: v.handle, posts_per_week: v.posts_per_week, hours_per_week: v.hours_per_week } });
              toast.success("Settings saved");
              window.dispatchEvent(new Event(DATA_CHANGED));
            } catch (e) {
              toast.error(errorMessage(e));
            }
          })}
        >
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-[#5b7cfa]" {...register("prefer_real_data")} />
            Prefer real data (hide demo data once real or manual data exists)
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Instagram handle" htmlFor="b-handle" error={errors.handle?.message}><Input id="b-handle" {...register("handle")} /></Field>
            <Field label="Posts per week" htmlFor="b-ppw" error={errors.posts_per_week?.message}><Input id="b-ppw" type="number" {...register("posts_per_week")} /></Field>
            <Field label="Hours per week" htmlFor="b-hpw" error={errors.hours_per_week?.message}><Input id="b-hpw" type="number" step="0.5" {...register("hours_per_week")} /></Field>
          </div>
          <div className="flex justify-end"><Button type="submit" disabled={isSubmitting}>Save preferences</Button></div>
        </form>
      </CardBody>
    </Card>
  );
}

function Secrets({ s }: { s: Settings }) {
  const rows: [string, boolean][] = [
    ["Meta app (META_APP_ID / META_APP_SECRET)", s.meta_app_configured],
    ["Token encryption key (TOKEN_ENCRYPTION_KEY)", s.token_encryption_key_set],
    ["AgentCore runtime", s.agentcore_runtime_configured],
    ["Research provider", s.research_provider_configured],
    ["S3 media bucket", !!s.s3_media_bucket],
    ["Local scheduler", s.local_scheduler],
  ];
  return (
    <Card>
      <CardHeader title="Configuration & secrets" description="Booleans only. Values never leave the backend." />
      <CardBody className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          {rows.map(([k, v]) => (
            <div key={k} className="flex items-center gap-2 text-sm">
              {v ? <Check className="size-4 text-emerald-400" /> : <X className="size-4 text-muted" />} {k}: <span className="text-muted">{v ? "set" : "not set"}</span>
            </div>
          ))}
        </div>
        <dl className="grid grid-cols-2 gap-3 text-sm">
          <div><dt className="text-xs text-muted">Environment</dt><dd>{s.app_env}</dd></div>
          <div><dt className="text-xs text-muted">Agent mode</dt><dd>{s.agent_mode}</dd></div>
          <div><dt className="text-xs text-muted">AWS region</dt><dd>{s.aws_region ?? "—"}</dd></div>
          <div><dt className="text-xs text-muted">Bedrock model</dt><dd className="break-all">{s.bedrock_model_id ?? "—"}</dd></div>
          <div className="col-span-2"><dt className="text-xs text-muted">Instagram redirect URI</dt><dd className="break-all">{s.meta_redirect_uri}</dd></div>
          <div className="col-span-2"><dt className="text-xs text-muted">Scopes</dt><dd className="text-xs">{s.meta_scopes.join(", ")}</dd></div>
        </dl>
      </CardBody>
    </Card>
  );
}
