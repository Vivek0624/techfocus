import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
// Recharts / Radix need these in jsdom.
globalThis.ResizeObserver = globalThis.ResizeObserver ?? (RO as unknown as typeof ResizeObserver);
if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {};
