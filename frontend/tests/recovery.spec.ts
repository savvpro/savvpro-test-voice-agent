import { expect, test, type Page } from "@playwright/test";

async function open(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
  const mute = page.getByRole("button", { name: "Spoken replies on" });
  if (await mute.isEnabled()) await mute.click();
}

async function message(page: Page, text: string) {
  const field = page.getByRole("textbox", { name: "Your message" });
  await field.fill(text);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(field).toBeEnabled();
}

test("storage quota failure leaves the live conversation usable", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key.startsWith("voxdesk."))
        throw new DOMException("Quota exceeded", "QuotaExceededError");
      return original.call(this, key, value);
    };
  });
  await open(page);
  await message(page, "What are your prices?");
  await expect(page.getByRole("log")).toContainText("PKR 1,800");
  await expect(page.locator(".storage-warning")).toContainText(
    "continue in this tab",
  );
  await expect(
    page.getByRole("button", { name: "New session", exact: true }),
  ).toBeEnabled();
  expect(errors).toEqual([]);
});

test("blocked storage reads and removals do not prevent startup", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new DOMException("Blocked", "SecurityError");
    };
    Storage.prototype.removeItem = () => {
      throw new DOMException("Blocked", "SecurityError");
    };
  });
  await open(page);
  await message(page, "What are your hours?");
  await expect(page.getByRole("log")).toContainText("10 AM");
  await expect(page.locator(".storage-warning")).toBeVisible();
});

test("malformed pending data is validated before any retry", async ({
  page,
}) => {
  await open(page);
  await page.evaluate(() =>
    sessionStorage.setItem("voxdesk.pending", JSON.stringify({ text: 7 })),
  );
  await page.reload();
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
  await expect(page.locator(".storage-warning")).toContainText("invalid");
  await expect(
    page.getByRole("button", { name: "Retry same message" }),
  ).toHaveCount(0);
});

test("lost commit response retries from memory when persistent storage fails", async ({
  page,
}) => {
  await open(page);
  await message(
    page,
    "book a haircut on November 4 2026 at 10 AM with the name Morgan Demo",
  );
  await page.evaluate(() => {
    const original = Storage.prototype.setItem;
    Storage.prototype.setItem = function (key, value) {
      if (key === "voxdesk.pending")
        throw new DOMException("Quota exceeded", "QuotaExceededError");
      return original.call(this, key, value);
    };
  });
  const ids: string[] = [];
  let dropped = false;
  await page.route("**/api/sessions/*/turns", async (route) => {
    const body = route.request().postDataJSON();
    ids.push(body.request_id);
    if (!dropped) {
      dropped = true;
      await route.fetch();
      await route.abort("failed");
    } else await route.continue();
  });
  await page.getByRole("button", { name: "Confirm appointment" }).click();
  await page.getByRole("button", { name: "Retry same message" }).click();
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Saved appointment", exact: true }),
  ).toContainText("confirmed");
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
  await expect(
    page.locator(".message.user p").filter({ hasText: /^yes$/ }),
  ).toHaveCount(1);
});

test("abandoned changes cannot replace saved details in the appointment card", async ({
  page,
}) => {
  await open(page);
  await message(
    page,
    "book a haircut on November 2 2026 at 10 AM with the name Robin Demo",
  );
  await message(page, "yes");
  await message(page, "reschedule it to November 3 2026 at 11 AM");
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  const saved = page.getByRole("region", {
    name: "Saved appointment",
    exact: true,
  });
  await expect(saved.locator(".booking-detail")).toContainText(
    "2026-11-02 · 10:00",
  );
  await expect(
    page.getByRole("region", { name: "Proposed change", exact: true }),
  ).toContainText("2026-11-03 · 11:00");
  await page
    .getByRole("button", { name: "Voice receptionist", exact: true })
    .click();
  await message(page, "end conversation");
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await expect(saved.locator(".booking-detail")).toContainText(
    "2026-11-02 · 10:00",
  );
  await expect(saved).not.toContainText("Draft · not booked");
  await expect(
    page.getByRole("region", { name: "Proposed change", exact: true }),
  ).toHaveCount(0);
});

test("connection status reflects network failure and recovers on retry", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/sessions/*/turns", (route) => route.abort("failed"));
  await page
    .getByRole("textbox", { name: "Your message" })
    .fill("What are your prices?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(
    page.getByText("Backend unavailable", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".conversation-status")).toHaveText(
    "Connection interrupted",
  );
  await page.unroute("**/api/sessions/*/turns");
  await page.getByRole("button", { name: "Retry same message" }).click();
  await expect(
    page.getByText("Backend connected", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
});

test("unreadable backend responses preserve a safely retryable message", async ({
  page,
}) => {
  await open(page);
  await page.route("**/api/sessions/*/turns", (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<html>upstream error</html>",
    }),
  );
  await page
    .getByRole("textbox", { name: "Your message" })
    .fill("What are your prices?");
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(page.locator(".error-box")).toContainText("unreadable response");
  await page.unroute("**/api/sessions/*/turns");
  await page.getByRole("button", { name: "Retry same message" }).click();
  await expect(page.getByRole("log")).toContainText("PKR 1,800");
});
