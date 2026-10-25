import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IdeasPage } from "@/components/pages/ideas";
import { ContentForm } from "@/components/content-form";
import type { ContentIdea } from "@/lib/api";
import { mockFetch } from "./helpers";

describe("Content ideas", () => {
  it("shows an empty state when there are no ideas", async () => {
    mockFetch([["/api/content", { items: [], total: 0, page: 1, page_size: 20 }]]);
    render(<IdeasPage />);
    expect(await screen.findByText("No ideas found")).toBeInTheDocument();
  });

  it("shows the API error on list failure", async () => {
    mockFetch([["/api/content", { error: "boom: content table missing" }, 500]]);
    render(<IdeasPage />);
    expect(await screen.findAllByText("boom: content table missing")).not.toHaveLength(0);
  });

  it("validates the create form: title required, caption ≤ 2200, duration range, evidence URLs", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ContentForm onSubmit={onSubmit} submitLabel="Create idea" />);
    await user.click(screen.getByRole("button", { name: "Create idea" }));
    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();

    await user.type(screen.getByLabelText("Title *"), "APIs explained");
    await user.type(screen.getByLabelText("Duration (s)"), "1");
    await user.type(screen.getByLabelText("Evidence URLs (one per line)"), "not a url");
    const caption = screen.getByLabelText("Caption");
    await user.click(caption);
    await user.paste("x".repeat(2201));
    expect(screen.getByTestId("caption-counter")).toHaveTextContent("2201/2200");
    await user.click(screen.getByRole("button", { name: "Create idea" }));
    expect(await screen.findByText("Caption must be 2200 characters or fewer")).toBeInTheDocument();
    expect(screen.getByText("Duration must be a whole number between 3 and 900")).toBeInTheDocument();
    expect(screen.getByText("Each evidence line must be an http(s) URL")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a valid create payload with lists split", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ContentForm onSubmit={onSubmit} submitLabel="Create idea" />);
    await user.type(screen.getByLabelText("Title *"), "APIs explained");
    await user.type(screen.getByLabelText("Hook options (one per line)"), "Hook A{enter}Hook B");
    await user.type(screen.getByLabelText("Hashtags (space separated)"), "#tech #apis");
    await user.type(screen.getByLabelText("Duration (s)"), "30");
    await user.click(screen.getByRole("button", { name: "Create idea" }));
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    const p = onSubmit.mock.calls[0][0];
    expect(p).toMatchObject({ title: "APIs explained", hook_options: ["Hook A", "Hook B"], hashtags: ["#tech", "#apis"], duration_seconds: 30, status: "idea", caption: null, storyboard: [] });
  });

  it("prefills the edit form and shows performance read-only", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    const idea = {
      id: 6, title: "Explain your project", pillar: "career", audience_segment: null, audience_problem: null, format: "talking_head",
      hook_options: ["h1"], recommended_hook: "h1", script: null, storyboard: [], on_screen_text: [], visual_direction: null, duration_seconds: 30,
      caption: "cap", keywords: [], hashtags: [], cta: null, effort: "medium", evidence: [], hypothesis: null, status: "selected",
      planned_at: null, lessons: null, package: {}, created_at: "", updated_at: "", published_media_id: null, performance: { views: 1234 }, is_demo: true,
    } as ContentIdea;
    render(<ContentForm initial={idea} onSubmit={onSubmit} />);
    expect(screen.getByLabelText("Title *")).toHaveValue("Explain your project");
    expect(screen.getByText(/"views": 1234/)).toBeInTheDocument();
    await user.clear(screen.getByLabelText("Title *"));
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Title is required")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Title *"), "New title");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await vi.waitFor(() => expect(onSubmit).toHaveBeenCalled());
    expect(onSubmit.mock.calls[0][0]).toMatchObject({ title: "New title", status: "selected", format: "talking_head" });
  });
});
