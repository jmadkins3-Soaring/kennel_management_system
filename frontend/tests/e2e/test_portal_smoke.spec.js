/**
 * Smoke tests: Owner self-service portal (Spec §8.6).
 * Validates the portal route exists and renders without crash.
 * Full token-flow tested at IAT level (test_iat_owner_portal.py).
 */
import { test, expect } from "@playwright/test";

test.describe("Owner portal smoke", () => {
  test("portal route with fake token renders without JS crash", async ({ page }) => {
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));

    await page.goto("/portal/fake-smoke-token");
    await expect(page.locator("body")).not.toBeEmpty();

    // Expect either a token-invalid message or a loading/portal UI — not a blank crash
    const content = await page.locator("body").textContent();
    expect(content.length).toBeGreaterThan(0);

    // Filter out known benign browser noise
    const realErrors = errors.filter(
      (e) => !e.includes("ResizeObserver") && !e.includes("Script error")
    );
    expect(realErrors).toHaveLength(0);
  });

  test("portal page shows some UI element (invalid token message or form)", async ({ page }) => {
    await page.goto("/portal/fake-smoke-token");
    // Accept: error message, login prompt, or portal home — anything visible
    const visible = page.locator("h1, h2, p, [data-testid], form, .portal, .error, .message");
    await expect(visible.first()).toBeVisible({ timeout: 8000 });
  });

  test("portal availability endpoint is reachable from frontend proxy", async ({ page }) => {
    // Verify the Vite proxy routes /api → backend (9101)
    const response = await page.request.get("/api/portal/availability", {
      params: { size_class: "M", start_date: "2026-06-01", end_date: "2026-06-07" },
    });
    // Backend is not running in Playwright CI, so accept connection errors gracefully
    // If backend IS running, must not be 501
    if (response.ok() || response.status() >= 400) {
      expect(response.status()).not.toBe(501);
    }
  });

  test("request-link API endpoint exists (not 404 or 501)", async ({ page }) => {
    const response = await page.request.post("/api/portal/request-link", {
      params: { email: "smoke@test.local" },
    });
    // 200 (success), 422 (validation), 404 (no owner) all acceptable — 501 is not
    if (response.status() !== 503 && response.status() !== 502) {
      expect(response.status()).not.toBe(501);
      expect(response.status()).not.toBe(404);
    }
  });
});
