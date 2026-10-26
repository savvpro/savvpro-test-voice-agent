import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
      "/health": process.env.API_PROXY_TARGET || "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    coverage: {
      provider: "v8",
      include: [
        "src/api/**/*.ts",
        "src/features/**/*.{ts,tsx}",
        "src/speech/**/*.{ts,tsx}",
      ],
      reporter: ["text", "json-summary", "lcov"],
      thresholds: { lines: 80, branches: 80, functions: 80, statements: 80 },
    },
  },
});
