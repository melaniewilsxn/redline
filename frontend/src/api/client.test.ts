import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, requestJson } from "./client.ts";
import { ApiErrorType } from "./types.ts";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("requestJson", () => {
  it("returns the body and the ETag on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json({ id: "document-1" }, { headers: { ETag: '"document-1-1"' } }),
      ),
    );

    const response = await requestJson<{ id: string }>("/documents/document-1", {});

    expect(response.body).toEqual({ id: "document-1" });
    expect(response.etag).toBe('"document-1-1"');
  });

  it("throws ApiError with the backend error type on a JSON error body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        Response.json(
          { error: "Not configured", code: 503, error_type: "ai_not_configured" },
          { status: 503 },
        ),
      ),
    );

    const thrown = await requestJson("/documents/document-1/ai-redlines", {
      method: "POST",
    }).then(
      () => null,
      (error: unknown) => error,
    );

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown).toMatchObject({
      status: 503,
      errorType: ApiErrorType.AiNotConfigured,
    });
  });

  it("throws ApiError with internal_error when the error body is not JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response("down", { status: 502, headers: { "Content-Type": "text/plain" } }),
      ),
    );

    const thrown = await requestJson("/documents", {}).then(
      () => null,
      (error: unknown) => error,
    );

    expect(thrown).toBeInstanceOf(ApiError);
    expect(thrown).toMatchObject({ errorType: ApiErrorType.InternalError });
  });
});
