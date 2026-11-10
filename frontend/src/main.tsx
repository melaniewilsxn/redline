import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { ApiError } from "./api/client.ts";
import { App } from "./app.tsx";
import "@fontsource/instrument-sans/400.css";
import "@fontsource/instrument-sans/500.css";
import "@fontsource/instrument-serif/400.css";
import "@fontsource-variable/newsreader/opsz.css";
import "./styles/tokens.css";
import "./styles/global.css";

const QUERY_STALE_TIME_MS = 30_000;
const QUERY_RETRY_LIMIT = 1;
const CLIENT_ERROR_MINIMUM = 400;
const CLIENT_ERROR_MAXIMUM = 500;

/**
 * Retry a failed read once, except for a client error.
 * @param failureCount - How many times this read has already failed.
 * @param error - The error from the last attempt.
 * @returns Whether to try again.
 * @throws Does not throw.
 */
function retryRead(failureCount: number, error: unknown): boolean {
  if (failureCount >= QUERY_RETRY_LIMIT) {
    return false;
  }
  if (
    error instanceof ApiError &&
    error.status >= CLIENT_ERROR_MINIMUM &&
    error.status < CLIENT_ERROR_MAXIMUM
  ) {
    return false;
  }
  return true;
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: QUERY_STALE_TIME_MS, retry: retryRead },
    mutations: { retry: false },
  },
});

const root = document.getElementById("root");
if (root === null) {
  throw new Error("The page is missing its root element");
}

createRoot(root).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
);
