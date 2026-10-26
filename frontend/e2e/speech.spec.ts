import { test, expect } from "@playwright/test";

test("recognized audio transcript reaches Python and response reaches speech synthesis", async ({
  page,
}) => {
  await page.addInitScript(() => {
    const root = window as unknown as Record<string, unknown>;
    root.__spoken = [];
    class FakeRecognition {
      lang = "";
      interimResults = false;
      onresult?: (event: unknown) => void;
      onend?: () => void;
      start() {
        setTimeout(
          () =>
            this.onresult?.({
              results: [[{ transcript: "hi-tea tomorrow at 6 PM" }]],
            }),
          10,
        );
      }
      stop() {
        this.onend?.();
      }
      abort() {
        this.onend?.();
      }
    }
    root.SpeechRecognition = FakeRecognition;
    Object.defineProperty(window, "speechSynthesis", {
      value: {
        cancel() {},
        speak(utterance: { text: string }) {
          (root.__spoken as string[]).push(utterance.text);
        },
      },
    });
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start speaking", exact: true }),
  ).toBeEnabled();
  await page.getByRole("button", { name: "Replay assistant reply" }).click();
  await page
    .getByRole("button", { name: "Start speaking", exact: true })
    .click();
  await expect(page.locator(".details")).toContainText("hi-tea");
  await expect(page.locator(".inspector")).toContainText("collect_adults");
  await expect
    .poll(() =>
      page.evaluate(() =>
        (window as unknown as { __spoken: string[] }).__spoken.join(" "),
      ),
    )
    .toContain("How many adults");
});

test("microphone permission failure explains typed fallback", async ({
  page,
}) => {
  await page.addInitScript(() => {
    class DeniedRecognition {
      onerror?: (event: unknown) => void;
      start() {
        this.onerror?.({ error: "not-allowed" });
      }
      stop() {}
      abort() {}
    }
    (window as unknown as { SpeechRecognition: unknown }).SpeechRecognition =
      DeniedRecognition;
  });
  await page.goto("/");
  await expect(
    page.getByRole("button", { name: "Start speaking", exact: true }),
  ).toBeEnabled();
  await page
    .getByRole("button", { name: "Start speaking", exact: true })
    .click();
  await expect(page.getByRole("alert")).toContainText("permission was denied");
  await page.getByRole("button", { name: "Mute assistant" }).click();
  await page.getByLabel("Your message", { exact: true }).fill("a la carte");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await expect(page.locator(".details")).toContainText("a la carte");
});
