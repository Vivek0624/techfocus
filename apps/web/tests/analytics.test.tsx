import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalyticsPage } from "@/components/pages/analytics";
import { TooltipProvider } from "@/components/ui/tooltip";
import { calls, metrics, mockFetch } from "./helpers";

const analytics = {
  mode: "demo", range: { start: "2026-09-22", end: "2026-10-22" }, follower_history: [], insights: metrics, posts: [],
  by_pillar: [{ group: "career_communication", n: 2, median: 60561, enough_data: false }],
  by_hook: [{ group: "question", n: 3, median: 1574, enough_data: true }], by_format: [],
  best_time: { status: "ok", windows: [], recommendation: "Post 10-14 IST" }, definitions: { reach_per_post: "sum / count" },
};

describe("Analytics", () => {
  it("passes the selected date filter to /api/analytics", async () => {
    const f = mockFetch([["/api/analytics", analytics]]);
    const user = userEvent.setup();
    render(<TooltipProvider><AnalyticsPage /></TooltipProvider>);
    expect(await screen.findByText("Post 10-14 IST")).toBeInTheDocument();
    expect(calls(f)[0]).toContain("/api/analytics?days=30");

    await user.click(screen.getByRole("button", { name: "7 days" }));
    await vi.waitFor(() => expect(calls(f).some((c) => c.endsWith("/api/analytics?days=7"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Custom" }));
    await user.type(screen.getByLabelText("Start date"), "2026-10-01");
    await user.type(screen.getByLabelText("End date"), "2026-10-10");
    await user.click(screen.getByRole("button", { name: "Apply" }));
    await vi.waitFor(() => expect(calls(f).some((c) => c.endsWith("/api/analytics?start=2026-10-01&end=2026-10-10"))).toBe(true));
  });

  it("dims groups without enough data and labels them", async () => {
    mockFetch([["/api/analytics", analytics]]);
    render(<TooltipProvider><AnalyticsPage /></TooltipProvider>);
    const label = await screen.findByText("n too small");
    expect(label.closest("tr")).toHaveClass("opacity-50");
  });
});
