import { defineConfig, devices } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

function port(value: string | undefined, fallback: number) {
  const result = Number(value || fallback);
  if (!Number.isInteger(result) || result < 1024 || result > 65535)
    throw new Error("E2E ports must be integers between 1024 and 65535.");
  return result;
}
const frontendPort = port(process.env.E2E_FRONTEND_PORT, 3000);
const backendPort = port(process.env.E2E_BACKEND_PORT, 8000);
const frontendURL = `http://127.0.0.1:${frontendPort}`;
const backendURL = `http://127.0.0.1:${backendPort}`;
const frontendDirectory = resolve(process.env.E2E_FRONTEND_DIR || __dirname);
const repositoryRoot = resolve(__dirname, "..");
const python = resolve(
  repositoryRoot,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);

// Never point destructive browser fixtures at an unrelated running backend.
try {
  const manifest = JSON.parse(
    readFileSync(
      resolve(frontendDirectory, ".next/required-server-files.json"),
      "utf8",
    ),
  );
  const builtAPI = new URL(manifest.config.env.NEXT_PUBLIC_API_URL);
  if (
    builtAPI.protocol !== "http:" ||
    builtAPI.username ||
    builtAPI.password ||
    !["localhost", "127.0.0.1"].includes(builtAPI.hostname) ||
    Number(builtAPI.port || 80) !== backendPort ||
    builtAPI.pathname !== "/"
  )
    throw new Error("API target mismatch");
} catch {
  throw new Error(
    `Build the frontend with NEXT_PUBLIC_API_URL=${backendURL} before running browser tests. The built app must target this suite's disposable backend.`,
  );
}

export default defineConfig({
  testDir: "./tests",
  outputDir: "./test-results/browser",
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  use: {
    baseURL: frontendURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    ...devices["Desktop Chrome"],
    channel: process.env.PLAYWRIGHT_CHANNEL || undefined,
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn serve_e2e:app --app-dir backend/tests --host 127.0.0.1 --port ${backendPort}`,
      cwd: repositoryRoot,
      env: { PYTHONPATH: "backend", VOXDESK_CORS_ORIGINS: frontendURL },
      url: `${backendURL}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: `npm run start -- --port ${frontendPort}`,
      cwd: frontendDirectory,
      url: frontendURL,
      reuseExistingServer: false,
    },
  ],
});
