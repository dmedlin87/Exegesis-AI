import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../../../lib/api";
import { forwardTraceHeaders } from "../../../../trace";
import { fetchWithTimeout } from "../../../../utils/fetchWithTimeout";
import { createProxyErrorResponse } from "../../../../utils/proxyError";

type RouteContext = {
  params: Promise<{ id: string; itemId: string }>;
};

function buildAuthHeaders(): Headers {
  const headers = new Headers({
    Accept: "application/json",
  });
  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      headers.set("Authorization", apiKey);
    } else {
      headers.set("X-API-Key", apiKey);
    }
  }
  return headers;
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  const { id, itemId } = await context.params;
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL(
    `/collections/${encodeURIComponent(id)}/items/${encodeURIComponent(itemId)}`,
    `${baseUrl}/api`
  );
  const headers = buildAuthHeaders();
  forwardTraceHeaders(request.headers, headers);

  try {
    const response = await fetchWithTimeout(target, {
      method: "DELETE",
      headers,
      cache: "no-store",
    });

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const responseBody = await response.text();
    const proxyHeaders = new Headers();
    proxyHeaders.set(
      "content-type",
      response.headers.get("content-type") ?? "application/json"
    );
    forwardTraceHeaders(response.headers, proxyHeaders);
    return new NextResponse(responseBody, {
      status: response.status,
      headers: proxyHeaders,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: `Failed to remove item ${itemId} from collection ${id}`,
      message: "Unable to remove item from collection. Please try again later.",
    });
  }
}
