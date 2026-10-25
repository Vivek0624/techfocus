import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { CalendarForm, CalendarPage } from "@/components/pages/calendar";
import type { ContentIdea } from "@/lib/api";
import { calls, mockFetch } from "./helpers";

describe("Calendar", () => {
  it("creates an item from an idea and sends an IST wall-clock time", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    const ideas = [{ id: 3, title: "UPI at 8pm", format: "talking_head", caption: "cap" } as ContentIdea];
    render(<CalendarForm ideas={ideas} defaultDate="2026-10-30" onSubmit={onSubmit} submitLabel="Create item" />);
    await user.selectOptions(screen.getByLabelText("From idea (optional)"), "3");
    expect(screen.getByLabelText("Title *")).toHaveValue("UPI at 8pm");
    await user.click(screen.getByRole("button", { name: "Create item" }));
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toEqual({
      title: "UPI at 8pm", idea_id: 3, format: "talking_head", scheduled_at: "2026-10-30T19:00:00", caption: "cap", asset_ref: null, production_status: "planned",
    });
  });

  it("requires a title", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<CalendarForm ideas={[]} defaultDate="2026-10-30" onSubmit={onSubmit} submitLabel="Create item" />);
    await user.click(screen.getByRole("button", { name: "Create item" }));
    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("POSTs a new item from the page and reloads", async () => {
    const created: unknown[] = [];
    const f = mockFetch([
      ["POST http://localhost:8001/api/calendar", (_u: string, init?: RequestInit) => { created.push(JSON.parse(String(init?.body))); return { id: 9 }; }],
      ["GET http://localhost:8001/api/calendar", []],
      ["/api/content", { items: [], total: 0, page: 1, page_size: 100 }],
      ["/api/approvals", []],
    ]);
    const user = userEvent.setup();
    render(<CalendarPage />);
    await user.click(await screen.findByRole("button", { name: "New item" }));
    await user.type(await screen.findByLabelText("Title *"), "Record reel");
    await user.click(screen.getByRole("button", { name: "Create item" }));
    await vi.waitFor(() => expect(created).toHaveLength(1));
    expect(created[0]).toMatchObject({ title: "Record reel", production_status: "planned" });
    expect((created[0] as { scheduled_at: string }).scheduled_at).toMatch(/^\d{4}-\d{2}-\d{2}T19:00:00$/);
    await vi.waitFor(() => expect(calls(f).filter((c) => c.startsWith("GET http://localhost:8001/api/calendar?")).length).toBeGreaterThan(1));
  });
});
