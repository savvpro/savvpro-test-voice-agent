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
  await field.press("Enter");
  await expect(field).toBeEnabled();
}

test("keyboard input regains focus after a completed turn", async ({
  page,
}) => {
  await open(page);
  await message(page, "What are your prices?");
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeFocused();
});

for (const width of [360, 390, 768]) {
  test(`mobile/tablet panels fit and controls remain readable at ${width}px`, async ({
    page,
  }) => {
    await page.setViewportSize({ width, height: 844 });
    await open(page);
    if (width < 570) {
      const composer = await page.locator(".composer").boundingBox();
      expect(composer!.y + composer!.height).toBeLessThanOrEqual(844);
      const column = await page.locator(".inspector-column").boundingBox();
      const card = await page.locator(".booking-card").boundingBox();
      expect(Math.abs(column!.width - card!.width)).toBeLessThan(2);
    }
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true);
    const inputSize = await page
      .getByRole("textbox", { name: "Your message" })
      .evaluate((element) => parseFloat(getComputedStyle(element).fontSize));
    expect(inputSize).toBeGreaterThanOrEqual(16);
    await message(
      page,
      "book a haircut on November 9 2026 at 10 AM with the name Jamie Demo",
    );
    for (const name of ["Confirm appointment", "Discard"]) {
      const box = await page
        .getByRole("button", { name, exact: true })
        .boundingBox();
      expect(box!.height).toBeGreaterThanOrEqual(44);
    }
    await page.screenshot({
      path: `test-results/mobile-${width}.png`,
      fullPage: true,
    });
  });
}

test("available slots are keyboard-selectable and still require confirmation", async ({
  page,
}) => {
  await open(page);
  await message(
    page,
    "check beard trim availability on November 6 2026 afternoon",
  );
  const slot = page.getByRole("button", { name: "Book at 13:00", exact: true });
  await slot.focus();
  await slot.press("Enter");
  await expect(page.getByRole("log")).toContainText("What name should I use?");
  await message(page, "Casey Demo");
  await expect(
    page.getByRole("region", { name: "Appointment draft", exact: true }),
  ).toContainText("13:00");
  await expect(
    page.getByRole("button", { name: "Confirm appointment" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Saved appointment", exact: true }),
  ).toHaveCount(0);
});

test("speech replay and language selection use the current reply", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const spoken: { text: string; lang: string }[] = [];
    Object.assign(window, { __spokenReplies: spoken });
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        speaking: false,
        cancel() {},
        speak(utterance: SpeechSynthesisUtterance) {
          spoken.push({ text: utterance.text, lang: utterance.lang });
          setTimeout(
            () => utterance.onend?.(new Event("end") as SpeechSynthesisEvent),
            10,
          );
        },
      },
    });
  });
  await open(page);
  await message(page, "What are your hours?");
  await page
    .getByRole("combobox", { name: "Speech language" })
    .selectOption("en-PK");
  await page.getByRole("button", { name: "Listen again", exact: true }).click();
  const replies = await page.evaluate(
    () =>
      (
        window as unknown as {
          __spokenReplies: { text: string; lang: string }[];
        }
      ).__spokenReplies,
  );
  expect(replies).toHaveLength(1);
  expect(replies[0].text).toContain("10 AM");
  expect(replies[0].lang).toBe("en-PK");
});

test("synchronous speech failure releases the microphone and keeps typing available", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "speechSynthesis", {
      configurable: true,
      value: {
        speaking: false,
        cancel() {},
        speak() {
          throw new Error("Speech service failed");
        },
      },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
  await message(page, "What are your hours?");
  await expect(page.locator(".error-box")).toContainText("could not speak");
  await expect(
    page.getByRole("button", { name: "Listen again", exact: true }),
  ).toBeEnabled();
  await expect(
    page.getByRole("textbox", { name: "Your message" }),
  ).toBeEnabled();
});
