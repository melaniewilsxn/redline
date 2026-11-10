import { ApiErrorType } from "./types.ts";

const API_PREFIX = "/api";
const JSON_CONTENT_TYPE = "application/json";
const GENERIC_ERROR_MESSAGE = "Something went wrong. Try again.";

export interface ApiResponse<Body> {
  body: Body;
  etag: string | null;
}

interface ErrorBody {
  error: string;
  code: number;
  error_type: string;
}

/**
 * An error response from the API.
 * @throws Does not throw.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly errorType: string;
  readonly errorMessage: string;

  /**
   * Store the status, error type, and message.
   * @param status - The HTTP status.
   * @param errorType - The stable error code.
   * @param errorMessage - The message safe to show.
   */
  constructor(status: number, errorType: string, errorMessage: string) {
    super(errorMessage);
    this.name = "ApiError";
    this.status = status;
    this.errorType = errorType;
    this.errorMessage = errorMessage;
  }
}

/**
 * Send a JSON request to the API and return the body with its ETag.
 * @param path - The path after the API prefix, beginning with a slash.
 * @param options - The fetch options. The JSON content type is added.
 * @returns The parsed body and the ETag header, quotes included.
 * @throws {ApiError} When the response is not a success.
 */
export async function requestJson<Body>(
  path: string,
  options: RequestInit,
): Promise<ApiResponse<Body>> {
  const headers = new Headers(options.headers);
  headers.set("Accept", JSON_CONTENT_TYPE);
  if (options.body !== undefined) {
    headers.set("Content-Type", JSON_CONTENT_TYPE);
  }
  let response: Response;
  try {
    response = await fetch(`${API_PREFIX}${path}`, { ...options, headers });
  } catch {
    throw new ApiError(0, ApiErrorType.InternalError, GENERIC_ERROR_MESSAGE);
  }
  if (!response.ok) {
    throw await readApiError(response);
  }
  const body = await readSuccessBody<Body>(response);
  return { body, etag: response.headers.get("etag") };
}

/**
 * Read a success body, or fail when it is not JSON.
 * @param response - The successful response.
 * @returns The parsed body.
 * @throws {ApiError} When the body is not JSON.
 */
async function readSuccessBody<Body>(response: Response): Promise<Body> {
  try {
    return (await response.json()) as Body;
  } catch {
    throw new ApiError(response.status, ApiErrorType.InternalError, GENERIC_ERROR_MESSAGE);
  }
}

/**
 * Read an error response into an ApiError.
 * @param response - The failed response.
 * @returns The error to throw.
 * @throws Does not throw.
 */
async function readApiError(response: Response): Promise<ApiError> {
  try {
    const payload: unknown = await response.json();
    const body = readErrorBody(payload);
    if (body === null) {
      return new ApiError(response.status, ApiErrorType.InternalError, GENERIC_ERROR_MESSAGE);
    }
    return new ApiError(body.code, body.error_type, body.error);
  } catch {
    return new ApiError(response.status, ApiErrorType.InternalError, GENERIC_ERROR_MESSAGE);
  }
}

/**
 * Return the error body when the payload has the API's three fields.
 * @param payload - The parsed JSON.
 * @returns The error body, or null when the shape does not match.
 * @throws Does not throw.
 */
function readErrorBody(payload: unknown): ErrorBody | null {
  if (typeof payload !== "object" || payload === null) {
    return null;
  }
  if (!("error" in payload) || !("code" in payload) || !("error_type" in payload)) {
    return null;
  }
  const { error, code, error_type: errorType } = payload;
  if (typeof error !== "string" || typeof code !== "number" || typeof errorType !== "string") {
    return null;
  }
  return { error, code, error_type: errorType };
}
