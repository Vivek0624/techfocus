// Typed client for the FastAPI backend. Browser-side only; no secrets.

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  problems: string[];
  body: unknown;
  constructor(message: string, status: number, problems: string[] = [], body: unknown = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.problems = problems;
    this.body = body;
  }
}

type Query = Record<string, string | number | boolean | null | undefined>;

function qs(q?: Query): string {
  if (!q) return "";
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(q)) if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  const s = p.toString();
  return s ? `?${s}` : "";
}

/** Turn any backend error body into a readable message (+ optional problems list). */
export function parseErrorBody(body: unknown, status: number): { message: string; problems: string[] } {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    const err = b.error ?? b.detail;
    if (typeof err === "string") return { message: err, problems: [] };
    if (Array.isArray(err)) {
      const msgs = err.map((e) => {
        if (e && typeof e === "object" && "msg" in e) {
          const loc = Array.isArray((e as { loc?: unknown[] }).loc) ? (e as { loc: unknown[] }).loc.slice(1).join(".") : "";
          return `${loc ? loc + ": " : ""}${(e as { msg: string }).msg}`;
        }
        return String(e);
      });
      return { message: msgs.join("; ") || `Request failed (${status})`, problems: msgs };
    }
    if (err && typeof err === "object") {
      const e = err as Record<string, unknown>;
      const problems = Array.isArray(e.problems) ? e.problems.map(String) : [];
      const message = typeof e.message === "string" ? e.message : JSON.stringify(err);
      return { message, problems };
    }
  }
  if (typeof body === "string" && body) return { message: body, problems: [] };
  return { message: `Request failed (${status})`, problems: [] };
}

export async function request<T>(method: string, path: string, opts: { query?: Query; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}${qs(opts.query)}`, {
      method,
      headers: opts.body !== undefined ? { "Content-Type": "application/json" } : undefined,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      cache: "no-store",
    });
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0);
  }
  const text = await res.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
  }
  if (!res.ok) {
    const { message, problems } = parseErrorBody(body, res.status);
    throw new ApiError(message, res.status, problems, body);
  }
  return body as T;
}

export function errorMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---------- Types ----------
export type Source = "instagram_api" | "manual" | "calculated" | "demo" | string;
export type Num = number | null;

export interface Metrics {
  days: number;
  followers_start: Num;
  followers_end: Num;
  net_follower_growth: Num;
  pct_follower_growth: Num;
  followers_gained: Num;
  followers_lost: Num;
  reach: Num;
  views: Num;
  accounts_engaged: Num;
  likes: Num;
  comments: Num;
  shares: Num;
  saves: Num;
  profile_links_taps: Num;
  follows_per_1k_reach: Num;
  sources: Source[];
  last_refresh: string | null;
}

export interface Post {
  id: number;
  ig_media_id: string | null;
  caption: string | null;
  media_product_type: string | null;
  permalink: string | null;
  published_at: string | null;
  pillar: string | null;
  hook_style: string | null;
  source: Source;
  views: Num;
  reach: Num;
  likes: Num;
  comments: Num;
  shares: Num;
  saved: Num;
  total_interactions: Num;
  avg_watch_time_ms: Num;
  metrics_fetched_at: string | null;
  multiple: Num;
}

export interface Scenario {
  daily_net: number;
  projected_followers: number;
}

export interface TargetProgress {
  configured: boolean;
  config?: { target: number; days: number; start_followers: number; start_date: string } | null;
  start_followers?: Num;
  target?: Num;
  current?: Num;
  start_date?: string | null;
  end_date?: string | null;
  days_total?: Num;
  days_elapsed?: Num;
  days_remaining?: Num;
  remaining?: Num;
  required_per_day?: Num;
  actual_per_day?: Num;
  on_pace?: boolean | null;
  scenarios?: Scenario[];
  scenario_note?: string;
}

export interface AgentRun {
  id: number;
  agent_id: string;
  parent_run_id: number | null;
  mode: string;
  status: "queued" | "running" | "cancelling" | "succeeded" | "failed" | "cancelled" | string;
  input_summary: string | null;
  input: Record<string, unknown>;
  output_summary: string | null;
  output: Record<string, unknown>;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  est_cost_usd: number | null;
  created_at: string;
  is_demo: boolean;
  tools_called?: string[];
}

export interface Dashboard {
  mode: "demo" | "real" | string;
  range: { start: string; end: string; days?: number };
  account: {
    mode: string;
    username: string | null;
    account_type: string | null;
    followers: Num;
    source: Source;
    last_refresh: string | null;
  };
  metrics: Metrics;
  metric_sources: Record<string, Source>;
  limitations: string[];
  posts_published: Num;
  engagement_rate_by_reach: Num;
  reach_per_post: Num;
  best_reels: Post[];
  recent_posts: Post[];
  target: TargetProgress;
  upcoming: { id: number; title: string; scheduled_at: string; approval_status: string }[];
  top_action: { title: string; reason: string | null } | null;
  recent_agent_runs: AgentRun[];
}

export interface GroupStat {
  group: string;
  n: number;
  median: Num;
  enough_data: boolean;
}

export interface DailyRow {
  date: string;
  followers: Num;
  follows: Num;
  unfollows: Num;
  reach: Num;
  views: Num;
  accounts_engaged: Num;
  likes: Num;
  comments: Num;
  shares: Num;
  saves: Num;
  profile_links_taps: Num;
  source: Source;
  fetched_at: string | null;
}

export interface Analytics {
  mode: string;
  range: { start: string; end: string };
  follower_history: DailyRow[];
  insights: Metrics;
  posts: Post[];
  by_pillar: GroupStat[];
  by_hook: GroupStat[];
  by_format: GroupStat[];
  best_time: { status: string; windows: GroupStat[]; recommendation: string | null };
  definitions: Record<string, string>;
}

export const CONTENT_FORMATS = ["talking_head", "motion_graphics", "carousel", "mixed"] as const;
export const CONTENT_STATUSES = ["idea", "selected", "scripting", "production", "ready", "scheduled", "published", "archived"] as const;
export const EFFORTS = ["low", "medium", "high"] as const;

export interface ContentIdeaFields {
  title: string;
  pillar: string | null;
  audience_segment: string | null;
  audience?: string | null;
  audience_problem: string | null;
  format: (typeof CONTENT_FORMATS)[number] | null;
  hook_options: string[];
  recommended_hook: string | null;
  script: string | null;
  storyboard: Record<string, unknown>[];
  on_screen_text: string[];
  visual_direction: string | null;
  duration_seconds: number | null;
  caption: string | null;
  keywords: string[];
  hashtags: string[];
  cta: string | null;
  effort: (typeof EFFORTS)[number] | null;
  evidence: string[];
  hypothesis: string | null;
  status: string;
  planned_at: string | null;
  lessons: string | null;
  notes?: string | null;
  package: Record<string, unknown>;
}

export interface ContentIdea extends ContentIdeaFields {
  id: number;
  created_at: string;
  updated_at: string;
  published_media_id: string | null;
  performance: Record<string, unknown>;
  is_demo: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CalendarItem {
  id: number;
  idea_id: number | null;
  title: string;
  format: string | null;
  scheduled_at: string;
  timezone: string;
  caption: string | null;
  asset_ref: string | null;
  production_status: string;
  approval_status: string;
  publishing_status: string;
  published_at: string | null;
  published_media_id: string | null;
  is_demo: boolean;
}

export interface CalendarCreate {
  title: string;
  idea_id?: number | null;
  format?: string | null;
  scheduled_at: string;
  caption?: string | null;
  asset_ref?: string | null;
  production_status?: string;
}

export interface Approval {
  id: number;
  action: string;
  target_type: string;
  target_id: number;
  summary: string;
  payload: Record<string, unknown>;
  status: string;
  requested_by: string;
  created_at: string;
  decided_at: string | null;
}

export const EVIDENCE_LEVELS = ["verified", "inferred", "hypothesis"] as const;
export interface PersonaIn {
  name: string;
  evidence_level: string;
  interests: string[];
  problems: string[];
  angles: string[];
  notes: string | null;
}
export interface Persona extends PersonaIn {
  id: number;
  is_demo: boolean;
}

export const EXPERIMENT_VARIABLES = ["hook_style", "duration", "format", "storytelling", "cta", "pillar", "publish_window", "caption_style"] as const;
export const EXPERIMENT_METRICS = ["views", "reach", "saves", "shares", "follows", "multiple"] as const;
export const EXPERIMENT_STATUSES = ["planned", "running", "complete"] as const;

export interface ExperimentIn {
  name: string;
  hypothesis: string;
  variable: string;
  control: string;
  variant: string;
  primary_metric?: string;
  observation_days?: number;
  min_samples_per_arm?: number;
}
export interface ExperimentResult {
  n_control?: number;
  n_variant?: number;
  status?: string;
  median_control?: Num;
  median_variant?: Num;
  lift_pct?: Num;
  p_value?: Num;
  confidence?: string;
  note?: string;
}
export interface Experiment extends Required<ExperimentIn> {
  id: number;
  status: string;
  decision: string | null;
  next_test: string | null;
  is_demo: boolean;
  created_at: string;
  result: ExperimentResult;
  observations: { id: number; arm: string; value: number; media_ref: string | null; source: string }[];
}

export interface Agent {
  id: string;
  name: string;
  responsibility: string;
  tools: string[];
  kind: string;
  mode: string;
  write_tools: string[];
  last_run: AgentRun | null;
}

export interface Task {
  id: number;
  task_date: string;
  title: string;
  reason: string | null;
  impact: number;
  effort_minutes: number;
  priority: number;
  done: boolean;
  is_demo: boolean;
}

export interface Settings {
  app_env: string;
  agent_mode: string;
  aws_region: string | null;
  bedrock_model_id: string | null;
  agentcore_runtime_configured: boolean;
  aws_profile: string | null;
  meta_app_configured: boolean;
  token_encryption_key_set: boolean;
  meta_redirect_uri: string;
  meta_scopes: string[];
  s3_media_bucket: string | null;
  research_provider_configured: boolean;
  local_scheduler: boolean;
  data_mode: string;
  prefer_real_data: boolean;
  brand: { handle: string; posts_per_week: number; hours_per_week: number };
}

export interface InstagramStatus {
  app_configured: boolean;
  encryption_key_set: boolean;
  connected: boolean;
  username: string | null;
  account_type: string | null;
  last_sync_at: string | null;
  last_error: string | null;
  token: { state: string; expires_at?: string | null; [k: string]: unknown };
  auto_sync?: { enabled: boolean; schedule: string; last: { at: string; ok: boolean; error: string | null } | null };
  permissions: { scope: string; purpose: string; granted: boolean }[];
  auth_flow: string;
  requirements: string[];
}

export interface AwsStatus {
  agent_mode: string;
  region: string | null;
  profile: string | null;
  bedrock_model_id: string | null;
  agentcore_runtime_arn_set: boolean;
  credentials: string;
  checked_at: string;
  services: { name: string; phase: string; needed: boolean }[];
}

export interface ManualSnapshotIn {
  snapshot_date: string;
  followers?: number | null;
  reach?: number | null;
  views?: number | null;
  follows?: number | null;
  unfollows?: number | null;
}

export interface DateFilter {
  days?: number;
  start?: string;
  end?: string;
}

// ---------- Endpoints ----------
export const api = {
  dashboard: (f: DateFilter = {}) => request<Dashboard>("GET", "/api/dashboard", { query: { ...f } }),
  analytics: (f: DateFilter = {}) => request<Analytics>("GET", "/api/analytics", { query: { ...f } }),
  settings: () => request<Settings>("GET", "/api/settings"),
  updateSettings: (body: Partial<Pick<Settings, "prefer_real_data" | "brand">>) => request<Settings>("PUT", "/api/settings", { body }),
  resetDemo: () => request<unknown>("POST", "/api/demo/reset"),

  target: () => request<TargetProgress>("GET", "/api/growth/target"),
  setTarget: (body: { target: number; days: number; start_followers: number; start_date: string }) =>
    request<TargetProgress>("PUT", "/api/growth/target", { body }),
  manualSnapshot: (body: ManualSnapshotIn) => request<unknown>("POST", "/api/growth/manual-snapshot", { body }),
  dailyPlan: (day?: string) => request<Task[]>("GET", "/api/growth/daily-plan", { query: { day } }),
  addTask: (body: { title: string; impact?: number; effort_minutes?: number }) => request<Task>("POST", "/api/growth/daily-plan", { body }),
  setTaskDone: (id: number, done: boolean) => request<Task>("PATCH", `/api/growth/daily-plan/${id}`, { query: { done } }),

  content: (q: { search?: string; status?: string; pillar?: string; sort?: string; order?: string; page?: number; page_size?: number }) =>
    request<Page<ContentIdea>>("GET", "/api/content", { query: q }),
  contentGet: (id: number) => request<ContentIdea>("GET", `/api/content/${id}`),
  contentCreate: (body: Partial<ContentIdeaFields> & { title: string }) => request<ContentIdea>("POST", "/api/content", { body }),
  contentUpdate: (id: number, body: Partial<ContentIdeaFields>) => request<ContentIdea>("PATCH", `/api/content/${id}`, { body }),
  contentDelete: (id: number) => request<unknown>("DELETE", `/api/content/${id}`),
  contentClone: (id: number) => request<ContentIdea>("POST", `/api/content/${id}/clone`),
  contentExportUrl: (fmt: "csv" | "json") => `${API_URL}/api/content/export${qs({ fmt })}`,

  calendar: (q: { start?: string; end?: string } = {}) => request<CalendarItem[]>("GET", "/api/calendar", { query: q }),
  calendarCreate: (body: CalendarCreate) => request<CalendarItem>("POST", "/api/calendar", { body }),
  calendarUpdate: (id: number, body: Partial<CalendarCreate> & { approval_status?: string }) =>
    request<CalendarItem>("PATCH", `/api/calendar/${id}`, { body }),
  calendarDelete: (id: number) => request<unknown>("DELETE", `/api/calendar/${id}`),
  manualChecklist: (id: number) => request<{ item: string; steps: string[]; caption: string | null }>("GET", `/api/calendar/${id}/manual-checklist`),
  requestPublish: (id: number) => request<Record<string, unknown>>("POST", `/api/calendar/${id}/request-publish`),

  approvals: (status?: string) => request<Approval[]>("GET", "/api/approvals", { query: { status } }),
  decide: (id: number, approve: boolean) => request<Approval>("POST", `/api/approvals/${id}/decision`, { query: { approve } }),
  executeApproval: (id: number) => request<Record<string, unknown>>("POST", `/api/approvals/${id}/execute`),

  personas: () => request<Persona[]>("GET", "/api/personas"),
  personaCreate: (body: PersonaIn) => request<Persona>("POST", "/api/personas", { body }),
  personaUpdate: (id: number, body: PersonaIn) => request<Persona>("PUT", `/api/personas/${id}`, { body }),
  personaDelete: (id: number) => request<unknown>("DELETE", `/api/personas/${id}`),

  experiments: () => request<Experiment[]>("GET", "/api/experiments"),
  experimentCreate: (body: ExperimentIn) => request<Experiment>("POST", "/api/experiments", { body }),
  experimentUpdate: (id: number, body: { status?: string | null; decision?: string | null; next_test?: string | null }) =>
    request<Experiment>("PATCH", `/api/experiments/${id}`, { body }),
  experimentDelete: (id: number) => request<unknown>("DELETE", `/api/experiments/${id}`),
  addObservation: (id: number, body: { arm: string; value: number; media_ref?: string | null }) =>
    request<Experiment>("POST", `/api/experiments/${id}/observations`, { body }),

  agents: () => request<Agent[]>("GET", "/api/agents"),
  runAgent: (id: string, input: Record<string, unknown> = {}) => request<AgentRun>("POST", `/api/agents/${id}/run`, { body: { input } }),
  agentRuns: (q: { agent_id?: string; page?: number; page_size?: number } = {}) => request<Page<AgentRun>>("GET", "/api/agent-runs", { query: q }),
  agentRun: (id: number) => request<AgentRun>("GET", `/api/agent-runs/${id}`),
  cancelRun: (id: number) => request<{ run_id: number; state: string }>("POST", `/api/agent-runs/${id}/cancel`),
  retryRun: (id: number) => request<AgentRun>("POST", `/api/agent-runs/${id}/retry`),

  instagramStatus: () => request<InstagramStatus>("GET", "/api/instagram/status"),
  instagramConnect: () => request<{ authorize_url: string }>("GET", "/api/instagram/connect"),
  instagramDisconnect: () => request<unknown>("POST", "/api/instagram/disconnect"),
  instagramSync: () => request<Record<string, unknown>>("POST", "/api/instagram/sync"),

  awsStatus: () => request<AwsStatus>("GET", "/api/aws/status"),
};

export const TERMINAL_RUN_STATES = ["succeeded", "failed", "cancelled"];
export const isTerminal = (s: string) => TERMINAL_RUN_STATES.includes(s);

// ---------- Creator workflow (v2) ----------
export interface Check { score: number; detail: string }
export interface HookScore {
  score: number;
  verdict: string;
  checks: Record<string, Check>;
  flags?: string[];
  fix: string | null;
  formula?: string;
}
export interface Hook {
  text: string;
  formula: string;
  on_screen: string;
  score: number;
  verdict: string;
  fix: string | null;
  checks?: Record<string, Check>;
}
export interface Suggestion {
  idea_id: number;
  title: string;
  status: string;
  step: string;
  category: string | null;
  hook: string | null;
  hook_score: HookScore | null;
  alt_hooks: Hook[];
  caption: string | null;
  hashtags: string[];
  why: string | null;
}
export interface AudienceTag { audience: string; label: string; inferred: boolean; reason: string }
export interface ShortlistItem {
  idea_id: number;
  title: string;
  status: string | null;
  category: string | null;
  hook: string | null;
  audience: AudienceTag;
  shareability: { score: number; band: string; tip: string | null };
  why: string[];
  flags: { kind: string; message: string }[];
  watch: { metric: string; target: number | null; text: string };
}
export interface Insight {
  kind: string;
  headline: string;
  detail?: string | null;
  action?: string | null;
  confidence?: string | null;
  evidence?: Record<string, unknown>;
  [k: string]: unknown;
}
export interface Today {
  mode: string;
  last_sync_at?: string | null;
  suggestion: Suggestion | null;
  tip: Insight | null;
  goal: TargetProgress;
  week: { published: number; target: number };
  pipeline_counts: Record<string, number>;
  reminders: { id: number; title: string; scheduled_at: string }[];
  tasks: { id: number; title: string; done: boolean }[];
  shortlist?: ShortlistItem[];
  memory?: { avoid: { group: string; label: string; median: number; n: number; confidence: string }[]; baseline_shares_per_1k: Num; sample_size: number };
}
export interface BoardItem {
  id: number;
  title: string;
  category: string | null;
  hook: string | null;
  format: string | null;
  updated_at: string;
  planned_at: string | null;
  calendar_id: number | null;
  audience?: string | null;
  audience_inferred?: boolean;
  shareability?: number | null;
}
export interface Board {
  columns: { status: string; items: BoardItem[] }[];
  categories: string[];
  formats: string[];
}
export interface WeekItem { id: number; idea_id: number | null; title: string; scheduled_at: string; status: string; published: boolean }
export interface Similar { kind: string; id: number; text: string; similarity: number }
export interface QuickIdeaIn { title: string; note?: string | null; category?: string | null; force?: boolean }
export interface Caption {
  source: string;
  first_line: string;
  body: string;
  cta: string;
  keywords: string[];
  hashtags: string[];
  full: string;
  preview_cut: string;
  length: number;
  max: number;
}
export interface Repurpose {
  source: string;
  audience: string;
  reel_30s: { t: string; say: string; screen: string }[];
  carousel: { title: string; text: string }[];
  linkedin_post: string;
  youtube_short: string;
  text_post: string;
}
export interface GroupRow { group: string; label: string; n: number; median: number }
export interface InsightPost {
  id: number;
  title: string | null;
  caption: string | null;
  published_at: string | null;
  views: Num;
  reach: Num;
  shares: Num;
  saved: Num;
  avg_watch_time_ms: Num;
  multiple: Num;
  pillar: string | null;
  format_style: string | null;
  length_seconds: Num;
  hook_text: string | null;
  media_product_type?: string | null;
  attribution?: { available: boolean; follows?: Num; profile_visits?: Num; profile_activity?: Num; reposts?: Num; note: string | null };
  audience_tag?: AudienceTag;
  retention?: { avg_seconds: number; length_seconds: Num; percent_watched: Num; total_watch_hours: Num; verdict: string } | null;
  [k: string]: unknown;
}
export interface Insights {
  sample_size: number;
  tagged: number;
  summary: { median_views: Num; median_shares_per_1k: Num; median_saves_per_1k: Num; median_watch_seconds: Num };
  insights: Insight[];
  answers: {
    best_hooks: GroupRow[];
    topics_by_shares: GroupRow[];
    formats: GroupRow[];
    lengths: GroupRow[];
    repeat: string[];
    improve: string[];
    stop: string[];
  };
  posts: InsightPost[];
  note: string;
  mode?: string;
  follower_history?: FollowerDay[];
}
export interface PostTags {
  audience?: string | null;
  hook_text?: string | null;
  category?: string | null;
  format_style?: string | null;
  length_seconds?: number | null;
}
export interface PostIn extends PostTags {
  title: string;
  published_at: string;
  permalink?: string | null;
  views?: number | null;
  reach?: number | null;
  likes?: number | null;
  comments?: number | null;
  shares?: number | null;
  saves?: number | null;
  avg_watch_seconds?: number | null;
}
export interface SaveIn {
  idea_id?: number | null;
  title?: string | null;
  hook?: string | null;
  caption?: string | null;
  hashtags?: string[] | null;
  category?: string | null;
  package?: Record<string, unknown> | null;
}
export type Audience = "beginner" | "developer";

export const v2 = {
  today: () => request<Today>("GET", "/api/today"),
  board: () => request<Board>("GET", "/api/board"),
  week: (start: string) => request<{ start: string; items: WeekItem[] }>("GET", "/api/week", { query: { start } }),
  quickIdea: (body: QuickIdeaIn) => request<{ id: number; title: string; [k: string]: unknown }>("POST", "/api/ideas/quick", { body }),
  checkDuplicate: (body: QuickIdeaIn) => request<{ similar: Similar[] }>("POST", "/api/ideas/check-duplicate", { body }),
  plan: (id: number, when: string) => request<unknown>("POST", `/api/ideas/${id}/plan`, { body: { when } }),
  idea: (id: number) => request<ContentIdea>("GET", `/api/content/${id}`),
  updateIdea: (id: number, body: Partial<ContentIdeaFields>) => request<ContentIdea>("PATCH", `/api/content/${id}`, { body }),
  hooks: (body: { topic: string; audience: Audience; perspective: string }) =>
    request<{ source: string; hooks: Hook[]; note?: string }>("POST", "/api/create/hooks", { body }),
  scoreHook: (body: { text: string; perspective: string }) => request<HookScore>("POST", "/api/create/score-hook", { body }),
  caption: (body: { topic: string; hook?: string | null; category?: string; audience: Audience }) => request<Caption>("POST", "/api/create/caption", { body }),
  repurpose: (body: { topic: string; audience: Audience; hook?: string | null; idea_id?: number | null }) =>
    request<Repurpose>("POST", "/api/create/repurpose", { body }),
  save: (body: SaveIn) => request<{ id?: number; [k: string]: unknown }>("POST", "/api/create/save", { body }),
  insights: () => request<Insights>("GET", "/api/insights"),
  coachAI: () => request<CoachBrief>("GET", "/api/insights/coach-ai"),
  tagPost: (id: number, body: PostTags) => request<unknown>("PATCH", `/api/posts/${id}`, { body }),
  addPost: (body: PostIn) => request<unknown>("POST", "/api/posts", { body }),
  importCsv: (csv_text: string) => request<{ added?: number; errors?: unknown[]; [k: string]: unknown }>("POST", "/api/posts/import-csv", { body: { csv_text } }),
  csvTemplate: () => request<{ columns: string[]; example: string }>("GET", "/api/posts/csv-template"),
};

// ---------- Activity + audience (v3) ----------
export interface Comment {
  id: number;
  username: string;
  text: string;
  intent: "question" | "request" | "praise" | "feedback" | "spam" | "other" | string;
  draft_reply: string | null;
  replied: boolean;
  reply_text: string | null;
  hidden: boolean;
  done: boolean;
  like_count: number | null;
  commented_at: string | null;
  post_title: string | null;
  idea_id: number | null;
  parent_ig_id?: string | null;
  from_owner?: boolean;
  replies?: Comment[];
}
export interface Comments { available: boolean; items: Comment[]; counts: Record<string, number>; note?: string }
export interface Mention { id: number; username: string; caption: string | null; permalink: string | null; posted_at: string | null }
export interface Share { label: string; value: number; share: number }
export interface AudienceData {
  available: boolean;
  source?: string;
  fetched_at?: string | null;
  age: Share[];
  gender: Share[];
  cities: Share[];
  countries: Share[];
  most_active_hours: { hour: number; value: number }[];
  best_times: { hour: number; label: string; followers_online: number; share: number }[];
  recommendation: string | null;
  note?: string;
}
export interface FollowerDay { date: string; followers: Num; follows: Num; unfollows: Num; [k: string]: unknown }

export const v3 = {
  comments: (filter: string) => request<Comments>("GET", "/api/comments", { query: { filter } }),
  reply: (id: number, text: string) => request<{ ok: boolean; simulated?: boolean; note?: string }>("POST", `/api/comments/${id}/reply`, { body: { text } }),
  hide: (id: number, hide: boolean) => request<unknown>("POST", `/api/comments/${id}/hide`, { body: { hide } }),
  done: (id: number) => request<unknown>("POST", `/api/comments/${id}/done`),
  toIdea: (id: number) => request<{ id: number; existing?: boolean }>("POST", `/api/comments/${id}/to-idea`),
  mentions: () => request<{ items: Mention[] }>("GET", "/api/mentions"),
  audience: () => request<AudienceData>("GET", "/api/audience"),
};

// ---------- Growth (v4): own-data features ----------
export interface SegmentRow { segment: string; label: string; n: number; posts: number; inferred: number; shares_per_1k: Num; saves_per_1k: Num; views_per_1k_reach: Num; confidence: string }
export interface Segments { segments: SegmentRow[]; headline: string | null; note: string }
export interface SubScore { label: string; score: number; reasons: string[] }
export interface Shareability {
  score: number;
  band: string;
  subscores: Record<string, SubScore>;
  tip: string | null;
  calibration: { groups: { by: string; label: string; n: number; median_shares_per_1k: number; confidence: string; text: string }[]; account_median: Num } | null;
  note: string;
  audience?: AudienceTag;
}
export interface FatigueItem { dimension: string; group: string; label: string; headline: string; suggestion: string; confidence?: string; count?: number; of?: number }
export interface Fatigue {
  window: number;
  repetitive: FatigueItem[];
  near_duplicates: { post_id: number; title: string; similar_to: Similar }[];
  declining: FatigueItem[];
  ok: boolean;
  note: string;
}
export interface Gap {
  theme: string;
  count: number;
  likes: number;
  covered: boolean;
  covered_by: { kind: string; id: number; text: string } | null;
  suggested_title: string;
  comments: { id: number; username: string | null; text: string; like_count: Num }[];
}
export interface Gaps { gaps: Gap[]; covered: Gap[]; questions_considered: number; note: string }
export interface Voice { tone_words: string[]; banned_words: string[]; preferred_cta: string | null; signature_hashtags: string[]; emoji_level: string }
export interface VoiceLint { score: number; ok: boolean; issues: { kind: string; severity: string; message: string }[] }
export interface ScriptBeat { start: number; end: number; label: string; voiceover: string; on_screen: string; visual: string }
export interface ReelScript { source: string; topic: string; audience: string; duration_seconds: number; hook: string; beats: ScriptBeat[]; caption: string; shot_list: string[] }
export interface WindowRow { label: string; n: number; median_multiple: number; median_shares_per_1k: Num; confidence: string }
export interface Schedule {
  windows: WindowRow[];
  weekdays: WindowRow[];
  online_peaks: { hour: number; label: string; followers_online: number; share: number }[];
  best: WindowRow | null;
  recommendation: string;
  sample_size: number;
  note: string;
}

export const AUDIENCE_LABEL: Record<string, string> = {
  beginners: "Beginners",
  developers: "Developers",
  ai_enthusiasts: "AI enthusiasts",
  students: "Students",
  career: "Career switchers & job seekers",
};

export const v4 = {
  segments: () => request<Segments>("GET", "/api/growth/segments"),
  fatigue: () => request<Fatigue>("GET", "/api/growth/fatigue"),
  gaps: () => request<Gaps>("GET", "/api/growth/gaps"),
  gapToIdea: (title: string, comment_ids: number[]) => request<{ id: number }>("POST", "/api/growth/gaps/to-idea", { body: { title, comment_ids } }),
  schedule: () => request<Schedule>("GET", "/api/growth/schedule"),
  shareability: (body: { text: string; category?: string | null; format?: string | null }) => request<Shareability>("POST", "/api/create/shareability", { body }),
  reelScript: (body: { topic: string; audience: Audience; hook?: string | null; duration: number; category?: string }) =>
    request<ReelScript>("POST", "/api/create/reel-script", { body }),
  voice: () => request<Voice>("GET", "/api/voice"),
  saveVoice: (body: Voice) => request<Voice>("PUT", "/api/voice", { body }),
  voiceCheck: (text: string) => request<VoiceLint>("POST", "/api/create/voice-check", { body: { text } }),
};

// ---------- v5: interests, recommendations, ideas bulk, Instagram capabilities ----------
export interface Reason { text: string; source: string; source_label: string; confidence: string; sample: Num }
export interface Recommendation {
  id: number;
  topic: string;
  category: string | null;
  category_label: string;
  idea_id: number | null;
  kind: string;
  for_who: { segment: string; label: string; inferred: boolean };
  reasons: Reason[];
  flags: string[];
  confidence: string;
  hook: { text: string; formula: string | null; on_screen: string | null; score: number; verdict: string | null };
  best_time: { label: string; why: string; source: string; source_label: string; confidence: string };
  feedback: "made_it" | "not_for_me" | null;
  created_at: string | null;
  /** Set when the AI rewrote this pick from the data's evidence. */
  data_topic?: string;
  angle?: string;
  ai_why?: string;
  written_by?: string;
}
export interface Recommendations {
  items: Recommendation[];
  inputs: { reels_with_numbers: number; interest_items: number; comment_questions: number; ideas: number; feedback: number };
  note: string;
  mode: string;
  written_by?: string;
}
export interface InterestCategory { category: string; label: string; share: number; matches: number; evidence: string[]; confidence: string }
export interface InterestProfile {
  counts: { saved: number; liked: number; following: number; topic: number; manual: number };
  total: number;
  top_creators: { creator: string; n: number; sources: Record<string, number> }[];
  collections: { name: string; n: number; category: string | null }[];
  monthly: { month: string; saved: number; liked: number }[];
  categories: InterestCategory[];
  topics: string[];
  notes: { id: number; url: string | null; note: string | null; creator: string | null; at: string | null }[];
  last_import_at: string | null;
  inferred_note: string;
  mode?: string;
}
export interface ImportResult {
  added: Record<string, number>;
  added_total: number;
  files_used: string[];
  files_skipped: number;
  errors: string[];
  hint: string | null;
  partition: string;
}
export interface Capability { what: string; plain: string; status: "used" | "needs_server" | "not_possible" | "not_used" | string; why: string | null }

async function upload<T>(path: string, files: File[]): Promise<T> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f, f.name);
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { method: "POST", body: fd, cache: "no-store" });
  } catch {
    throw new ApiError(`Cannot reach the API at ${API_URL}. Is the backend running?`, 0);
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) {
    const { message, problems } = parseErrorBody(body, res.status);
    throw new ApiError(message, res.status, problems, body);
  }
  return body as T;
}

export const v5 = {
  recommendations: () => request<Recommendations>("GET", "/api/recommendations/next"),
  recommendationFeedback: (id: number, verdict: "made_it" | "not_for_me" | "clear") => request<Recommendation>("POST", `/api/recommendations/${id}/feedback`, { body: { verdict } }),
  saveRecommendation: (id: number) => request<{ idea_id: number; created: boolean }>("POST", `/api/recommendations/${id}/save`),
  recommendationHistory: () => request<Recommendation[]>("GET", "/api/recommendations/history"),
  interests: () => request<InterestProfile>("GET", "/api/interests/profile"),
  addInterest: (body: { url?: string | null; note: string; creator?: string | null }) => request<{ id: number; creator: string | null }>("POST", "/api/interests/manual", { body }),
  deleteInterest: (id: number) => request<unknown>("DELETE", `/api/interests/items/${id}`),
  importInterests: (files: File[]) => upload<ImportResult>("/api/interests/import", files),
  ideas: (q: { search?: string; status?: string; pillar?: string }) =>
    request<Page<ContentIdea>>("GET", "/api/content", { query: { ...q, page_size: 100, sort: "updated", order: "desc" } }),
  cloneIdea: (id: number) => request<ContentIdea>("POST", `/api/content/${id}/clone`),
  deleteIdea: (id: number) => request<unknown>("DELETE", `/api/content/${id}`),
  bulkIdeas: (ids: number[], action: "delete" | "archive" | "move" | "restore", status?: string) =>
    request<{ ok: boolean; affected: number }>("POST", "/api/ideas/bulk", { body: { ids, action, status } }),
  capabilities: () => request<Capability[]>("GET", "/api/instagram/capabilities"),
};

export interface CoachBrief {
  available: boolean;
  source: string;
  headline?: string | null;
  working?: string[];
  fix?: string[];
  this_week?: string[];
  note?: string;
}

// ---------- Reel Planner (Ideas → Reel Planner) ----------
export const REEL_PLATFORMS = ["instagram_reels", "youtube_shorts", "tiktok"] as const;
export type ReelPlatform = (typeof REEL_PLATFORMS)[number];
export const REEL_SECTIONS = ["hooks", "script", "shots", "caption", "cta"] as const;
export type ReelSection = (typeof REEL_SECTIONS)[number];

export interface TrendSource { title: string; url: string }
export interface TrendTopic {
  title: string;
  why_trending: string;
  angle: string;
  engagement_potential: "high" | "medium" | "low";
  potential_reason: string;
  sources: TrendSource[];
}
export interface TrendReport {
  niche: string;
  platform: ReelPlatform;
  topics: TrendTopic[];
  live_research_performed: boolean;
  disclosure: string;
  source: string;
  provider: string;
  search_results_found: number;
}
export interface ReelHook { text: string; hook_type: string; why_it_works: string }
export interface ReelScriptSection { section: "hook" | "setup" | "value" | "payoff" | "cta"; t_start: number; t_end: number; spoken: string; on_screen_text: string }
export interface ReelShot {
  order: number;
  shot_type: string;
  framing: string;
  location: string;
  action: string;
  delivery_tone: string;
  b_roll: string[];
  seconds: number;
}
export interface ReelPackage {
  topic: string;
  platform: ReelPlatform;
  audience: string;
  one_idea: string;
  hooks: ReelHook[];
  script: ReelScriptSection[];
  shots: ReelShot[];
  total_duration_seconds: number;
  caption: string;
  hashtags: string[];
  pinned_comment: string;
  cta_primary: string;
  cta_alternative: string;
  audio_direction: string;
  best_posting_time: string;
  ab_test_idea: string;
}
export interface SavedReelPlan {
  id: number;
  niche: string;
  platform: ReelPlatform;
  title: string;
  topic: Partial<TrendTopic>;
  package: ReelPackage;
  duration_seconds: number | null;
  source: string | null;
  live_research: boolean;
  idea_id: number | null;
  created_at: string | null;
  updated_at?: string | null;
  saved?: boolean;
}
export interface ReelPlanSummary {
  id: number;
  title: string;
  niche: string;
  platform: ReelPlatform;
  duration_seconds: number | null;
  source: string | null;
  live_research: boolean;
  hook: string | null;
  created_at: string | null;
}
export interface ReelMeta {
  niche: string;
  platforms: { value: ReelPlatform; label: string }[];
  default_platform: ReelPlatform;
  sections: ReelSection[];
  live_research_available: boolean;
  research_provider: string;
  video_autoedit_available: boolean;
  note: string;
}

export const reels = {
  meta: () => request<ReelMeta>("GET", "/api/reels/meta"),
  trends: (body: { niche: string; platform: ReelPlatform; count?: number; audience?: string | null }) =>
    request<TrendReport>("POST", "/api/reels/trends", { body }),
  plan: (body: { niche: string; platform: ReelPlatform; topic: TrendTopic; duration?: number; audience?: string | null; save?: boolean }) =>
    request<SavedReelPlan>("POST", "/api/reels/plan", { body }),
  plans: () => request<{ items: ReelPlanSummary[] }>("GET", "/api/reels/plans"),
  getPlan: (id: number) => request<SavedReelPlan>("GET", `/api/reels/plans/${id}`),
  regenerate: (id: number, section: ReelSection) =>
    request<SavedReelPlan & { section: ReelSection }>("POST", `/api/reels/plans/${id}/regenerate`, { body: { section } }),
  deletePlan: (id: number) => request<void>("DELETE", `/api/reels/plans/${id}`),
};
