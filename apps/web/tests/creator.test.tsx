import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { TodayPage } from "@/components/creator/today";
import { BoardView, QuickCapture } from "@/components/creator/ideas";
import { CreatePage } from "@/components/creator/create";
import { InsightsPage } from "@/components/creator/insights";
import { ConnectPage } from "@/components/creator/connect";
import { NAV, SETTINGS_NAV, Shell } from "@/components/shell";
import { ThemeToggle, THEME_KEY } from "@/components/theme";
import { calls, dashboard, mockFetch, settings } from "./helpers";

const search = { value: new URLSearchParams() };
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useSearchParams: () => search.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const bodyOf = (f: ReturnType<typeof mockFetch>, needle: string) => {
  const c = f.mock.calls.filter((x) => `${(x[1] as RequestInit | undefined)?.method ?? "GET"} ${String(x[0])}`.includes(needle));
  return c.map((x) => JSON.parse(String((x[1] as RequestInit).body)));
};

beforeEach(() => {
  search.value = new URLSearchParams();
});

const goal = { configured: true, current: 602, target: 10000, required_per_day: 626.5, actual_per_day: 17.5, days_remaining: 15, on_pace: false };
const today = {
  mode: "demo",
  suggestion: {
    idea_id: 1,
    title: "Your English isn't why you fail interviews",
    status: "ready",
    step: "Post it",
    category: "career",
    hook: "Your English isn't why you fail interviews",
    hook_score: { score: 62, verdict: "OK", checks: {}, fix: "Weakest: frontload" },
    alt_hooks: [{ text: "Nobody tells beginners this about interviews.", formula: "Nobody Tells You", on_screen: "X", score: 88, verdict: "STRONG", fix: null }],
    caption: "Your English isn't why you fail interviews\n\nSave this.",
    hashtags: ["#careertips", "#techindia"],
    why: "Next in your pipeline.",
  },
  tip: { kind: "outlier", headline: "A post ran 69x your usual views.", action: "Make a follow-up.", confidence: "low" },
  goal,
  week: { published: 2, target: 5 },
  pipeline_counts: {},
  reminders: [],
  tasks: [{ id: 2, title: "Record it", done: false }],
};

const recs = {
  mode: "demo",
  note: "n",
  inputs: { reels_with_numbers: 10, interest_items: 20, comment_questions: 2, ideas: 3, feedback: 0 },
  items: [
    {
      id: 7,
      topic: "The interview question freshers get wrong",
      category: "career",
      category_label: "Jobs & career",
      idea_id: null,
      kind: "starter",
      for_who: { segment: "career", label: "Career switchers & job seekers", inferred: true },
      reasons: [
        { text: "Your jobs & career reels get 3.2x your usual shares per 1,000 people reached (n=4).", source: "reels", source_label: "Your reels", confidence: "medium", sample: 4 },
        { text: "It matches what you're into: 40% of your saves point to jobs & career. Inferred.", source: "interests", source_label: "Your saves & likes", confidence: "low", sample: 8 },
      ],
      flags: [],
      confidence: "medium",
      hook: { text: "Most freshers answer this wrong.", formula: null, on_screen: null, score: 70, verdict: "STRONG" },
      best_time: { label: "Post around 8 PM IST", why: "That's when most of your followers are on Instagram.", source: "audience", source_label: "Instagram audience data", confidence: "medium" },
      feedback: null,
      created_at: null,
    },
  ],
};
const emptyInterests = { counts: { saved: 0, liked: 0, following: 0, topic: 0, manual: 0 }, total: 0, top_creators: [], collections: [], monthly: [], categories: [], topics: [], notes: [], last_import_at: null, inferred_note: "" };

describe("Navigation", () => {
  it("has exactly the 5 items plus settings", () => {
    mockFetch([["/api/settings", settings]]);
    wrap(<Shell><div /></Shell>);
    expect(NAV.map((n) => n.label)).toEqual(["Home", "Ideas", "Create", "Insights", "Profile"]);
    expect(SETTINGS_NAV.href).toBe("/settings");
    const main = screen.getByRole("navigation", { name: "Main" });
    const links = within(main).getAllByRole("link").map((a) => a.textContent);
    expect(links).toEqual(["Home", "Ideas", "Create", "Insights", "Profile"]);
    expect(within(screen.getByRole("navigation", { name: "Tabs" })).getAllByRole("link")).toHaveLength(5);
    expect(screen.getAllByRole("link", { name: "Settings" }).length).toBeGreaterThan(0);
  });
});

describe("Today", () => {
  it("shows the next reel with sourced reasons, prefilled Create link, feedback and the step guide", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const f = mockFetch([
      ["PATCH http://localhost:8001/api/content/1", { id: 1 }],
      ["POST http://localhost:8001/api/recommendations/7/feedback", { id: 7, feedback: "not_for_me" }],
      ["POST http://localhost:8001/api/recommendations/7/save", { idea_id: 12, created: true }, 201],
      ["/api/recommendations/next", recs],
      ["/api/interests/profile", { ...emptyInterests }],
      ["/api/today", { ...today, pipeline_counts: { idea: 4, ready: 1 } }],
      ["/api/dashboard", { ...dashboard, metrics: { ...dashboard.metrics, net_follower_growth: 42 } }],
      ["/api/comments", { available: true, items: [], counts: { needs_reply: 0 } }],
    ]);
    wrap(<TodayPage />);
    expect(await screen.findByTestId("rec-topic")).toHaveTextContent("The interview question freshers get wrong");
    expect(screen.getByTestId("today-hook")).toHaveTextContent("Most freshers answer this wrong.");
    const reasons = screen.getByTestId("rec-reasons");
    expect(within(reasons).getByText("Your reels")).toBeInTheDocument();
    expect(within(reasons).getByText(/3.2x your usual shares/)).toBeInTheDocument();
    expect(within(reasons).getByText("Your saves & likes")).toBeInTheDocument();
    expect(screen.getByTestId("best-time")).toHaveTextContent("Post around 8 PM IST");
    const write = screen.getByRole("link", { name: /Write script/ });
    expect(write.getAttribute("href")).toContain("topic=The+interview+question");
    expect(write.getAttribute("href")).toContain("hook=Most+freshers");
    expect(screen.getByText("Post it")).toBeInTheDocument();
    expect(screen.getByTestId("gained")).toHaveTextContent("+42");
    expect(screen.getByTestId("followers")).toHaveTextContent("602 followers");
    expect(screen.getByRole("link", { name: "Activity" })).toHaveAttribute("href", "/activity");
    expect(screen.getByText(/You need ~627\/day; you're doing ~18\/day/)).toBeInTheDocument();
    expect(within(screen.getByTestId("step-guide")).getByText("Check results after 48h")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Copy hook" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith("Most freshers answer this wrong."));
    fireEvent.click(screen.getByRole("button", { name: /Save to ideas/ }));
    await waitFor(() => expect(calls(f)).toContain("POST http://localhost:8001/api/recommendations/7/save"));
    fireEvent.click(screen.getByRole("button", { name: /Not for me/ }));
    await waitFor(() => expect(bodyOf(f, "POST http://localhost:8001/api/recommendations/7/feedback")).toEqual([{ verdict: "not_for_me" }]));
    fireEvent.click(screen.getByRole("button", { name: /Mark done → Published/ }));
    await waitFor(() => expect(bodyOf(f, "PATCH http://localhost:8001/api/content/1")).toEqual([{ status: "published" }]));
  });

  it("shows the quick-capture empty state when there's no suggestion", async () => {
    const f = mockFetch([
      ["POST http://localhost:8001/api/ideas/quick", { id: 9, status: "idea" }, 201],
      ["/api/today", { ...today, suggestion: null, goal: { configured: false } }],
    ]);
    wrap(<TodayPage />);
    expect(await screen.findByText("Capture your first idea")).toBeInTheDocument();
    expect(screen.getByText("Set your goal")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Your idea"), { target: { value: "APIs with chai" } });
    fireEvent.click(screen.getByRole("button", { name: "Save idea" }));
    await waitFor(() => expect(bodyOf(f, "POST http://localhost:8001/api/ideas/quick")[0]).toMatchObject({ title: "APIs with chai" }));
  });
});

describe("Ideas", () => {
  it("quick capture shows the duplicate warning on 409 and 'Add anyway' resends with force", async () => {
    const f = mockFetch([
      ["/api/ideas/check-duplicate", { similar: [] }],
      ["POST http://localhost:8001/api/ideas/quick", { id: 10, status: "idea" }, 201],
    ]);
    // The first POST /ideas/quick answers 409 with the similar list.
    f.mockImplementationOnce(async () =>
      new Response(JSON.stringify({ error: { message: "Looks similar", similar: [{ kind: "idea", id: 4, text: "How Instagram's feed learns", similarity: 1 }] } }), { status: 409 }),
    );
    const onAdded = vi.fn();
    wrap(<QuickCapture onAdded={onAdded} />);
    fireEvent.change(screen.getByLabelText("Idea title"), { target: { value: "How the Instagram feed learns" } });
    fireEvent.click(screen.getByRole("button", { name: /Add$/ }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Looks similar to something you already have");
    expect(alert).toHaveTextContent("How Instagram's feed learns");
    fireEvent.click(within(alert).getByRole("button", { name: "Add anyway" }));
    await waitFor(() => expect(onAdded).toHaveBeenCalled());
    const quick = bodyOf(f, "POST http://localhost:8001/api/ideas/quick");
    expect(quick.at(-1)).toMatchObject({ title: "How the Instagram feed learns", force: true });
    expect(quick[0].force).toBe(false);
  });

  it("board moves a card to the next stage", async () => {
    const f = mockFetch([["PATCH http://localhost:8001/api/content/3", { id: 3 }]]);
    const board = {
      columns: [
        { status: "idea", items: [] },
        { status: "script", items: [{ id: 3, title: "ChatGPT vs a chai stall", category: "tech_concepts", hook: "h", format: null, updated_at: "", planned_at: null, calendar_id: null }] },
      ],
      categories: ["ai", "tech_concepts"],
      formats: [],
    };
    const onChange = vi.fn();
    wrap(<BoardView board={board} onChange={onChange} onOpen={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: "Move ChatGPT vs a chai stall to Recording" }));
    await waitFor(() => expect(bodyOf(f, "PATCH http://localhost:8001/api/content/3")).toEqual([{ status: "recording" }]));
    expect(onChange).toHaveBeenCalled();
  });
});

const hooksRes = {
  source: "template",
  note: "Scores catch weak hooks.",
  hooks: [
    { text: "Low hook", formula: "Negative Command", on_screen: "LOW", score: 44, verdict: "WEAK", fix: "Weakest: stakes" },
    { text: "Top hook", formula: "Story Open", on_screen: "TOP", score: 73, verdict: "STRONG", fix: null },
  ],
};
const captionRes = {
  source: "template",
  first_line: "Top hook",
  body: "b",
  cta: "c",
  keywords: ["apis"],
  hashtags: ["#techindia", "#learncoding"],
  full: "Top hook\n\nHere's APIs even if you've never coded. More words here.\n\n#techindia #learncoding",
  preview_cut: "Top hook\n\nHere's APIs even if... more",
  length: 84,
  max: 2200,
};
const repurposeRes = {
  source: "template",
  audience: "beginner",
  reel_30s: [{ t: "0-3s", say: "Hi", screen: "HI" }],
  carousel: [1, 2, 3, 4, 5].map((i) => ({ title: `Slide ${i}`, text: "t" })),
  linkedin_post: "LI",
  youtube_short: "YT",
  text_post: "TP",
};

describe("Create", () => {
  it("renders hooks sorted by score; 'Use this' sets the hook used by Caption", async () => {
    const f = mockFetch([
      ["/api/create/hooks", hooksRes],
      ["/api/create/caption", captionRes],
    ]);
    wrap(<CreatePage />);
    fireEvent.change(screen.getByLabelText("What's the post about?"), { target: { value: "APIs" } });
    fireEvent.click(screen.getByRole("button", { name: /Write hooks/ }));
    await screen.findByTestId("hook-list");
    expect(screen.getAllByTestId("hook-text").map((e) => e.textContent)).toEqual(["Top hook", "Low hook"]);
    expect(bodyOf(f, "/api/create/hooks")[0]).toEqual({ topic: "APIs", audience: "beginner", perspective: "third" });
    fireEvent.click(screen.getAllByRole("button", { name: "Use this" })[0]);
    fireEvent.click(screen.getByRole("tab", { name: "Caption" }));
    fireEvent.click(screen.getByRole("button", { name: /Write caption/ }));
    await screen.findByTestId("ig-preview");
    expect(bodyOf(f, "/api/create/caption")[0]).toMatchObject({ topic: "APIs", hook: "Top hook" });
  });

  it("caption preview shows '... more' and a character counter", async () => {
    mockFetch([["/api/create/caption", captionRes]]);
    wrap(<CreatePage />);
    fireEvent.change(screen.getByLabelText("What's the post about?"), { target: { value: "APIs" } });
    fireEvent.click(screen.getByRole("tab", { name: "Caption" }));
    fireEvent.click(screen.getByRole("button", { name: /Write caption/ }));
    const preview = await screen.findByTestId("ig-preview");
    expect(within(preview).getByRole("button", { name: "... more" })).toBeInTheDocument();
    expect(screen.getByTestId("char-count")).toHaveTextContent(/\/ 2200 characters/);
    fireEvent.click(within(preview).getByRole("button", { name: "... more" }));
    expect(preview).toHaveTextContent("More words here.");
  });

  it("repurpose renders 5 carousel slides", async () => {
    mockFetch([["/api/create/repurpose", repurposeRes]]);
    wrap(<CreatePage />);
    fireEvent.change(screen.getByLabelText("What's the post about?"), { target: { value: "APIs" } });
    fireEvent.click(screen.getByRole("tab", { name: "Repurpose" }));
    fireEvent.click(screen.getByRole("button", { name: /Turn into 5 posts/ }));
    await screen.findByTestId("carousel");
    expect(screen.getAllByTestId("slide")).toHaveLength(5);
    for (const t of ["30-second Reel", "LinkedIn post", "YouTube Short script", "Text post"]) expect(screen.getByText(t)).toBeInTheDocument();
  });
});

describe("Insights", () => {
  it("renders coach sentences and Repeat / Improve / Stop", async () => {
    mockFetch([
      [
        "/api/insights",
        {
          sample_size: 14,
          tagged: 13,
          summary: { median_views: 2003, median_shares_per_1k: 5.4, median_saves_per_1k: 9.7, median_watch_seconds: null },
          insights: [
            { kind: "pattern", headline: "Your tech concepts posts get 5.7x more shares.", detail: "Tech concepts: median 8.25 shares per 1,000 reached (n=4).", action: "Make your next post about tech concepts again.", confidence: "medium" },
          ],
          answers: {
            best_hooks: [{ group: "x", label: "Head To Head", n: 2, median: 1.4 }],
            topics_by_shares: [],
            formats: [],
            lengths: [],
            repeat: ["Topic: tech concepts"],
            improve: ["Add a share moment"],
            stop: ["Nothing to stop yet."],
          },
          posts: [{ id: 1, title: "Post A", caption: null, published_at: "2026-10-21T07:30:00+00:00", views: 2000, reach: 1400, shares: 10, saved: 5, avg_watch_time_ms: 15000, multiple: 1, pillar: null, format_style: null, length_seconds: null, hook_text: null }],
          note: "Compared against your own posts only.",
        },
      ],
      ["/api/audience", { available: false, recommendation: "r", note: "n", age: [], gender: [], cities: [], countries: [], most_active_hours: [], best_times: [] }],
    ]);
    wrap(<InsightsPage />);
    const coach = await screen.findByTestId("coach");
    expect(within(coach).getByText("Your tech concepts posts get 5.7x more shares.")).toBeInTheDocument();
    expect(within(coach).getByText(/based on 4 posts/)).toBeInTheDocument();
    expect(within(coach).getByText("likely")).toBeInTheDocument();
    const ris = screen.getByTestId("ris");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    for (const t of ["Repeat", "Improve", "Stop"]) expect(within(ris).getByText(t)).toBeInTheDocument();
    expect(within(screen.getByTestId("stat-Average watch time")).getByText("unavailable")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Content" }));
    expect(screen.getByText("Tag me")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Audience" }));
    expect(await screen.findByTestId("audience-tab")).toBeInTheDocument();
  });
});

describe("Connect", () => {
  it("shows step states and the CSV import result", async () => {
    const f = mockFetch([
      [
        "/api/instagram/status",
        { app_configured: false, encryption_key_set: true, connected: false, username: null, account_type: null, last_sync_at: null, last_error: null, token: { state: "missing" }, permissions: [], auth_flow: "", requirements: ["redirect URI http://localhost:8001/api/instagram/callback added."] },
      ],
      ["/api/posts/csv-template", { columns: ["date", "title"], example: "2026-10-02,x" }],
      ["/api/posts/import-csv", { added: 2, errors: ["row 4: bad date"] }],
      ["/api/settings", { ...settings, data_mode: "manual" }],
    ]);
    wrap(<ConnectPage />);
    expect(await screen.findByTestId("step-keys")).toHaveAttribute("data-done", "false");
    expect(screen.getByTestId("step-creator")).toHaveAttribute("data-done", "false");
    expect(screen.getByText(/META_APP_ID=/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect Instagram" })).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: "Import CSV" }));
    fireEvent.change(screen.getByLabelText("CSV text"), { target: { value: "date,title\n2026-10-01,A" } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    const res = await screen.findByTestId("csv-result");
    expect(res).toHaveTextContent("Added 2 posts.");
    expect(res).toHaveTextContent("row 4: bad date");
    expect(calls(f)).toContain("POST http://localhost:8001/api/posts/import-csv");
  });
});

describe("Theme", () => {
  it("toggling sets the dark class / data-theme and saves the override", () => {
    const root = document.documentElement;
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("radio", { name: /Dark/ }));
    expect(root.classList.contains("dark")).toBe(true);
    expect(root.dataset.theme).toBe("dark");
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    fireEvent.click(screen.getByRole("radio", { name: /Light/ }));
    expect(root.classList.contains("dark")).toBe(false);
    expect(root.dataset.theme).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    fireEvent.click(screen.getByRole("radio", { name: /System/ }));
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });
});

const comment = {
  id: 4, username: "sneha.learns", text: "What should I say when I don't know the answer?", intent: "question",
  draft_reply: "@sneha.learns Good question.", replied: false, reply_text: null, hidden: false, done: false, like_count: 36,
  commented_at: "2026-10-21T11:30:00+00:00", post_title: "How to speak confidently", idea_id: null,
};

describe("Activity", () => {
  it("renders needs-reply rows; Send posts the edited text; Turn into idea links to Ideas", async () => {
    const { ActivityPage } = await import("@/components/creator/activity");
    const f = mockFetch([
      ["/api/comments/4/reply", { ok: true, simulated: true, note: "Demo mode: not sent to Instagram." }],
      ["/api/comments/4/to-idea", { id: 12, existing: false }],
      ["/api/comments", { available: true, items: [comment], counts: { needs_reply: 1, question: 1 }, note: "Replies are sent only when you press Send." }],
    ]);
    wrap(<ActivityPage />);
    const row = await screen.findByTestId("comment-4");
    expect(row).toHaveTextContent("sneha.learns");
    expect(within(row).getByText("Question")).toBeInTheDocument();
    expect(calls(f)[0]).toContain("filter=needs_reply");
    const box = within(row).getByLabelText("Reply to sneha.learns");
    expect(box).toHaveValue("@sneha.learns Good question.");
    fireEvent.change(box, { target: { value: "@sneha.learns Say: let me think it through." } });
    fireEvent.click(within(row).getByRole("button", { name: "Send" }));
    await waitFor(() => expect(bodyOf(f, "/api/comments/4/reply")).toEqual([{ text: "@sneha.learns Say: let me think it through." }]));
    expect(await within(row).findByText("Demo mode: not sent to Instagram.")).toBeInTheDocument();
    fireEvent.click(within(row).getByRole("button", { name: "Turn into idea" }));
    expect(await within(row).findByRole("link", { name: /Open in Ideas/ })).toHaveAttribute("href", "/ideas");
    expect(calls(f)).toContain("POST http://localhost:8001/api/comments/4/to-idea");
  });
});

const audience = {
  available: true, source: "demo", fetched_at: null,
  age: [{ label: "18-24", value: 172, share: 50.7 }],
  gender: [{ label: "M", value: 241, share: 71.1 }, { label: "F", value: 93, share: 27.4 }],
  cities: [{ label: "Pune, Maharashtra", value: 64, share: 29.9 }],
  countries: [{ label: "IN", value: 309, share: 93.4 }],
  most_active_hours: Array.from({ length: 24 }, (_, h) => ({ hour: h, value: h === 19 ? 46 : 5 })),
  best_times: [{ hour: 19, label: "7 PM", followers_online: 46, share: 13.1 }],
  recommendation: "Most of your followers are online around 7 PM.",
  note: "Needs 100+ followers.",
};

describe("Audience", () => {
  it("renders bars and the best-time sentence", async () => {
    const { AudienceTab, bestTimeHint } = await import("@/components/creator/audience");
    mockFetch([["/api/audience", audience]]);
    wrap(<AudienceTab />);
    expect(await screen.findByText("Pune, Maharashtra")).toBeInTheDocument();
    expect(screen.getByText("Men")).toBeInTheDocument();
    expect(screen.getByText("Most of your followers are online around 7 PM.")).toBeInTheDocument();
    expect(screen.getByTestId("active-hours").children).toHaveLength(24);
    fireEvent.click(screen.getByRole("radio", { name: "Countries" }));
    expect(screen.getByText("India")).toBeInTheDocument();
    expect(bestTimeHint(audience)).toBe("Your followers peak around 7 PM. Post at 6:30 PM.");
  });

  it("shows the recommendation and note when unavailable", async () => {
    const { AudienceTab } = await import("@/components/creator/audience");
    mockFetch([["/api/audience", { ...audience, available: false, recommendation: "Post around 7 PM for now." }]]);
    wrap(<AudienceTab />);
    expect(await screen.findByText("Post around 7 PM for now.")).toBeInTheDocument();
    expect(screen.getByText("Needs 100+ followers.")).toBeInTheDocument();
    expect(screen.queryByText("Top locations")).toBeNull();
  });
});

describe("Followers", () => {
  it("renders follows / unfollows totals", async () => {
    const { FollowersSection } = await import("@/components/creator/audience");
    wrap(
      <FollowersSection
        history={[
          { date: "2026-09-22", followers: 366, follows: 5, unfollows: 2 },
          { date: "2026-09-23", followers: 369, follows: 4, unfollows: 1 },
        ]}
      />,
    );
    expect(screen.getByTestId("follows-total")).toHaveTextContent("9");
    expect(screen.getByTestId("unfollows-total")).toHaveTextContent("3");
    expect(screen.getByText("+3")).toBeInTheDocument();
  });
});
