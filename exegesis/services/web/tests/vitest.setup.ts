import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterAll, afterEach, beforeAll } from "vitest";

import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "warn" }));
afterEach(() => {
  server.resetHandlers();
  cleanup();
});
afterAll(() => server.close());

class MockResizeObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}

type GlobalWithMockResizeObserver = typeof globalThis & {
  ResizeObserver?: typeof MockResizeObserver;
};

if (!globalThis.ResizeObserver) {
  (globalThis as GlobalWithMockResizeObserver).ResizeObserver = MockResizeObserver;
}
