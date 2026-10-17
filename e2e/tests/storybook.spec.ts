import { expect, test } from "@playwright/test";

test("create, read, download, share for review, and delete a book", async ({ page }) => {
  let storyId: number | undefined;
  let publishToken = "";
  try {
    await page.goto("/");
    await page.locator('[name="child_name"]').fill(`E2E Reader ${Date.now()}`);
    await page.locator('[name="child_appearance"]').fill("Short dark hair and a yellow raincoat");
    await page.locator('[name="favorite_theme"]').fill("friendly sea turtles");
    await page.locator('[name="reading_level"]').selectOption("beginner");
    await page.locator('[name="moral_lesson"]').fill("Helping friends matters");
    await page.locator('[name="art_style"]').selectOption("pencil");

    const createdResponse = page.waitForResponse((response) =>
      response.request().method() === "POST" && response.url().endsWith("/api/stories/"),
    );
    await page.locator("#submit-button").click();
    const created = await (await createdResponse).json();
    storyId = created.story.id;
    publishToken = created.publishToken;

    await expect(page.locator("#storybook")).toBeVisible({ timeout: 180_000 });
    await expect(page.locator("#download-link")).toBeVisible({ timeout: 180_000 });
    await expect(page.locator("[data-reader-text]")).not.toBeEmpty();

    await page.locator("#download-link").click();
    await expect(page.locator("#download-status")).toHaveText("Your book download has started.");

    await page.locator("#publish-consent").check();
    await page.locator("#publish-button").click();
    await expect(page.locator("#publish-status")).toContainText("sent for community review");
  } finally {
    if (storyId && publishToken) {
      const csrfToken = await page.locator('#story-form [name="csrfmiddlewaretoken"]').inputValue().catch(() => "");
      const cleanup = await page.request.post(`/api/stories/${storyId}/delete/`, {
        headers: { "X-CSRFToken": csrfToken, "X-Story-Token": publishToken },
      });
      expect(cleanup.status()).toBe(204);
    }
  }
});
