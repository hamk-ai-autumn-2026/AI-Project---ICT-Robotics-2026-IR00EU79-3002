import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.E2E_BASE_URL;
if (!baseURL) throw new Error("Set E2E_BASE_URL to a disposable staging deployment.");

export default defineConfig({
  testDir: "./tests",
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 1,
  reporter: "list",
  use: { baseURL, ...devices["Desktop Chrome"] },
});
