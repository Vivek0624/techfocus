import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useRunPoller } from "@/lib/hooks";
import { parseRunInput, RunDetails } from "@/components/pages/agents";
import { mockFetch, run } from "./helpers";

function Harness({ input = {} }: { input?: Record<string, unknown> }) {
  const p = useRunPoller();
  return (
    <div>
      <button onClick={() => p.start("reel_creative", input)}>start</button>
      <button onClick={p.cancel}>cancel</button>
      <span data-testid="status">{p.status ?? "idle"}</span>
      {p.run && <RunDetails run={p.run} status={p.status} />}
      {p.error && <span role="alert">{p.error}</span>}
    </div>
  );
}

describe("Agent run polling", () => {
  beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
  afterEach(() => vi.useRealTimers());

  it("polls until failed and shows the error", async () => {
    const states = [run({ status: "running" }), run({ status: "failed", error: "simulated failure for testing", duration_ms: 12 })];
    let i = 0;
    const f = mockFetch([
      ["POST http://localhost:8001/api/agents/reel_creative/run", (_u: string, init?: RequestInit) => {
        expect(JSON.parse(String(init?.body))).toEqual({ input: { simulate_failure: true } });
        return run({ status: "queued" });
      }, 202],
      ["GET http://localhost:8001/api/agent-runs/42", () => states[Math.min(i++, states.length - 1)]],
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Harness input={parseRunInput("", true).input} />);
    await user.click(screen.getByText("start"));
    expect(await screen.findByTestId("status")).toHaveTextContent("queued");
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.getByTestId("status")).toHaveTextContent("running");
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.getByTestId("status")).toHaveTextContent("failed");
    expect(screen.getByText("simulated failure for testing")).toBeInTheDocument();
    const polls = f.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(f.mock.calls.length).toBe(polls); // stopped polling
  });

  it("shows 'cancelling' (not 'cancelled') until the worker reports cancelled", async () => {
    let cancelled = false;
    let workerDone = false;
    mockFetch([
      ["POST http://localhost:8001/api/agents/reel_creative/run", run({ status: "running" }), 202],
      ["POST http://localhost:8001/api/agent-runs/42/cancel", () => { cancelled = true; return { run_id: 42, state: "cancelling" }; }],
      ["GET http://localhost:8001/api/agent-runs/42", () => run({ status: cancelled && workerDone ? "cancelled" : "running" })],
    ]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Harness />);
    await user.click(screen.getByText("start"));
    expect(await screen.findByTestId("status")).toHaveTextContent("running");
    await user.click(screen.getByText("cancel"));
    await vi.waitFor(() => expect(screen.getByTestId("status")).toHaveTextContent("cancelling"));
    await act(() => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByTestId("status")).toHaveTextContent("cancelling");
    workerDone = true;
    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.getByTestId("status")).toHaveTextContent("cancelled");
  });

  it("surfaces API errors when starting a run", async () => {
    mockFetch([["POST http://localhost:8001/api/agents/reel_creative/run", { error: "unknown agent" }, 404]]);
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    render(<Harness />);
    await user.click(screen.getByText("start"));
    expect(await screen.findByRole("alert")).toHaveTextContent("unknown agent");
  });

  it("validates run input JSON", () => {
    expect(parseRunInput("{bad", false).error).toBe("Input is not valid JSON");
    expect(parseRunInput("[1]", false).error).toBe("Input must be a JSON object");
    expect(parseRunInput('{"topic":"x"}', true).input).toEqual({ topic: "x", simulate_failure: true });
  });
});
