import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OverviewPage } from "@/components/pages/overview";
import { Shell } from "@/components/shell";
import { TooltipProvider } from "@/components/ui/tooltip";
import { dashboard, mockFetch, settings } from "./helpers";

vi.mock("next/navigation", () => ({ usePathname: () => "/", useSearchParams: () => new URLSearchParams() }));

const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("Overview dashboard", () => {
  it("shows a loading state, then metrics with source badges; null renders as unavailable", async () => {
    mockFetch([
      ["/api/dashboard", dashboard],
      ["/api/growth/daily-plan", []],
    ]);
    wrap(<OverviewPage />);
    expect(screen.getByText("Loading dashboard…")).toBeInTheDocument();
    const followers = await screen.findByTestId("metric-Followers");
    expect(within(followers).getByText("602")).toBeInTheDocument();
    expect(within(followers).getByText("DEMO")).toBeInTheDocument();
    expect(within(screen.getByTestId("metric-Views")).getByText("unavailable")).toBeInTheDocument();
    expect(within(screen.getByTestId("metric-Views")).queryByText("0")).toBeNull();
    expect(within(screen.getByTestId("metric-Engagement rate (reach)")).getByText("calculated")).toBeInTheDocument();
    // target not configured => onboarding prompt
    expect(screen.getByText("Set your growth target")).toBeInTheDocument();
  });

  it("renders the demo banner without any reset button when data mode is demo", async () => {
    mockFetch([["/api/settings", settings]]);
    wrap(<Shell><div>child</div></Shell>);
    const banner = await screen.findByTestId("demo-banner");
    expect(banner).toHaveTextContent("You're looking at sample data.");
    expect(within(banner).queryByRole("button")).toBeNull();
  });

  it("does not render the demo banner in real mode", async () => {
    const f = mockFetch([["/api/settings", { ...settings, data_mode: "real" }]]);
    wrap(<Shell><div>child</div></Shell>);
    await vi.waitFor(() => expect(f).toHaveBeenCalled());
    expect(screen.queryByTestId("demo-banner")).toBeNull();
  });

  it("shows the API error message when the dashboard fails", async () => {
    mockFetch([
      ["/api/dashboard", { error: "database is locked" }, 500],
      ["/api/growth/daily-plan", []],
    ]);
    wrap(<OverviewPage />);
    expect(await screen.findByText("database is locked")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Retry" }).length).toBeGreaterThan(0);
  });
});
