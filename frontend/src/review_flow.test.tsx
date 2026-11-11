import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { App } from "./app.tsx";
import { REVIEWER_NAME } from "./api/endpoints.ts";
import documentStyles from "./features/redline/document_view.module.css";

const DOCUMENT_ID = "document-1";
const ETAG = '"document-1-1"';
const DOCUMENT_TEXT = "The Customer shall indemnify the Company.\n\nThe parties sign below.";
const SHALL_START = 13;
const SHALL_END = 18;
const INDEMNIFY_START = 19;
const INDEMNIFY_END = 28;

interface ReviewSuggestionResponse {
  suggestion_id: string;
  start: number;
  end: number;
  original_text: string;
  replacement: string;
  rationale: string;
  title: string;
}

const SHALL_SUGGESTION: ReviewSuggestionResponse = {
  suggestion_id: "s1",
  start: SHALL_START,
  end: SHALL_END,
  original_text: "shall",
  replacement: "will",
  rationale: "Prefer will.",
  title: "Prefer will",
};
const INDEMNIFY_SUGGESTION: ReviewSuggestionResponse = {
  suggestion_id: "s2",
  start: INDEMNIFY_START,
  end: INDEMNIFY_END,
  original_text: "indemnify",
  replacement: "compensate",
  rationale: "Soften the duty.",
  title: "Soften the duty",
};
const PLAYBOOK_SUGGESTIONS = [SHALL_SUGGESTION, INDEMNIFY_SUGGESTION];
const ONE_WORD_SUGGESTIONS = [SHALL_SUGGESTION];

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
 * @param suggestions - The suggestions the review returns.
 * @returns The recorded requests.
 * @throws Does not throw.
 */
function installFetch(
  applyStatus: number,
  suggestions: ReviewSuggestionResponse[],
  documentText: string = DOCUMENT_TEXT,
): CapturedRequest[] {
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
      if (url.includes("/search")) {
        return Response.json({ hits: [], total_count: 0, limit: 20, offset: 0 });
      }
      if (url.includes("/ai-redlines")) {
        return Response.json(
          {
            document_id: DOCUMENT_ID,
            version: 1,
            suggestions,
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
            text: documentText,
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
          text: documentText,
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
            character_count: documentText.length,
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
    const requests = installFetch(200, PLAYBOOK_SUGGESTIONS);
    const user = userEvent.setup();
    renderApp();
    await openPlaybookReview();
    const paragraphs = document.querySelector("article")?.querySelectorAll("p");
    expect(paragraphs?.[0]?.classList.contains(documentStyles.activeChange)).toBe(true);
    expect(paragraphs?.[1]?.classList.contains(documentStyles.activeChange)).toBe(false);
    expect(
      document
        .querySelector("[data-suggestion-id='s1']")
        ?.classList.contains(documentStyles.active),
    ).toBe(true);
    expect(
      document
        .querySelector("[data-suggestion-id='s2']")
        ?.classList.contains(documentStyles.active),
    ).toBe(false);

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

  it("a pending suggestion that changes one word shows exactly one del and one ins", async () => {
    installFetch(200, ONE_WORD_SUGGESTIONS);
    const user = userEvent.setup();
    renderApp();
    await user.click(await screen.findByRole("button", { name: /Services agreement/ }));
    await user.click(await screen.findByRole("button", { name: "Review against our playbook" }));
    await screen.findByRole("heading", { name: "Prefer will" });

    expect(document.querySelectorAll("del")).toHaveLength(1);
    expect(document.querySelectorAll("ins")).toHaveLength(1);
    expect(document.querySelector("del")?.textContent).toBe("shall");
    expect(document.querySelector("ins")?.textContent).toBe("will");
    expect(document.querySelector("[data-suggestion-id='s1']")?.textContent).toBe("shall will");
  });

  it("asks for an open contract before showing the composer", async () => {
    installFetch(200, PLAYBOOK_SUGGESTIONS);
    const user = userEvent.setup();
    renderApp();

    expect(
      await screen.findByText("Open a contract to ask Claude for redlines."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Suggest redlines/ })).not.toBeInTheDocument();

    await user.click(await screen.findByRole("button", { name: /Services agreement/ }));

    expect(await screen.findByRole("button", { name: /Suggest redlines/ })).toBeInTheDocument();
    expect(
      screen.queryByText("Open a contract to ask Claude for redlines."),
    ).not.toBeInTheDocument();
  });

  it("shows in-document match controls only while the field has a query", async () => {
    installFetch(200, PLAYBOOK_SUGGESTIONS);
    const user = userEvent.setup();
    renderApp();
    await user.click(await screen.findByRole("button", { name: /Services agreement/ }));

    expect(screen.queryByRole("button", { name: "Previous" })).not.toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Search in this contract"), "shall");

    expect(await screen.findByRole("button", { name: "Previous" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeInTheDocument();
    expect(screen.getByText("1 of 1")).toBeInTheDocument();
  });

  it("in-contract find steps through every match", async () => {
    installFetch(200, [], "shall shall shall shall shall");
    const user = userEvent.setup();
    renderApp();
    await user.click(await screen.findByRole("button", { name: /Services agreement/ }));
    await user.type(screen.getByPlaceholderText("Search in this contract"), "shall");

    expect(screen.getByText("1 of 5")).toBeInTheDocument();
    for (let step = 0; step < 4; step += 1) {
      await user.click(screen.getByRole("button", { name: "Next" }));
    }
    expect(screen.getByText("5 of 5")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("1 of 5")).toBeInTheDocument();
  });

  it("filters contract names from the first character without searching text", async () => {
    const requests = installFetch(200, []);
    const user = userEvent.setup();
    renderApp();
    await screen.findByRole("button", { name: /Services agreement/ });

    await user.type(screen.getByPlaceholderText("Search contracts"), "S");
    await new Promise((resolve) => {
      setTimeout(resolve, 250);
    });

    expect(screen.getByRole("heading", { name: "Contracts" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Services agreement/ })).toBeInTheDocument();
    expect(requests.some((request) => request.url.includes("/search"))).toBe(false);
  });

  it("stale review shows the changed-since banner", async () => {
    installFetch(412, PLAYBOOK_SUGGESTIONS);
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
