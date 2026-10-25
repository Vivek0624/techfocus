import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Explain } from "@/components/ui/explain";
import { IdeasPage } from "@/components/creator/ideas";
import { ImportPanel, InterestsSummary } from "@/components/creator/interests";
import { SettingsPageV2 } from "@/components/creator/settings";
import { GLOSSARY } from "@/lib/glossary";
import { calls, mockFetch, settings } from "./helpers";

const toasts: { msg: string; opts?: { action?: { label: string; onClick: () => void } } }[] = [];
vi.mock("sonner", () => {
  const t = Object.assign((msg: string, opts?: { action?: { label: string; onClick: () => void } }) => toasts.push({ msg, opts }), {
    success: vi.fn(),
    error: vi.fn(),
  });
  return { toast: t, Toaster: () => null };
});

const search = { value: new URLSearchParams() };
vi.mock("next/navigation", () => ({
  usePathname: () => "/ideas",
  useSearchParams: () => search.value,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}));

const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const bodyOf = (f: ReturnType<typeof mockFetch>, needle: string) =>
  f.mock.calls.filter((x) => `${(x[1] as RequestInit | undefined)?.method ?? "GET"} ${String(x[0])}`.includes(needle)).map((x) => JSON.parse(String((x[1] as RequestInit).body)));

beforeEach(() => {
  search.value = new URLSearchParams();
  toasts.length = 0;
});
afterEach(() => vi.useRealTimers());

const idea = (id: number, title: string, over: Record<string, unknown> = {}) => ({
  id, title, pillar: null, audience_segment: null, audience: null, audience_problem: null, format: null, hook_options: [], recommended_hook: null, script: null, storyboard: [],
  on_screen_text: [], visual_direction: null, duration_seconds: null, caption: null, keywords: [], hashtags: [], cta: null, effort: null, evidence: [], hypothesis: null,
  status: "idea", planned_at: null, lessons: null, notes: null, package: {}, created_at: "2026-10-20T10:00:00", updated_at: "2026-10-21T10:00:00", published_media_id: null,
  performance: {}, is_demo: false, ...over,
});
const board = { columns: [{ status: "idea", items: [] }], categories: [], formats: [], audiences: [] };

describe("Explain", () => {
  it("shows the plain label and toggles the explanation on click", async () => {
    wrap(<Explain term="reach" />);
    expect(screen.getByText("People reached")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "What is People reached?" }));
    expect((await screen.findAllByText(/Different people who saw it at least once/)).length).toBeGreaterThan(0);
  });
  it("glossary covers the jargon the user asked about", () => {
    for (const k of ["reach", "views", "saves", "shares", "engagement", "hook", "carousel", "reel", "cta", "insights"]) expect(GLOSSARY[k]?.short).toBeTruthy();
  });
});

describe("Ideas notebook", () => {
  const routes = (items: unknown[]) => [
    ["PATCH http://localhost:8001/api/content/", { id: 1 }],
    ["POST http://localhost:8001/api/content/1/clone", idea(3, "APIs with chai (copy)"), 201],
    ["POST http://localhost:8001/api/ideas/bulk", { ok: true, affected: 1 }],
    ["/api/content", { items, total: items.length, page: 1, page_size: 100 }],
    ["/api/board", board],
    ["/api/ideas/check-duplicate", { similar: [] }],
  ] as Parameters<typeof mockFetch>[0];

  it("lists ideas, edits inline on blur, filters by search, duplicates", async () => {
    const f = mockFetch(routes([idea(1, "APIs with chai", { notes: "try the chai stall angle" }), idea(2, "Cloud explained")]));
    wrap(<IdeasPage />);
    expect(within(await screen.findByTestId("idea-list")).getByText("try the chai stall angle")).toBeInTheDocument();
    const editor = screen.getByTestId("idea-editor");
    const title = within(editor).getByLabelText("Title");
    fireEvent.change(title, { target: { value: "APIs explained with chai" } });
    fireEvent.blur(title);
    await waitFor(() => expect(bodyOf(f, "PATCH http://localhost:8001/api/content/1")).toEqual([{ title: "APIs explained with chai" }]));
    const notes = within(editor).getByLabelText(/Notes/);
    fireEvent.change(notes, { target: { value: "new note" } });
    fireEvent.blur(notes);
    await waitFor(() => expect(bodyOf(f, "PATCH http://localhost:8001/api/content/1").at(-1)).toEqual({ notes: "new note" }));
    fireEvent.click(within(editor).getByRole("button", { name: /Duplicate/ }));
    await waitFor(() => expect(calls(f)).toContain("POST http://localhost:8001/api/content/1/clone"));
    fireEvent.change(screen.getByLabelText("Search ideas"), { target: { value: "cloud" } });
    const list = screen.getByTestId("idea-list");
    expect(within(list).queryByText("try the chai stall angle")).toBeNull();
    expect(within(list).getByText("Cloud explained")).toBeInTheDocument();
  });

  it("bulk delete hides at once, offers Undo, and only deletes on the server if not undone", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const f = mockFetch(routes([idea(1, "APIs with chai"), idea(2, "Cloud explained")]));
    wrap(<IdeasPage />);
    await screen.findByLabelText("Select APIs with chai");
    fireEvent.click(screen.getByLabelText("Select APIs with chai"));
    const bar = screen.getByRole("toolbar", { name: "Bulk actions" });
    fireEvent.click(within(bar).getByRole("button", { name: /Delete/ }));
    expect(screen.queryByLabelText("Select APIs with chai")).toBeNull();
    const t = toasts.find((x) => x.msg.startsWith("Deleted"));
    expect(t?.opts?.action?.label).toBe("Undo");
    act(() => t!.opts!.action!.onClick());
    expect(await screen.findByLabelText("Select APIs with chai")).toBeInTheDocument();
    await act(async () => {
      vi.advanceTimersByTime(6000);
    });
    expect(calls(f)).not.toContain("POST http://localhost:8001/api/ideas/bulk");
    // now delete for real
    fireEvent.click(screen.getByLabelText("Select APIs with chai"));
    fireEvent.click(within(screen.getByRole("toolbar", { name: "Bulk actions" })).getByRole("button", { name: /Delete/ }));
    await act(async () => {
      vi.advanceTimersByTime(6000);
    });
    await waitFor(() => expect(bodyOf(f, "POST http://localhost:8001/api/ideas/bulk")).toEqual([{ ids: [1], action: "delete" }]));
  });

  it("bulk move sends the chosen stage", async () => {
    const f = mockFetch(routes([idea(1, "APIs with chai"), idea(2, "Cloud explained")]));
    wrap(<IdeasPage />);
    fireEvent.click(await screen.findByLabelText("Select all"));
    fireEvent.change(screen.getByLabelText("Move selected to"), { target: { value: "script" } });
    await waitFor(() => expect(bodyOf(f, "POST http://localhost:8001/api/ideas/bulk")).toEqual([{ ids: [1, 2], action: "move", status: "script" }]));
  });
});

describe("Interests", () => {
  it("uploads the Instagram download and shows what was added", async () => {
    const f = mockFetch([
      ["POST http://localhost:8001/api/interests/import", { added: { saved: 5, liked: 2 }, added_total: 7, files_used: ["saved_posts.json"], files_skipped: 0, errors: [], hint: null, partition: "live" }],
      ["/api/interests/profile", { counts: { saved: 5, liked: 2, following: 0, topic: 0, manual: 0 }, total: 7, top_creators: [], collections: [], monthly: [], categories: [], topics: [], notes: [], last_import_at: null, inferred_note: "" }],
    ]);
    wrap(<ImportPanel />);
    expect(screen.getByText(/Format: JSON/)).toBeInTheDocument();
    const file = new File(['{"saved_saved_media": []}'], "saved_posts.json", { type: "application/json" });
    fireEvent.change(screen.getByLabelText("Instagram data files"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "Import" }));
    expect(await screen.findByTestId("import-result")).toHaveTextContent("Added 7 new items: 5 saved, 2 liked.");
    const call = f.mock.calls.find((c) => String(c[0]).endsWith("/api/interests/import"))!;
    expect((call[1] as RequestInit).body).toBeInstanceOf(FormData);
  });

  it("summary labels guessed topics and lists creators", () => {
    wrap(
      <InterestsSummary
        p={{
          counts: { saved: 9, liked: 4, following: 2, topic: 1, manual: 1 },
          total: 17,
          top_creators: [{ creator: "aiexplained", n: 5, sources: { saved: 3, liked: 2 } }],
          collections: [],
          monthly: [],
          categories: [{ category: "ai", label: "AI & tools", share: 60, matches: 9, evidence: ["collection “AI tools”"], confidence: "low" }],
          topics: [],
          notes: [],
          last_import_at: null,
          inferred_note: "",
        }}
      />,
    );
    expect(screen.getByText("AI & tools")).toBeInTheDocument();
    expect(screen.getByText("Guessed")).toBeInTheDocument();
    expect(screen.getByText(/@aiexplained/)).toBeInTheDocument();
  });
});

describe("Settings", () => {
  it("has no demo reset button and lists what Instagram allows", async () => {
    search.value = new URLSearchParams("tab=instagram");
    mockFetch([
      ["/api/instagram/capabilities", [
        { what: "Comments and replies", plain: "Read comments", status: "used", why: null },
        { what: "Real-time comments and mentions", plain: "Instant alerts", status: "needs_server", why: "Needs webhooks" },
        { what: "Your saved and liked posts", plain: "What you save", status: "not_possible", why: "Import instead" },
      ]],
      ["/api/settings", settings],
      ["/api/growth/target", { configured: false }],
      ["/api/voice", { tone_words: [], banned_words: [], preferred_cta: null, signature_hashtags: [], emoji_level: "low" }],
    ]);
    wrap(<SettingsPageV2 />);
    const caps = await screen.findByTestId("capabilities");
    expect(within(caps).getByText("Possible, but needs a public server")).toBeInTheDocument();
    expect(within(caps).getByText("Your saved and liked posts")).toBeInTheDocument();
    expect(screen.queryByText(/Reset demo data/)).toBeNull();
    fireEvent.click(screen.getByRole("tab", { name: "General" }));
    await screen.findByText("Appearance");
    expect(screen.queryByText(/Reset demo data/)).toBeNull();
  });
});
