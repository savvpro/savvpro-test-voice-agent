import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
const database = join(tmpdir(), `mezban-e2e-${randomUUID()}.db`);
process.env.MEZBAN_TEST_DB = database;
const python =
  process.env.MEZBAN_PYTHON ||
  resolve(
    process.platform === "win32"
      ? "../.venv/Scripts/python.exe"
      : "../.venv/bin/python",
  );
export default defineConfig({
  testDir: "./e2e",
  testMatch: "**/*.spec.ts",
  workers: 1,
  globalSetup: "./e2e/cleanup.ts",
  use: {
    baseURL: "http://127.0.0.1:5174",
    channel: process.env.CI ? undefined : "chrome",
    viewport: { width: 1440, height: 1040 },
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn app.main:app --host 127.0.0.1 --port 8012`,
      cwd: "../backend",
      url: "http://127.0.0.1:8012/api/health",
      env: { MEZBAN_DB: database },
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5174 --strictPort",
      url: "http://127.0.0.1:5174",
      env: { MEZBAN_API_TARGET: "http://127.0.0.1:8012" },
      reuseExistingServer: false,
    },
  ],
});
