import { expect, test, type Page } from "@playwright/test";

async function message(page: Page, text: string) {
  const field = page.getByRole("textbox", { name: "Your message" });
  await expect(field).toBeEnabled();
  await field.fill(text);
  await page.getByRole("button", { name: "Send message", exact: true }).click();
  await expect(field).toBeEnabled();
}

async function open(page: Page) {
  await page.goto("/");
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
  const mute = page.getByRole("button", { name: "Spoken replies on" });
  if (await mute.isEnabled()) await mute.click();
}

for (const width of [390, 1440]) {
  test(`appointment cards preserve saved details through management actions at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await open(page);
    const appointment = () =>
      page
        .getByRole("button", { name: "View appointment", exact: true })
        .click();
    await appointment();
    await expect(
      page.getByRole("heading", { name: "No appointment yet", exact: true }),
    ).toBeVisible();
    await expect(page.locator(".inspector-toggle")).toBeHidden();
    await page.screenshot({
      path: `test-results/appointment-${width}-empty-dark.png`,
    });
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await page.waitForTimeout(200);
    await page.screenshot({
      path: `test-results/appointment-${width}-empty-light.png`,
    });
    await page.getByRole("button", { name: "Switch to dark mode" }).click();
    await page
      .getByRole("button", {
        name: "Book a haircut tomorrow at 3 PM",
        exact: true,
      })
      .click();
    await expect(
      page.getByRole("textbox", { name: "Your message" }),
    ).toBeEnabled();
    await expect(page.getByRole("log")).toContainText(
      "What name should I use?",
    );
    await appointment();
    const draft = page.getByRole("region", {
      name: "Appointment draft",
      exact: true,
    });
    await expect(draft).toContainText("Draft · not booked");
    await expect(draft).toContainText("2026-10-27 · 15:00");
    await draft
      .getByRole("button", { name: "Continue in conversation", exact: true })
      .click();
    await message(page, "Riley Demo");
    await page
      .getByRole("button", { name: "Confirm appointment", exact: true })
      .click();
    await appointment();
    const saved = page.getByRole("region", {
      name: "Saved appointment",
      exact: true,
    });
    await expect(saved.locator(".booking-status")).toHaveText("confirmed");
    await expect(
      saved.getByRole("heading", { name: "Classic Haircut", exact: true }),
    ).toBeVisible();
    await expect(saved.locator(".appointment-facts")).toContainText(
      "Riley Demo",
    );
    await expect(saved.locator(".appointment-facts")).toContainText("30 min");
    await expect(saved.locator(".appointment-facts")).toContainText(
      "PKR 1,800",
    );
    await expect(saved.locator("time")).toHaveAttribute(
      "datetime",
      "2026-10-27T15:00:00+05:00",
    );
    const reference = await saved.locator("code").textContent();
    await page.screenshot({
      path: `test-results/appointment-${width}-saved-dark.png`,
    });
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await page.waitForTimeout(200);
    await page.screenshot({
      path: `test-results/appointment-${width}-saved-light.png`,
    });
    await saved
      .getByRole("button", { name: "Reschedule", exact: true })
      .click();
    await expect(page.getByRole("log")).toContainText("What new date or time");
    await message(page, "October 28 2026 at 4 PM");
    await appointment();
    await expect(saved.locator("time")).toHaveAttribute(
      "datetime",
      "2026-10-27T15:00:00+05:00",
    );
    await expect(
      saved.getByRole("region", { name: "Proposed change", exact: true }),
    ).toContainText("2026-10-28 · 16:00");
    await saved
      .getByRole("button", { name: "Review in conversation", exact: true })
      .click();
    await message(page, "no");
    await appointment();
    await expect(saved.locator("code")).toHaveText(reference!);
    await saved
      .getByRole("button", { name: "Cancel booking", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "Confirm cancellation", exact: true }),
    ).toBeVisible();
    await appointment();
    await expect(saved.locator(".booking-status")).toHaveText("confirmed");
    await expect(
      saved.getByRole("region", { name: "Proposed change", exact: true }),
    ).toContainText("Proposed cancellation");
    await saved
      .getByRole("button", { name: "Review in conversation", exact: true })
      .click();
    await page
      .getByRole("button", { name: "Confirm cancellation", exact: true })
      .click();
    await appointment();
    await expect(saved.locator(".booking-status")).toHaveText("cancelled");
    await expect(
      saved.getByRole("button", { name: "Reschedule", exact: true }),
    ).toHaveCount(0);
    await expect(
      saved.getByRole("button", { name: "Cancel booking", exact: true }),
    ).toHaveCount(0);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
  });
}

for (const width of [390, 1440]) {
  test(`services are a workspace page with safe booking handoff at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await open(page);
    const input = page.getByRole("textbox", { name: "Your message" });
    await input.fill("Keep my unfinished message");
    const rail = page.getByRole("complementary", { name: "Application" });
    async function services() {
      if (width < 570)
        await page
          .locator(".topbar")
          .getByRole("button", { name: "Expand navigation", exact: true })
          .click();
      await rail
        .getByRole("button", { name: "View studio services", exact: true })
        .click();
    }
    await services();
    const view = page.getByRole("region", {
      name: "Studio services workspace",
    });
    await expect(view).toBeVisible();
    await expect(
      page.getByRole("heading", { name: "Studio services", exact: true }),
    ).toBeVisible();
    await expect(
      rail.getByRole("button", { name: "View studio services" }),
    ).toHaveAttribute("aria-current", "page");
    await expect(page.getByRole("log")).toBeHidden();
    await expect(page.locator(".service-banner")).toHaveCount(0);
    await expect(view.getByRole("button", { name: /^Book / })).toHaveCount(3);
    await expect(
      view.getByRole("region", { name: "Service catalog" }),
    ).toContainText("PKR 1,800");
    await expect(
      view.getByRole("region", { name: "Service catalog" }),
    ).toContainText("Save PKR 200");
    await expect(
      view.getByRole("region", { name: "Opening hours" }),
    ).toContainText("Asia/Karachi");
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    await page.screenshot({ path: `test-results/services-${width}-dark.png` });
    await page.getByRole("button", { name: "Switch to light mode" }).click();
    await page.waitForTimeout(200);
    await page.screenshot({ path: `test-results/services-${width}-light.png` });
    await view
      .getByRole("button", { name: "Start a conversation", exact: true })
      .click();
    await expect(input).toHaveValue("Keep my unfinished message");
    await expect(input).toBeFocused();
    await services();
    await view
      .getByRole("button", { name: "Book Haircut + Beard", exact: true })
      .click();
    await expect(input).toBeEnabled();
    await expect(page.getByRole("log")).toContainText("Haircut + Beard");
    await expect(page.getByRole("log")).toContainText("Which date?");
    await expect(
      page.getByRole("region", { name: "Latest appointment receipt" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Confirm appointment", exact: true }),
    ).toHaveCount(0);
  });
}

for (const { width, suggestion, expectedReply } of [
  {
    width: 390,
    suggestion: "Explore availability",
    expectedReply: "Available starts:",
  },
  { width: 1440, suggestion: "Services & pricing", expectedReply: "PKR" },
]) {
  test(`first-turn suggestions sit above the composer and stay dismissed at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 900 });
    await open(page);
    const suggestions = page.getByRole("region", {
      name: "Conversation suggestions",
    });
    const input = page.getByRole("textbox", { name: "Your message" });
    await expect(suggestions).toBeVisible();
    await expect(suggestions.getByRole("button")).toHaveCount(2);
    await expect(page.locator(".inspector-toggle")).toHaveText(
      "Decision inspector",
    );
    await expect(page.locator(".inspector-toggle span")).toBeVisible();
    const choices = (await suggestions.boundingBox())!;
    const composer = (await page.locator(".composer").boundingBox())!;
    expect(choices.y + choices.height).toBeLessThanOrEqual(composer.y);
    expect(
      Math.abs(choices.x + choices.width / 2 - composer.x - composer.width / 2),
    ).toBeLessThan(2);
    await input.fill("An unsent draft");
    await expect(suggestions).toBeVisible();
    await suggestions
      .getByRole("button", { name: suggestion, exact: true })
      .click();
    await expect(input).toBeEnabled();
    await expect(page.getByRole("log")).toContainText(expectedReply);
    await expect(suggestions).toHaveCount(0);
    await page.reload();
    await expect(input).toBeEnabled();
    await expect(suggestions).toHaveCount(0);
    await page
      .getByRole("button", { name: "New session", exact: true })
      .click();
    await expect(suggestions).toBeVisible();
    await message(page, "What are your hours?");
    await expect(suggestions).toHaveCount(0);
  });
}

test("navigation and inspector resize independently without losing a draft", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await open(page);
  const input = page.getByRole("textbox", { name: "Your message" });
  await input.fill("Keep this unfinished message");
  const rail = page.getByRole("complementary", { name: "Application" });
  const narrow = await rail.boundingBox();
  await rail
    .getByRole("button", { name: "Expand navigation", exact: true })
    .click();
  await expect(rail).toHaveCSS("width", "232px");
  expect((await rail.boundingBox())!.width).toBeGreaterThan(narrow!.width);
  await page
    .getByRole("button", { name: "Expand decision inspector", exact: true })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Decision inspector" }),
  ).toBeVisible();
  await rail
    .getByRole("button", { name: "Collapse navigation", exact: true })
    .click();
  await expect(rail).toHaveCSS("width", "76px");
  await expect(input).toHaveValue("Keep this unfinished message");
  await page
    .getByRole("button", { name: "Collapse decision inspector", exact: true })
    .click();
  await expect(
    page.getByRole("complementary", { name: "Decision inspector" }),
  ).toBeHidden();
  await page.getByRole("button", { name: "Switch to light mode" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(input).toHaveValue("Keep this unfinished message");
});

test("mobile navigation opens appointment and returns to the preserved conversation", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  const input = page.getByRole("textbox", { name: "Your message" });
  await input.fill("An unfinished mobile message");
  await page
    .locator(".topbar")
    .getByRole("button", { name: "Expand navigation", exact: true })
    .click();
  const rail = page.getByRole("complementary", { name: "Application" });
  await rail
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await rail
    .getByRole("button", { name: "Collapse navigation", exact: true })
    .click();
  await expect(
    page.getByRole("region", { name: "Appointment workspace" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Back to conversation", exact: true })
    .click();
  await expect(input).toHaveValue("An unfinished mobile message");
  await expect(page.locator(".main-grid")).toHaveCSS("width", "362px");
  await page
    .locator(".topbar")
    .getByRole("button", { name: "Expand navigation", exact: true })
    .click();
  const backdrop = page.getByRole("button", {
    name: "Close navigation",
    exact: true,
  });
  await expect(backdrop).toBeVisible();
  await backdrop.click({ position: { x: 360, y: 400 } });
  await expect(rail).toBeHidden();
  await expect(page.getByRole("log")).toContainText(
    "Welcome to Northline Studio",
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});

test("typed booking, contextual correction, real trace and receipt", async ({
  page,
}) => {
  await open(page);
  await message(page, "Book a haircut tomorrow at 3 PM");
  await expect(page.getByRole("log")).toContainText("What name should I use?");
  await message(page, "Actually make it 5 PM");
  await message(page, "Alex Example");
  await expect(
    page.getByRole("button", { name: "Confirm appointment" }),
  ).toBeVisible();
  await expect(page.locator(".booking-status")).toHaveText(
    "Needs explicit confirmation",
  );
  await page.getByRole("button", { name: "Confirm appointment" }).click();
  await expect(
    page.getByRole("region", { name: "Latest appointment receipt" }),
  ).toContainText("Alex Example");
  await expect(
    page.getByRole("region", { name: "Latest appointment receipt" }),
  ).toContainText("17:00");
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "Saved appointment", exact: true })
      .locator(".booking-status"),
  ).toHaveText("confirmed");
  await expect(page.locator(".booking-detail")).toContainText("17:00");
  await page
    .getByRole("button", { name: "Voice receptionist", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Expand decision inspector", exact: true })
    .click();
  await page.getByRole("button", { name: "View raw decision trace" }).click();
  await expect(page.locator(".raw-trace")).toContainText("commit.confirmed");
  await expect(page.locator(".raw-trace")).toContainText(
    "AWAITING_CONFIRMATION",
  );
  await page.screenshot({
    path: "test-results/desktop-workspace.png",
    fullPage: true,
  });
});

test("existing appointment can be rescheduled and cancelled through the UI", async ({
  page,
}) => {
  await open(page);
  await message(page, "Book a beard trim 2026-10-28 at 11 AM");
  await message(page, "Jordan Demo");
  await message(page, "yes");
  const reference = (await page.locator(".booking-detail code").textContent())!;
  await message(page, `reschedule ${reference} Friday at 4 PM`);
  await expect(page.locator(".proposal-status")).toHaveText(
    "Needs explicit confirmation",
  );
  await message(page, "yes");
  await expect(page.locator(".booking-detail time")).toHaveAttribute(
    "datetime",
    "2026-10-30T16:00:00+05:00",
  );
  await message(page, `cancel ${reference}`);
  await page.getByRole("button", { name: "Confirm cancellation" }).click();
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "Saved appointment", exact: true })
      .getByRole("heading", { name: "Beard Trim", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".booking-status")).toHaveText("cancelled");
});

test("uncertain network outcome retries the same request after a real commit", async ({
  page,
}) => {
  await open(page);
  await message(page, "book a haircut 2026-10-29 at 2 PM");
  await message(page, "Taylor Demo");
  const ids: string[] = [];
  let dropped = false;
  await page.route("**/api/sessions/*/turns", async (route) => {
    const body = route.request().postDataJSON();
    if (body.text === "yes") {
      ids.push(body.request_id);
      if (!dropped) {
        dropped = true;
        await route.fetch(); // The server really commits; only the response is lost.
        await route.abort("failed");
        return;
      }
    }
    await route.continue();
  });
  await page.getByRole("button", { name: "Confirm appointment" }).click();
  await expect(
    page.getByRole("button", { name: "Retry same message" }),
  ).toBeVisible();
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeDisabled();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Retry same message" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Retry same message" }).click();
  await page
    .getByRole("button", { name: "View appointment", exact: true })
    .click();
  await expect(
    page
      .getByRole("region", { name: "Saved appointment", exact: true })
      .locator(".booking-status"),
  ).toHaveText("confirmed");
  expect(ids).toHaveLength(2);
  expect(ids[0]).toBe(ids[1]);
  await expect(
    page.locator(".message.user p").filter({ hasText: /^yes$/ }),
  ).toHaveCount(1);
});

test("browser speech adapter submits a final transcript and stops recognition before speaking", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const state = { active: false, spoke: [] as string[], echo: false };
    Object.assign(window, { __voiceTest: state });
    class MockRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      onresult: ((event: unknown) => void) | null = null;
      onerror = null;
      onend: (() => void) | null = null;
      start() {
        state.active = true;
        setTimeout(
          () =>
            this.onresult?.({
              results: [
                { isFinal: true, 0: { transcript: "What are your prices?" } },
              ],
            }),
          20,
        );
      }
      abort() {
        state.active = false;
        this.onend?.();
      }
      stop() {
        this.abort();
      }
    }
    Object.assign(window, { SpeechRecognition: MockRecognition });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        speaking: false,
        cancel() {},
        speak(utterance: SpeechSynthesisUtterance) {
          if (state.active) state.echo = true;
          state.spoke.push(utterance.text);
          setTimeout(
            () => utterance.onend?.(new Event("end") as SpeechSynthesisEvent),
            10,
          );
        },
      },
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Start microphone" }).click();
  await expect(page.getByRole("log")).toContainText("What are your prices?");
  await page
    .getByRole("button", { name: "Expand decision inspector", exact: true })
    .click();
  await expect(page.locator(".rule-name")).toHaveText("business.question");
  const state = await page.evaluate(
    () =>
      (
        window as unknown as {
          __voiceTest: { active: boolean; spoke: string[]; echo: boolean };
        }
      ).__voiceTest,
  );
  expect(state.spoke.length).toBe(1);
  expect(state.echo).toBe(false);
  expect(state.active).toBe(false);
});

test("unsupported speech keeps typed input usable and mobile layout fits", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "SpeechRecognition", {
      value: undefined,
      configurable: true,
    });
    Object.defineProperty(window, "webkitSpeechRecognition", {
      value: undefined,
      configurable: true,
    });
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  await expect(
    page.getByRole("button", { name: "Start microphone" }),
  ).toBeDisabled();
  await message(page, "check availability for a beard trim Friday afternoon");
  await expect(page.locator(".availability-card")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "test-results/mobile-workspace.png",
    fullPage: true,
  });
});

test("microphone permission failure gives an actionable typed fallback", async ({
  page,
}) => {
  await page.addInitScript(() => {
    class DeniedRecognition {
      lang = "";
      continuous = false;
      interimResults = false;
      onresult = null;
      onend: (() => void) | null = null;
      onerror: ((event: { error: string }) => void) | null = null;
      start() {
        setTimeout(() => this.onerror?.({ error: "not-allowed" }), 10);
      }
      abort() {
        this.onend?.();
      }
      stop() {
        this.abort();
      }
    }
    Object.assign(window, { SpeechRecognition: DeniedRecognition });
  });
  await open(page);
  await page.getByRole("button", { name: "Start microphone" }).click();
  await expect(
    page.getByRole("region", { name: "Voice conversation" }).getByRole("alert"),
  ).toContainText("Microphone permission was denied");
  await message(page, "What are your prices?");
  await expect(page.getByRole("log")).toContainText("PKR 1,800");
});
