import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../../../lib/api";
import { forwardTraceHeaders } from "../../../trace";
import { fetchWithTimeout } from "../../../utils/fetchWithTimeout";
import { createProxyErrorResponse } from "../../../utils/proxyError";

type RouteContext = {
  params: Promise<{ id: string }>;
};

function buildAuthHeaders(): Headers {
  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
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

export async function POST(
  request: NextRequest,
  context: RouteContext
): Promise<NextResponse> {
  const { id } = await context.params;
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL(
    `/collections/${encodeURIComponent(id)}/items`,
    `${baseUrl}/api`
  );
  const headers = buildAuthHeaders();
  forwardTraceHeaders(request.headers, headers);

  try {
    const body = await request.text();
    const response = await fetchWithTimeout(target, {
      method: "POST",
      headers,
      body,
      cache: "no-store",
    });
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
      logContext: `Failed to add item to collection ${id}`,
      message: "Unable to add item to collection. Please try again later.",
    });
  }
}
