/** @vitest-environment jsdom */

import { render, screen } from "@testing-library/react";

import GraphQLExplorer from "../../../app/admin/graphql/GraphQLExplorer";

const graphiqlPropsSpy = vi.fn();

vi.mock("graphiql", () => ({
  GraphiQL: (props: unknown) => {
    graphiqlPropsSpy(props);
    return <div data-testid="graphiql" />;
  },
}));

vi.mock("../../../app/lib/api-config", () => ({
  useApiHeaders: vi.fn(),
  useGraphQLExplorerEnabled: vi.fn(),
}));

const useApiHeadersMock =
  require("../../../app/lib/api-config").useApiHeaders as vi.MockedFunction<() => Record<string, string>>;
const useGraphQLExplorerEnabledMock =
  require("../../../app/lib/api-config").useGraphQLExplorerEnabled as vi.MockedFunction<() => boolean>;

describe("GraphQLExplorer", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    graphiqlPropsSpy.mockClear();
    useApiHeadersMock.mockReset();
    useGraphQLExplorerEnabledMock.mockReset();
    global.fetch = vi.fn();
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("renders a message when the explorer is disabled", () => {
    useGraphQLExplorerEnabledMock.mockReturnValue(false);
    useApiHeadersMock.mockReturnValue({});

    render(<GraphQLExplorer />);

    expect(screen.getByText(/explorer is disabled/i)).toBeInTheDocument();
    expect(screen.queryByTestId("graphiql")).not.toBeInTheDocument();
  });

  it("passes the stored headers to the GraphiQL fetcher", async () => {
    useGraphQLExplorerEnabledMock.mockReturnValue(true);
    useApiHeadersMock.mockReturnValue({ Authorization: "Bearer example" });
    process.env.NEXT_PUBLIC_API_BASE_URL = "https://api.test";

    const jsonResponse = { data: { hello: "world" } };
    (global.fetch as vi.Mock).mockResolvedValue({
      headers: new Headers({ "content-type": "application/json" }),
      json: async () => jsonResponse,
      text: async () => JSON.stringify(jsonResponse),
    });

    render(<GraphQLExplorer />);

    expect(screen.getByTestId("graphiql")).toBeInTheDocument();
    expect(graphiqlPropsSpy).toHaveBeenCalled();

    const props = graphiqlPropsSpy.mock.calls[0][0] as { fetcher: (params: unknown) => Promise<unknown> };
    await props.fetcher({ query: "{ hello }" });

    expect(global.fetch).toHaveBeenCalledWith("https://api.test/graphql", {
      method: "POST",
      credentials: "include",
      headers: expect.objectContaining({
        Accept: "application/json",
        "Content-Type": "application/json",
        Authorization: "Bearer example",
      }),
      body: JSON.stringify({ query: "{ hello }" }),
    });
  });
});
