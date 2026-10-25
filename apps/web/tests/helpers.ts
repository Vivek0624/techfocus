import { vi } from "vitest";

export type Route = [RegExp | string, unknown | ((url: string, init?: RequestInit) => unknown), number?];

export function json(body: unknown, status = 200) {
  return new Response(body === undefined ? "" : JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

/** Install a fetch mock that answers by URL pattern (first match wins). */
export function mockFetch(routes: Route[]) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    for (const [pat, body, status] of routes) {
      const key = `${method} ${url}`;
      const hit = typeof pat === "string" ? key.includes(pat) : pat.test(key);
      if (hit) {
        const b = typeof body === "function" ? (body as (u: string, i?: RequestInit) => unknown)(url, init) : body;
        return json(b, status ?? 200);
      }
    }
    return json({ error: `unmocked ${method} ${url}` }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}

export const calls = (fn: ReturnType<typeof mockFetch>) => fn.mock.calls.map((c) => `${(c[1] as RequestInit | undefined)?.method ?? "GET"} ${String(c[0])}`);

export const metrics = {
  days: 30, followers_start: 366, followers_end: 602, net_follower_growth: 236, pct_follower_growth: 64.48, followers_gained: 289, followers_lost: 50,
  reach: 91997, views: null, accounts_engaged: 3665, likes: 4126, comments: 260, shares: 536, saves: 627, profile_links_taps: 75, follows_per_1k_reach: 3.14,
  sources: ["demo"], last_refresh: "2026-10-22T12:24:21",
};

export const dashboard = {
  mode: "demo",
  range: { start: "2026-09-22", end: "2026-10-22", days: 30 },
  account: { mode: "demo", username: "demo_techfocus (SYNTHETIC)", account_type: "MEDIA_CREATOR", followers: 602, source: "demo", last_refresh: "2026-10-22T12:24:21" },
  metrics,
  metric_sources: { followers: "demo", "reach/views/interactions": "demo", engagement_rate_by_reach: "calculated", follows_per_1k_reach: "calculated" },
  limitations: ["Insights can lag up to 48 hours."],
  posts_published: 10, engagement_rate_by_reach: 7.06, reach_per_post: 9561.6,
  best_reels: [], recent_posts: [],
  target: { configured: false },
  upcoming: [], top_action: null, recent_agent_runs: [],
};

export const settings = {
  app_env: "local", agent_mode: "mock", aws_region: "us-east-1", bedrock_model_id: null, agentcore_runtime_configured: false, aws_profile: null,
  meta_app_configured: false, token_encryption_key_set: false, meta_redirect_uri: "http://localhost:8001/api/instagram/callback", meta_scopes: [],
  s3_media_bucket: null, research_provider_configured: false, local_scheduler: false, data_mode: "demo", prefer_real_data: false,
  brand: { handle: "vivek_techfocus", posts_per_week: 5, hours_per_week: 8 },
};

export function run(over: Record<string, unknown> = {}) {
  return {
    id: 42, agent_id: "reel_creative", parent_run_id: null, mode: "mock", status: "queued", input_summary: "topic=APIs", input: { topic: "APIs" },
    output_summary: null, output: {}, error: null, started_at: null, finished_at: null, duration_ms: null, input_tokens: null, output_tokens: null,
    est_cost_usd: null, created_at: "2026-10-22T12:00:00", is_demo: true, tools_called: [], ...over,
  };
}
