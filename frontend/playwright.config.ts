import { defineConfig } from "@playwright/test";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const python =
  process.env.PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30000,
  expect: { timeout: 10000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5181",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    viewport: { width: 1440, height: 1000 },
  },
  webServer: [
    {
      command: `"${python}" scripts/e2e_server.py`,
      cwd: "../backend",
      url: "http://127.0.0.1:8011/health/ready",
      timeout: 60000,
      reuseExistingServer: false,
    },
    {
      command: "npm run dev -- --port 5181 --strictPort",
      url: "http://127.0.0.1:5181",
      env: { API_PROXY_TARGET: "http://127.0.0.1:8011" },
      timeout: 60000,
      reuseExistingServer: false,
    },
  ],
});
