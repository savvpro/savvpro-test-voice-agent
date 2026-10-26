import { expect, test } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { mkdir } from "node:fs/promises";

for (const width of [390, 768, 1440]) {
  test(`accessibility and layout at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("/");
    await expect(
      page.getByLabel("Your message", { exact: true }),
    ).toBeEnabled();
    await page.evaluate(() => document.fonts.ready);
    const report = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
      .analyze();
    expect(
      report.violations.filter((violation) =>
        ["serious", "critical"].includes(violation.impact || ""),
      ),
    ).toEqual([]);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await mkdir("../.artifacts/browser", { recursive: true });
    await page.screenshot({
      path: `../.artifacts/browser/riverside-${width}.png`,
      fullPage: true,
    });
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "Skip to conversation" }),
    ).toBeFocused();
  });
}
