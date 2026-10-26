import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

async function say(page: Page, text: string) {
  const version = await page.locator(".message.caller").count();
  await page.getByLabel("Your message", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator(".message.caller")).toHaveCount(version + 1);
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
}
test("a real API conversation records one pending claim", async ({ page }) => {
  const failures: string[] = [];
  page.on("pageerror", (error) => failures.push(error.message));
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Lost something?" }),
  ).toBeVisible();
  await say(
    page,
    "black backpack with two compartments near the food court yesterday",
  );
  await expect(page.getByRole("log")).not.toContainText("yellow duck");
  await say(page, "yellow duck keychain");
  await expect(page.getByRole("log")).toContainText("Shall I submit it?");
  await say(page, "yes");
  await expect(
    page.getByText("Pending staff review", { exact: true }),
  ).toBeVisible();
  const reference = await page.locator(".receipt strong").textContent();
  await say(page, "yes");
  await expect(page.locator(".receipt strong")).toHaveText(reference!);
  await page.reload();
  await expect(page.locator(".receipt strong")).toHaveText(reference!);
  expect(failures).toEqual([]);
});

test("no match becomes a confirmed lost report", async ({ page }) => {
  await page.goto("/");
  await say(page, "purple wallet with stars near the cinema yesterday");
  for (let count = 0; count < 6; count++) {
    if (
      await page
        .getByRole("log")
        .textContent()
        .then((text) => text?.includes("Shall I submit it?"))
    )
      break;
    await say(page, "I don't know");
  }
  await say(page, "yes");
  await expect(page.getByText("Lost-item report recorded")).toBeVisible();
});

test("a correction in a confirmation does not submit the old claim", async ({
  page,
}) => {
  await page.goto("/");
  await say(page, "black backpack with two compartments food court yesterday");
  await say(page, "yellow duck keychain");
  await say(page, "yes but actually it was blue");
  await expect(page.locator(".receipt")).toHaveCount(0);
  await expect(
    page.locator(".detail-row").filter({ hasText: "Colour" }),
  ).toContainText("blue");
});

test("new browser context cannot read another caller conversation", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  await say(page, "black backpack");
  const other = await browser.newContext();
  const second = await other.newPage();
  await second.goto("http://127.0.0.1:5181");
  await expect(
    second.getByLabel("Your message", { exact: true }),
  ).toBeEnabled();
  await expect(second.getByRole("log")).not.toContainText("black backpack");
  await expect(second.locator(".detail-row").first()).toContainText(
    "Not provided",
  );
  await other.close();
});

test("unsupported recognition still provides a complete typed interaction", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "MediaRecorder", { value: undefined });
  });
  await page.goto("/");
  await expect(
    page.getByText("Microphone recording isn't available here.", {
      exact: false,
    }),
  ).toBeVisible();
  await say(page, "a black bag");
  await expect(page.getByRole("log")).toContainText("a black bag");
});
