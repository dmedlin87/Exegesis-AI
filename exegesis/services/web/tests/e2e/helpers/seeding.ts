import type { APIRequestContext } from "@playwright/test";
import { expect } from "@playwright/test";
import crypto from "node:crypto";

const API_BASE = process.env.PLAYWRIGHT_API_BASE ?? "http://127.0.0.1:8000";

export async function seedCorpus(request: APIRequestContext): Promise<void> {
  const uniqueId = crypto.randomUUID().slice(0, 8);
  const content = `---
title: Playwright E2E Sermon ${uniqueId}
collection: e2e-tests
osis_ref: John.1.1
---

# The Divine Prologue

In the beginning was the Word, and the Word was with God, and the Word was God.

This sermon explores the profound theological implications of John's prologue,
examining how the Logos concept bridges Jewish wisdom tradition with Greek philosophy.

The divine Word (Logos) represents both creative power and redemptive purpose.
`;

  const response = await request.post(`${API_BASE}/ingest/file`, {
    multipart: {
      file: {
        name: "sermon.md",
        buffer: Buffer.from(content, "utf-8"),
        mimeType: "text/markdown",
      },
    },
  });
  expect(response.ok()).toBeTruthy();
}

export async function seedResearchNote(request: APIRequestContext): Promise<void> {
  const payload = {
    osis: "John.1.1",
    body: "Playwright integration commentary on John 1:1",
    title: "Playwright commentary",
    stance: "apologetic",
    claim_type: "textual",
    confidence: 0.7,
    tags: ["playwright", "integration"],
    evidences: [
      {
        source_type: "crossref",
        source_ref: "Genesis.1.1",
        snippet: "Creation language links the passages.",
        osis_refs: ["Genesis.1.1"],
      },
    ],
  };
  const response = await request.post(`${API_BASE}/research/notes`, {
    data: JSON.stringify(payload),
    headers: { "content-type": "application/json" },
  });
  expect(response.ok()).toBeTruthy();
}
