import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ReelPlanner } from "@/components/creator/reel-planner";
import { mockFetch } from "./helpers";

const meta = (over: Record<string, unknown> = {}) => ({
  niche: "AI tools for developers",
  platforms: [
    { value: "instagram_reels", label: "Instagram Reels" },
    { value: "youtube_shorts", label: "YouTube Shorts" },
    { value: "tiktok", label: "TikTok" },
  ],
  default_platform: "instagram_reels",
  sections: ["hooks", "script", "shots", "caption", "cta"],
  live_research_available: false,
  research_provider: "model_knowledge",
  video_autoedit_available: false,
  note: "",
  ...over,
});

const topic = {
  title: "The AI advice nobody follows",
  why_trending: "Contrarian takes keep resurfacing.",
  angle: "Name the advice, show what works instead.",
  engagement_potential: "high",
  potential_reason: "Disagreement drives comments.",
  sources: [{ title: "A real page", url: "https://example.test/a" }],
};

const trends = (over: Record<string, unknown> = {}) => ({
  niche: "AI tools for developers",
  platform: "instagram_reels",
  topics: [topic],
  live_research_performed: false,
  disclosure: "Model knowledge only, not live. Check each one before you film.",
  source: "template",
  provider: "model_knowledge",
  search_results_found: 0,
  ...over,
});

const pkg = {
  topic: topic.title,
  platform: "instagram_reels",
  audience: "Developers who tried the obvious advice",
  one_idea: "One change beats ten tips.",
  hooks: [
    { text: "Most people get this wrong in five seconds.", hook_type: "contrarian", why_it_works: "Opens on a belief." },
    { text: "Nobody told me until it cost a month.", hook_type: "story", why_it_works: "A cost earns the next line." },
    { text: "Why is this harder than it should be?", hook_type: "curiosity", why_it_works: "Names a feeling." },
  ],
  script: [
    { section: "hook", t_start: 0, t_end: 3, spoken: "Most people get this wrong.", on_screen_text: "Backwards" },
    { section: "setup", t_start: 3, t_end: 8, spoken: "Here is what everyone repeats.", on_screen_text: "The usual advice" },
    { section: "value", t_start: 8, t_end: 20, spoken: "Do this one thing instead.", on_screen_text: "Do this" },
    { section: "payoff", t_start: 20, t_end: 26, spoken: "One change, not ten.", on_screen_text: "One change" },
    { section: "cta", t_start: 26, t_end: 30, spoken: "Save this.", on_screen_text: "Save it" },
  ],
  shots: [
    { order: 1, shot_type: "talking head", framing: "tight crop", location: "plain wall", action: "Deliver the hook", delivery_tone: "Fast, flat", b_roll: ["hard cut"], seconds: 3 },
    { order: 2, shot_type: "screen recording", framing: "full screen", location: "laptop", action: "Walk through it", delivery_tone: "Steady", b_roll: [], seconds: 17 },
    { order: 3, shot_type: "talking head", framing: "tight crop", location: "plain wall", action: "Land the CTA", delivery_tone: "Warmer", b_roll: [], seconds: 10 },
  ],
  total_duration_seconds: 30,
  caption: "The advice everyone repeats.\n\nSave this.",
  hashtags: ["#ai", "#devtools", "#reels", "#shortform", "#howto", "#creator"],
  pinned_comment: "Which advice did you give up on?",
  cta_primary: "Save this before your next session.",
  cta_alternative: "Comment the step you are stuck on.",
  audio_direction: "Low instrumental under the voice.",
  best_posting_time: "19:00-21:00 IST. A starting default to test.",
  ab_test_idea: "Contrarian hook vs curiosity hook, three reels each.",
};

const saved = { id: 7, niche: "AI tools for developers", platform: "instagram_reels", title: topic.title, topic, package: pkg, duration_seconds: 30, source: "template", live_research: false, idea_id: null, created_at: "2026-10-25T10:00:00+00:00", saved: true };

describe("Reel Planner", () => {
  it("prefills the niche, then runs niche → topics → full reel package", async () => {
    const user = userEvent.setup();
    const fetchMock = mockFetch([
      ["/api/reels/meta", meta()],
      ["POST http://localhost:8001/api/reels/trends", trends()],
      ["POST http://localhost:8001/api/reels/plan", saved],
      ["/api/reels/plans", { items: [] }],
    ]);

    render(<ReelPlanner />);
    const niche = await screen.findByLabelText("Niche");
    expect(niche).toHaveValue("AI tools for developers"); // prefilled from the profile

    await user.click(screen.getByRole("button", { name: /Find trending topics/ }));
    expect(await screen.findByText(topic.title)).toBeInTheDocument();
    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText(/Model knowledge only, not live/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /A real page/ })).toHaveAttribute("href", "https://example.test/a");

    // Generating is blocked until a topic is chosen.
    const generate = screen.getByRole("button", { name: /Generate reel plan/ });
    expect(generate).toBeDisabled();
    await user.click(screen.getByRole("button", { name: new RegExp(topic.title) }));
    expect(generate).toBeEnabled();
    await user.click(generate);

    // Every part of the package is on screen.
    expect(await screen.findByText("Hooks — first 1-3 seconds")).toBeInTheDocument();
    expect(screen.getByText("Most people get this wrong in five seconds.")).toBeInTheDocument();
    expect(screen.getByText("contrarian")).toBeInTheDocument();
    expect(screen.getByText("Do this one thing instead.")).toBeInTheDocument();
    expect(screen.getByText(/Shot 2 · screen recording/)).toBeInTheDocument();
    expect(screen.getByText("#devtools")).toBeInTheDocument();
    expect(screen.getByText(/Which advice did you give up on/)).toBeInTheDocument();
    expect(screen.getByText(/Save this before your next session/)).toBeInTheDocument();
    expect(screen.getByText(/19:00-21:00 IST/)).toBeInTheDocument();
    expect(screen.getByText(/Contrarian hook vs curiosity hook/)).toBeInTheDocument();

    const posted = fetchMock.mock.calls.find((c) => String(c[0]).endsWith("/api/reels/plan"));
    expect(JSON.parse(String((posted?.[1] as RequestInit).body))).toMatchObject({ niche: "AI tools for developers", platform: "instagram_reels", topic: { title: topic.title } });

    // Every section has its own copy button, and the whole plan has one.
    expect(screen.getByRole("button", { name: "Copy whole plan" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Copy" }).length).toBeGreaterThanOrEqual(5);
  });

  it("reopens a saved plan, regenerates one section and deletes it", async () => {
    const user = userEvent.setup();
    const newHooks = { ...saved, section: "hooks", package: { ...pkg, hooks: [{ ...pkg.hooks[0], text: "A sharper opener." }, pkg.hooks[1], pkg.hooks[2]] } };
    mockFetch([
      ["/api/reels/meta", meta()],
      ["GET http://localhost:8001/api/reels/plans/7", saved],
      ["POST http://localhost:8001/api/reels/plans/7/regenerate", newHooks],
      ["DELETE http://localhost:8001/api/reels/plans/7", undefined, 204],
      ["/api/reels/plans", { items: [{ id: 7, title: topic.title, niche: "AI tools for developers", platform: "instagram_reels", duration_seconds: 30, source: "template", live_research: false, hook: pkg.hooks[0].text, created_at: null }] }],
    ]);

    render(<ReelPlanner />);
    const list = await screen.findByText("My reel plans");
    await user.click(await screen.findByRole("button", { name: `Open ${topic.title}` }));

    expect(await screen.findByText("Shot list — how to film it")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Regenerate hooks" }));
    expect(await screen.findByText("A sharper opener.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: `Delete ${topic.title}` }));
    expect(list).toBeInTheDocument();
  });

  it("warns when no live search provider is configured, and keeps auto-edit disabled", async () => {
    mockFetch([
      ["/api/reels/meta", meta()],
      ["/api/reels/plans", { items: [] }],
    ]);
    render(<ReelPlanner />);
    expect(await screen.findByText(/No live search provider is configured/)).toBeInTheDocument();
    const autoEdit = screen.getByRole("button", { name: /Upload video for auto-edit/ });
    expect(autoEdit).toBeDisabled();
    expect(within(autoEdit.parentElement as HTMLElement).getByText("Coming soon")).toBeInTheDocument();
  });
});
