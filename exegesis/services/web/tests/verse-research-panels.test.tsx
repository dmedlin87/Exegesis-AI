/** @vitest-environment jsdom */

import { render, screen } from "@testing-library/react";

import ResearchPanels from "../app/research/ResearchPanels";
import type { ResearchFeatureFlags } from "../app/research/types";

vi.mock("../app/mode-context", () => {
  const { RESEARCH_MODES, DEFAULT_MODE_ID } = vi.importActual<
    typeof import("../app/mode-config")
  >("../app/mode-config");
  return {
    useMode: () => ({
      mode: RESEARCH_MODES[DEFAULT_MODE_ID],
      modes: Object.values(RESEARCH_MODES),
      setMode: vi.fn(),
    }),
  };
});

beforeEach(() => {
  global.fetch = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({}),
    text: async () => "",
  }) as unknown as typeof fetch;
});

afterEach(() => {
  vi.resetAllMocks();
});

describe("ResearchPanels", () => {
  const baseFlags: ResearchFeatureFlags = { research: true };

  it("renders the research header and chat hint", () => {
    render(
      <ResearchPanels
        osis="John.1.1"
        features={{
          ...baseFlags,
          cross_references: true,
          contradictions: true,
          textual_variants: true,
        }}
      />,
    );

    expect(screen.getByText(/Research/)).toBeInTheDocument();
    expect(screen.getByText(/Prefer chatting\?/)).toBeInTheDocument();
    expect(screen.getAllByText(/John\.1\.1/).length).toBeGreaterThan(0);
  });

  it("does not render when research access is disabled", () => {
    const { container } = render(<ResearchPanels osis="John.1.1" features={{ research: false }} />);
    expect(container.firstChild).toBeNull();
  });
});
