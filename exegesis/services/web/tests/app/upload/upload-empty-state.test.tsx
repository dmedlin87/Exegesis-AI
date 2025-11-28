/** @vitest-environment jsdom */

import { render, waitFor } from "@testing-library/react";

import { ToastProvider } from "../../../app/components/Toast";
import UploadPage from "../../../app/upload/page";

vi.mock("../../../app/upload/components/SimpleIngestForm", () => ({
  __esModule: true,
  default: () => <div data-testid="simple-ingest-form" />,
}));

vi.mock("../../../app/upload/components/FileUploadForm", () => ({
  __esModule: true,
  default: () => <div data-testid="file-upload-form" />,
}));

vi.mock("../../../app/upload/components/UrlIngestForm", () => ({
  __esModule: true,
  default: () => <div data-testid="url-ingest-form" />,
}));

vi.mock("../../../app/upload/components/JobsTable", () => ({
  __esModule: true,
  default: () => <div data-testid="jobs-table" />,
}));

vi.mock("../../../app/lib/api", () => ({
  getApiBaseUrl: () => "https://api.example.com",
}));

describe("UploadPage empty state hero", () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
    vi.useRealTimers();
  });

  it("highlights supported formats before any jobs exist", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ jobs: [] }),
    } as Response);
    global.fetch = fetchMock as unknown as typeof fetch;

    const { asFragment } = render(
      <ToastProvider>
        <UploadPage />
      </ToastProvider>,
    );

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalled();
    });

    expect(asFragment()).toMatchSnapshot();
    vi.runOnlyPendingTimers();
  });
});
