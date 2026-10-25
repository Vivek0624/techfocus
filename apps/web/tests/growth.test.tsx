import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { FatigueSection, GapsSection, ShareabilityCard, Shortlist } from "@/components/creator/growth";
import { calls, mockFetch } from "./helpers";

const wrap = (ui: React.ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("Growth features", () => {
  it("shortlist shows audience, shareability, flags and the metric to watch", () => {
    wrap(
      <Shortlist
        items={[
          {
            idea_id: 2,
            title: "Crores pay on UPI at 8pm",
            status: "recording",
            category: "tech_concepts",
            hook: null,
            audience: { audience: "beginners", label: "Beginners", inferred: true, reason: "mentions upi" },
            shareability: { score: 45, band: "medium", tip: null },
            why: ["Already at the recording stage, so it's the fastest to ship."],
            flags: [{ kind: "near_duplicate", message: "Very close to a post you already published." }],
            watch: { metric: "shares_per_1k", target: 5.5, text: "Shares per 1K reached above your median 5.5" },
          },
        ]}
      />,
    );
    expect(screen.getByText("For: Beginners")).toBeInTheDocument();
    expect(screen.getByText(/Very close to a post/)).toBeInTheDocument();
    expect(screen.getByText(/above your median 5.5/)).toBeInTheDocument();
  });

  it("shareability card shows sub-scores and the estimate label", async () => {
    mockFetch([
      [
        "POST http://localhost:8001/api/create/shareability",
        {
          score: 60,
          band: "medium",
          subscores: { relatability: { label: "Relatable", score: 80, reasons: ["talks to the viewer"] } },
          tip: null,
          calibration: { groups: [{ by: "topic", label: "career", n: 3, median_shares_per_1k: 11.9, confidence: "medium", text: "Your career posts averaged 11.9 shares per 1K reached (n=3)." }], account_median: 5.5 },
          note: "An estimate from the wording only. It is not a prediction of shares, views or followers.",
        },
      ],
    ]);
    wrap(<ShareabilityCard text="Most freshers freeze in interviews" category="career" />);
    fireEvent.click(screen.getByRole("button", { name: /Check shareability/ }));
    expect(await screen.findByTestId("shareability")).toHaveTextContent("Relatable");
    expect(screen.getByText(/averaged 11.9 shares/)).toBeInTheDocument();
    expect(screen.getByText(/not a prediction/)).toBeInTheDocument();
  });

  it("fatigue and gaps render from the API; add to ideas posts the comment ids", async () => {
    const f = mockFetch([
      ["GET http://localhost:8001/api/growth/fatigue", { window: 6, repetitive: [{ dimension: "topic", group: "ai", label: "AI", headline: "4 of your last 6 posts used the same topic: AI.", suggestion: "Mix it up." }], near_duplicates: [], declining: [], ok: false, note: "n" }],
      ["GET http://localhost:8001/api/growth/gaps", { gaps: [{ theme: "refund · upi", count: 2, likes: 40, covered: false, covered_by: null, suggested_title: "How do UPI refunds work", comments: [{ id: 5, username: "a", text: "How do refunds work?", like_count: 3 }] }], covered: [], questions_considered: 3, note: "Only your own comments." }],
      ["POST http://localhost:8001/api/growth/gaps/to-idea", { id: 9 }],
    ]);
    wrap(
      <>
        <FatigueSection />
        <GapsSection />
      </>,
    );
    expect(await screen.findByText(/same topic: AI/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Add to ideas" }));
    expect(await screen.findByText(/Added. Open Ideas/)).toBeInTheDocument();
    expect(calls(f)).toContain("POST http://localhost:8001/api/growth/gaps/to-idea");
  });
});
