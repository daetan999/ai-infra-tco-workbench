const { defineConfig, devices } = require("@playwright/test");

const python = process.env.PYTHON_EXECUTABLE || "python3";
const database = `/tmp/tco-workbench-e2e-${process.pid}.db`;

module.exports = defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:8033",
    screenshot: "only-on-failure",
    trace: "on-first-retry"
  },
  webServer: {
    command: `TCO_WORKBENCH_DB=${database} SEED_DEMO_DATA=true ${python} -m uvicorn app.main:app --host 127.0.0.1 --port 8033`,
    url: "http://127.0.0.1:8033/health",
    reuseExistingServer: !process.env.CI,
    timeout: 120000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
