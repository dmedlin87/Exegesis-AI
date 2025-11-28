/** @vitest-environment jsdom */

import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import ErrorCallout from "../../../app/components/ErrorCallout";
import { emitTelemetry } from "../../../app/lib/telemetry";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href }: { children: ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock("../../../app/lib/telemetry", () => ({
  __esModule: true,
  emitTelemetry: vi.fn().mockResolvedValue(undefined),
}));

describe("ErrorCallout", () => {
  const emitTelemetryMock = emitTelemetry as vi.MockedFunction<typeof emitTelemetry>;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders retry, details, and help actions with telemetry", () => {
    const handleRetry = vi.fn();
    const handleDetails = vi.fn();

    render(
      <ErrorCallout
        message="Authentication failed"
        traceId="trace-123"
        onRetry={handleRetry}
        retryLabel="Retry search"
        onShowDetails={handleDetails}
        detailsLabel="Show details"
        helpLink="/admin/settings"
        helpLabel="Open Settings"
        telemetry={{ source: "search_page", page: "search", errorCategory: "auth" }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Retry search" }));
    expect(handleRetry).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Show details" }));
    expect(handleDetails).toHaveBeenCalledWith("trace-123");

    const helpLink = screen.getByRole("link", { name: "Open Settings" });
    expect(helpLink).toHaveAttribute("href", "/admin/settings");
    fireEvent.click(helpLink);

    expect(emitTelemetryMock).toHaveBeenCalledTimes(3);
    const actions = emitTelemetryMock.mock.calls.map((call) => {
      const event = call[0][0];
      const metadata = event.metadata as Record<string, unknown> | undefined;
      return metadata?.action;
    });
    expect(actions).toEqual(["retry", "details", "help"]);
  });

  it("omits optional controls when callbacks are not provided", () => {
    render(<ErrorCallout message="Upload failed" />);

    expect(screen.getByText("Upload failed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Retry/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Details/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
