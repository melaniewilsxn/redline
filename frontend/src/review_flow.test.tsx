import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./app.tsx";
import { REVIEWER_NAME } from "./api/endpoints.ts";

const DOCUMENT_ID = "document-1";
const ETAG = '"document-1-1"';
const DOCUMENT_TEXT = "The Customer shall indemnify the Company.";
const SHALL_START = 13;
const SHALL_END = 18;
const INDEMNIFY_START = 19;
const INDEMNIFY_END = 28;

interface CapturedRequest {
  url: string;
  method: string;
  body: string | null;
  ifMatch: string | null;
}

/**
 * Render the app with retries turned off.
 * @returns The render result.
 * @throws Does not throw.
 */
function renderApp() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>,
  );
}

/**
 * Stub fetch for the review flow and record every request.
 * @param applyStatus - The status the apply request returns.
 * @returns The recorded requests.
 * @throws Does not throw.
 */
function installFetch(applyStatus: number): CapturedRequest[] {
  const requests: CapturedRequest[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      const headers = new Headers(init?.headers);
      requests.push({
        url,
        method,
        body: typeof init?.body === "string" ? init.body : null,
        ifMatch: headers.get("If-Match"),
      });
      if (url.includes("/ai-redlines")) {
        return Response.json(
          {
            document_id: DOCUMENT_ID,
            version: 1,
            suggestions: [
              {
                suggestion_id: "s1",
                start: SHALL_START,
                end: SHALL_END,
                original_text: "shall",
                replacement: "will",
                rationale: "Prefer will.",
              },
              {
                suggestion_id: "s2",
                start: INDEMNIFY_START,
                end: INDEMNIFY_END,
                original_text: "indemnify",
                replacement: "compensate",
                rationale: "Soften the duty.",
              },
            ],
            dropped: [],
          },
          { headers: { ETag: ETAG } },
        );
      }
      if (method === "PATCH") {
        if (applyStatus === 412) {
          return Response.json(
            { error: "The contract changed.", code: 412, error_type: "precondition_failed" },
            { status: 412 },
          );
        }
        return Response.json({
          document: {
            id: DOCUMENT_ID,
            title: "Services agreement",
            version: 2,
            text: DOCUMENT_TEXT,
            created_at: "2026-11-10T00:00:00Z",
            updated_at: "2026-11-10T00:00:00Z",
          },
          applied_edits: [],
        });
      }
      if (url.includes(`/documents/${DOCUMENT_ID}`)) {
        return Response.json({
          id: DOCUMENT_ID,
          title: "Services agreement",
          version: 1,
          text: DOCUMENT_TEXT,
          created_at: "2026-11-10T00:00:00Z",
          updated_at: "2026-11-10T00:00:00Z",
        });
      }
      return Response.json({
        documents: [
          {
            id: DOCUMENT_ID,
            title: "Services agreement",
            version: 1,
            character_count: DOCUMENT_TEXT.length,
            updated_at: "2026-11-10T00:00:00Z",
          },
        ],
        total_count: 1,
        limit: 100,
        offset: 0,
      });
    }),
  );
  return requests;
}

/**
 * Open the sample contract and load the playbook review.
 * @throws Does not throw.
 */
async function openPlaybookReview(): Promise<void> {
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: /Services agreement/ }));
  await user.click(await screen.findByRole("button", { name: "Review against our playbook" }));
  await screen.findByRole("heading", { name: "Prefer will" });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("review flow", () => {
  it("reviewer accepts one suggestion, rejects one, and applies", async () => {
    const requests = installFetch(200);
    const user = userEvent.setup();
    renderApp();
    await openPlaybookReview();

    await user.keyboard("a");
    await user.keyboard("r");
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(await screen.findByText("Applied 1 change. Now version 2.")).toBeInTheDocument();
    const patch = requests.find((request) => request.method === "PATCH");
    if (patch === undefined || patch.body === null) {
      throw new Error("The review was not applied");
    }
    expect(patch.ifMatch).toBe(ETAG);
    expect(JSON.parse(patch.body)).toEqual({
      author: REVIEWER_NAME,
      changes: [
        {
          target: { type: "range", start: SHALL_START, end: SHALL_END },
          replacement: "will",
        },
      ],
    });
  });

  it("stale review shows the changed-since banner", async () => {
    installFetch(412);
    const user = userEvent.setup();
    renderApp();
    await openPlaybookReview();

    await user.keyboard("a");
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(
      await screen.findByText(
        "This contract changed since the review. Run the review again to get fresh suggestions.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run again" })).toBeInTheDocument();
  });
});
