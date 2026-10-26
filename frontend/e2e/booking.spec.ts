import { test, expect, Page } from "@playwright/test";
async function send(page: Page, text: string) {
  await page.getByLabel("Your message", { exact: true }).fill(text);
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Send", exact: true }),
  ).toBeDisabled();
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
  await expect(page.getByLabel("Your message", { exact: true })).toHaveValue(
    "",
  );
}
test("buffet booking, deposit, amendment and cancellation", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await expect(page.getByLabel("Your message", { exact: true })).toBeEnabled();
  await page.getByRole("button", { name: "Mute assistant" }).click();
  const date = new Date();
  date.setDate(date.getDate() + 20);
  for (const value of [
    "hi-tea",
    date.toISOString().slice(0, 10),
    "6 PM",
    "2 adults",
    "children aged 3 and 7",
    "indoor",
    "name is Demo Browser",
    "03000000000",
  ])
    await send(page, value);
  await expect(page.locator(".state")).toHaveText("review");
  await expect(page.locator(".quote")).toContainText("5,000");
  await send(page, "yes");
  await expect(page.locator(".booking")).toContainText("payment pending");
  await page.getByRole("button", { name: "Simulate deposit" }).click();
  await expect(page.locator(".booking")).toContainText("confirmed");
  await send(page, "4 PM");
  await expect(page.locator(".state")).toHaveText("review");
  await send(page, "yes");
  await page.getByRole("button", { name: "Simulate deposit" }).click();
  await expect(page.locator(".state")).toHaveText("confirmed");
  await send(page, "cancel");
  await send(page, "yes");
  await expect(page.locator(".booking")).toContainText("cancelled");
  expect(errors).toEqual([]);
});
test("responsive first screen and conversation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Book a table", exact: true }),
  ).toBeEnabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBeTruthy();
  await page.getByRole("button", { name: "Book a table", exact: true }).click();
  await expect(page.locator(".details")).toContainText("a la carte");
});
