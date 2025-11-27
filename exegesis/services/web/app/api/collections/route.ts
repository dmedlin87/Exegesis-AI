import { NextRequest, NextResponse } from "next/server";

import { getApiBaseUrl } from "../../lib/api";
import { forwardTraceHeaders } from "../trace";
import { fetchWithTimeout } from "../utils/fetchWithTimeout";
import { createProxyErrorResponse } from "../utils/proxyError";

function buildAuthHeaders(): Headers {
  const headers = new Headers({
    Accept: "application/json",
    "Content-Type": "application/json",
  });
  const apiKey = process.env.EXEGESIS_SEARCH_API_KEY?.trim();
  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      headers.set("Authorization", apiKey);
    } else {
      headers.set("X-API-Key", apiKey);
    }
  }
  return headers;
}

function buildTargetUrl(request: NextRequest): URL {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/collections/", `${baseUrl}/api`);
  request.nextUrl.searchParams.forEach((value, key) => {
    if (value != null && value !== "") {
      target.searchParams.set(key, value);
    }
  });
  return target;
}

export async function GET(request: NextRequest): Promise<NextResponse> {
  const target = buildTargetUrl(request);
  const headers = buildAuthHeaders();
  forwardTraceHeaders(request.headers, headers);

  try {
    const response = await fetchWithTimeout(target, {
      headers,
      cache: "no-store",
    });
    const body = await response.text();
    const proxyHeaders = new Headers();
    proxyHeaders.set(
      "content-type",
      response.headers.get("content-type") ?? "application/json"
    );
    forwardTraceHeaders(response.headers, proxyHeaders);
    return new NextResponse(body, {
      status: response.status,
      headers: proxyHeaders,
    });
  } catch (error) {
    return createProxyErrorResponse({
      error,
      logContext: "Failed to fetch collections",
      message: "Collections are currently unavailable. Please try again later.",
    });
  }
}

export async function POST(request: NextRequest): Promise<NextResponse> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const target = new URL("/collections/", `${baseUrl}/api`);
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
      logContext: "Failed to create collection",
      message: "Unable to create collection. Please try again later.",
    });
  }
}
