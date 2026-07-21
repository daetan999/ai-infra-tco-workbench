const { test, expect } = require("@playwright/test");

test("loads a fictional scenario and renders authoritative engine results", async ({ page }) => {
  await page.goto("/");

  await expect(page.locator(".scenario-item")).toHaveCount(3);
  await page.getByRole("button", { name: /CPU-to-GPU inference modernization/i }).click();
  await expect(page.getByRole("heading", { name: "CPU-to-GPU inference modernization" })).toBeVisible();
  await expect(page.locator("#analysis-source-label")).toHaveText("Saved engine result");
  await expect(page.locator("#net-impact")).not.toHaveText("—");
  await expect(page.locator("#confidence-score")).toHaveText("15 / 100");
  await expect(page.locator("#lineage-grid .lineage-card").first()).toBeVisible();

  await page.locator("#export-button").click();
  const download = page.waitForEvent("download");
  await page.getByRole("menuitem", { name: /Board memo/i }).click();
  await expect((await download).suggestedFilename()).toMatch(/\.pdf$/);
});

test("edits and saves a scenario as a new immutable analysis version", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /Shared serving utilization/i }).click();

  const name = page.locator("#scenario-name");
  await name.fill("Shared serving utilization - reviewed");
  await expect(page.locator("#analysis-source-label")).toHaveText("Draft preview");
  await expect(page.locator("#sync-label")).toHaveText("Unsaved changes");

  await page.locator("#save-button").click();
  await expect(page.locator("#toast-region")).toContainText("Scenario saved");
  await expect(page.locator("#analysis-source-label")).toHaveText("Saved engine result");
  await expect(page.locator("#scenario-title")).toHaveText("Shared serving utilization - reviewed");
});

test("keeps the decision workspace usable at a narrow viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.locator("#new-scenario")).toBeVisible();
  await expect(page.locator("#comparison-heading")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > innerWidth);
  expect(overflow).toBe(false);
});
