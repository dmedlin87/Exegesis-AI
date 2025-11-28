import { getApiBaseUrl } from "../../../app/lib/api";
import { fetchResearchFeatures } from "../../../app/research/features";
import type { ResearchFeaturesResult } from "../../../app/research/features";

vi.mock("../../../app/lib/api", () => ({
  getApiBaseUrl: vi.fn(() => "https://api.example.com"),
}));

describe("fetchResearchFeatures", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (getApiBaseUrl as vi.Mock).mockReturnValue("https://api.example.com");
  });

  it("returns feature flags when the request succeeds", async () => {
    const mockResponse = {
      ok: true,
      json: async () => ({ features: { research: true } }),
    } as unknown as Response;
    global.fetch = vi.fn().mockResolvedValue(mockResponse) as unknown as typeof fetch;

    const result = await fetchResearchFeatures();

    expect(global.fetch).toHaveBeenCalledWith(
      "https://api.example.com/features/discovery",
      { cache: "no-store" },
    );
    expect(result).toEqual<ResearchFeaturesResult>({
      features: { research: true },
      error: null,
    });
  });

  it("returns an error when the response is not ok", async () => {
    const mockResponse = {
      ok: false,
      status: 503,
      statusText: "Service Unavailable",
      text: async () => "maintenance",
    } as unknown as Response;
    global.fetch = vi.fn().mockResolvedValue(mockResponse) as unknown as typeof fetch;

    const result = await fetchResearchFeatures();

    expect(result.features).toBeNull();
    expect(result.error).toContain("Unable to load research features");
    expect(result.error).toContain("503");
    expect(result.error).toContain("maintenance");
  });

  it("returns an error when the fetch throws", async () => {
    global.fetch = vi.fn().mockRejectedValue(new Error("network down")) as unknown as typeof fetch;

    const result = await fetchResearchFeatures();

    expect(result.features).toBeNull();
    expect(result.error).toContain("network down");
  });
});
