import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const DEFAULT_API_URL = "http://localhost:8000";
const apiUrl = process.env.REDLINE_API_URL ?? DEFAULT_API_URL;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": {
        target: apiUrl,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test_setup.ts"],
  },
});
