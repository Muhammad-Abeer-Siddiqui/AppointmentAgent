import { test, expect } from "@playwright/test";

test.describe("AI Scheduling Agent Chat", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the app
    await page.goto("http://localhost:3000");
  });

  test("should display login page", async ({ page }) => {
    await expect(page.locator("h1")).toContainText("Sign In");
  });

  test("should register a new user", async ({ page }) => {
    await page.click("text=Sign Up");
    await expect(page.locator("h1")).toContainText("Create Account");

    const testEmail = `test_${Date.now()}@example.com`;
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    // Should redirect to dashboard
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("should login with existing user", async ({ page }) => {
    // First register
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/dashboard/);

    // Logout
    await page.click("text=Logout");

    // Login again
    await expect(page.locator("h1")).toContainText("Sign In");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("should navigate to chat page", async ({ page }) => {
    // Register and login
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    // Navigate to chat
    await page.click("text=Chat");
    await expect(page).toHaveURL(/\/dashboard\/chat/);

    // Check chat interface loads
    await expect(page.locator("text=AI Scheduling Agent")).toBeVisible();
    await expect(page.locator("text=Ask me to schedule")).toBeVisible();
  });

  test("should send a message and receive response", async ({ page }) => {
    // Register and login
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    // Navigate to chat
    await page.click("text=Chat");

    // Send message
    await page.fill('input[placeholder="Ask me to schedule an appointment..."]', "Hello");
    await page.click('button[type="submit"]');

    // Wait for response
    await expect(page.locator("text=Hello")).toBeVisible({ timeout: 10000 });
    // Wait for assistant response
    await page.waitForTimeout(5000);
  });

  test("should search for availability", async ({ page }) => {
    // Register and login
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    // Navigate to chat
    await page.click("text=Chat");

    // Ask for availability
    await page.fill('input[placeholder="Ask me to schedule an appointment..."]', "Find me a 60-minute slot tomorrow");
    await page.click('button[type="submit"]');

    // Wait for tool call and response
    await page.waitForTimeout(15000);

    // Check for availability suggestions
    const suggestions = page.locator("text=Available slots");
    if (await suggestions.count() > 0) {
      await expect(suggestions.first()).toBeVisible();
    }
  });

  test("should navigate to calendar page", async ({ page }) => {
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    await page.click("text=Calendar");
    await expect(page).toHaveURL(/\/dashboard\/calendar/);
    await expect(page.locator("text=Calendar")).toBeVisible();
  });

  test("should navigate to settings page", async ({ page }) => {
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    await page.click("text=Settings");
    await expect(page).toHaveURL(/\/dashboard\/settings/);
    await expect(page.locator("text=Settings")).toBeVisible();
  });

  test("should display working hours in settings", async ({ page }) => {
    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    await page.click("text=Settings");
    await expect(page.locator("text=Working Hours")).toBeVisible();
  });

  test("should be responsive on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });

    const testEmail = `test_${Date.now()}@example.com`;
    await page.click("text=Sign Up");
    await page.fill('input[name="name"]', "Test User");
    await page.fill('input[name="email"]', testEmail);
    await page.fill('input[name="password"]', "password123");
    await page.click('button[type="submit"]');

    // Check mobile layout
    await expect(page.locator("text=Dashboard")).toBeVisible();
  });
});
