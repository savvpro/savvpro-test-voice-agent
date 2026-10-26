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
    page.getByRole("heading", { name: "Appointment confirmed", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".booking-detail")).toContainText("17:00");
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
  await expect(page.locator(".booking-status")).toHaveText(
    "Needs explicit confirmation",
  );
  await message(page, "yes");
  await expect(page.locator(".booking-detail")).toContainText(
    "2026-10-30 · 16:00",
  );
  await message(page, `cancel ${reference}`);
  await page.getByRole("button", { name: "Confirm cancellation" }).click();
  await expect(
    page.getByRole("heading", { name: "Appointment cancelled", exact: true }),
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
  await expect(
    page.getByRole("heading", { name: "Appointment confirmed", exact: true }),
  ).toBeVisible();
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
  await expect(page.getByRole("region", { name: "Voice conversation" }).getByRole("alert")).toContainText(
    "Microphone permission was denied",
  );
  await message(page, "What are your prices?");
  await expect(page.getByRole("log")).toContainText("PKR 1,800");
});
