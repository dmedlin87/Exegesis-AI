/** @vitest-environment jsdom */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import ChatWorkspace from "../../../app/chat/ChatWorkspace";
import type { ChatWorkflowClient } from "../../../app/lib/chat-client";
import { TheoApiError } from "../../../app/lib/api-client";

vi.mock("../../../app/lib/telemetry", () => ({
  submitFeedback: vi.fn(),
  emitTelemetry: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
  }),
}));

describe("ChatWorkspace error translations", () => {
  const INPUT_LABEL = "Ask Theoria";

  function renderChat(client: ChatWorkflowClient) {
    return render(<ChatWorkspace client={client} />);
  }

  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("prompts the user to add an API key for authentication failures", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(async () => {
        throw new TheoApiError("Unauthorized", 401, "https://api.test/chat");
      }),
      fetchChatSession: vi.fn(async () => null),
    };

    renderChat(client);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "Explain John 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(
        screen.getByText(
          /Theo couldn’t authenticate with the API\. Add a valid API key in Settings/i,
        ),
      ).toBeInTheDocument();
    });

    const helpLink = screen.getByRole("link", { name: "Open Settings" });
    expect(helpLink).toHaveAttribute("href", "/admin/settings");
  });

  it("surfaces retry guidance for server failures", async () => {
    const client: ChatWorkflowClient = {
      runChatWorkflow: vi.fn(async () => {
        throw new TheoApiError("Service unavailable", 503, "https://api.test/chat");
      }),
      fetchChatSession: vi.fn(async () => null),
    };

    renderChat(client);

    fireEvent.change(screen.getByLabelText(INPUT_LABEL), { target: { value: "Explain John 1" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(
        screen.getByText(/Theo’s services are having trouble responding\. Please retry in a moment\./i),
      ).toBeInTheDocument();
    });

    expect(screen.getByRole("button", { name: "Retry question" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Check system status" })).toHaveAttribute(
      "href",
      "https://status.theo.ai/",
    );
  });
});
