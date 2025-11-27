"use server";

import { getApiBaseUrl } from "../lib/api";
import type { components } from "../lib/generated/api";
import { type SearchFilters, serializeSearchParams } from "./searchParams";

type SearchResponse = components["schemas"]["HybridSearchResponse"];

export type SearchActionResult =
  | {
      success: true;
      data: SearchResponse;
      rerankerName: string | null;
    }
  | {
      success: false;
      error: {
        message: string;
        status?: number;
        traceId?: string | null;
      };
    };

/**
 * Server Action for corpus search.
 *
 * This replaces the client-side fetch to `/api/search` with a direct
 * server-side call to the backend API. Benefits:
 * - Full type safety for request/response
 * - Reduced client bundle size (fetch logic not shipped to browser)
 * - Better error handling with structured error types
 * - Automatic request deduplication by Next.js
 *
 * @param filters - Search filters from the UI
 * @param signal - Optional AbortSignal for cancellation (note: limited support in Server Actions)
 * @returns Typed result with either search data or error details
 */
export async function searchCorpus(
  filters: SearchFilters,
): Promise<SearchActionResult> {
  const baseUrl = getApiBaseUrl().replace(/\/$/, "");
  const searchQuery = serializeSearchParams(filters);
  const target = new URL(`/search${searchQuery ? `?${searchQuery}` : ""}`, baseUrl);

  const apiKey = process.env.THEO_SEARCH_API_KEY?.trim();
  const headers = new Headers({ Accept: "application/json" });

  if (apiKey) {
    if (/^Bearer\s+/i.test(apiKey)) {
      headers.set("Authorization", apiKey);
    } else {
      headers.set("X-API-Key", apiKey);
    }
  }

  try {
    const response = await fetch(target.toString(), {
      headers,
      cache: "no-store",
    });

    const rerankerHeader = response.headers.get("x-reranker");
    const rerankerName = rerankerHeader?.trim() || null;

    if (!response.ok) {
      let errorMessage = `Search failed with status ${response.status}`;
      let traceId: string | null = null;

      try {
        const errorBody = await response.json();
        if (typeof errorBody === "object" && errorBody !== null) {
          if (typeof errorBody.detail === "string") {
            errorMessage = errorBody.detail;
          } else if (typeof errorBody.message === "string") {
            errorMessage = errorBody.message;
          }
          if (typeof errorBody.trace_id === "string") {
            traceId = errorBody.trace_id;
          }
        }
      } catch {
        // Ignore JSON parse errors, use default message
      }

      return {
        success: false,
        error: {
          message: errorMessage,
          status: response.status,
          traceId,
        },
      };
    }

    const data = (await response.json()) as SearchResponse;
    return {
      success: true,
      data,
      rerankerName,
    };
  } catch (error) {
    const message =
      error instanceof Error
        ? error.message
        : "Search service is currently unavailable. Please try again later.";

    return {
      success: false,
      error: { message },
    };
  }
}
