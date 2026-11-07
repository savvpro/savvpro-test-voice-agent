import { test, expect } from "@playwright/test";

test.describe("Dental Voice Agent — Text Interaction Suite", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Click Start Call and wait for initial greeting turn
    const startCallBtn = page.locator(".start-btn");
    await expect(startCallBtn).toBeVisible();
    await startCallBtn.click();

    // Verify connection and greeting turn 0
    const greetingMsg = page.locator(".message-bubble.assistant .message-text").first();
    await expect(greetingMsg).toContainText("Hello, thank you for calling BrightSmile Dental Clinic", {
      timeout: 15000,
    });
  });

  test.afterEach(async ({ page }) => {
    // End call if active
    const endBtn = page.locator(".end-btn");
    if (await endBtn.isVisible()) {
      await endBtn.click();
      await expect(page.locator(".start-btn")).toBeVisible({ timeout: 5000 });
    }
  });

  test("1. Text input: sends a message via Send button and receives FSM response", async ({ page }) => {
    const inputField = page.locator('.text-input-group input[type="text"]');
    const sendBtn = page.locator(".send-btn");

    // Type query
    await inputField.fill("What services do you offer?");
    await sendBtn.click();

    // Verify user bubble appeared
    const userMsg = page.locator(".message-bubble.user .message-text");
    await expect(userMsg.last()).toContainText("What services do you offer?");

    // Verify assistant answered with dental services
    const assistantMsgs = page.locator(".message-bubble.assistant .message-text");
    await expect(assistantMsgs).toHaveCount(2, { timeout: 15000 });
    await expect(assistantMsgs.last()).toContainText(/cleanings|checkups|fillings|whitening/i);

    // Verify input cleared
    await expect(inputField).toHaveValue("");
  });

  test("2. Text input: sends a message using 'Enter' key and extracts appointment intent", async ({ page }) => {
    const inputField = page.locator('.text-input-group input[type="text"]');

    // Type booking request and press Enter
    await inputField.fill("Book a cleaning tomorrow at 10 AM");
    await inputField.press("Enter");

    // Verify caller bubble appears
    const userMsg = page.locator(".message-bubble.user .message-text");
    await expect(userMsg.last()).toContainText("Book a cleaning tomorrow at 10 AM");

    // Verify assistant asks for patient name or time
    const assistantMsgs = page.locator(".message-bubble.assistant .message-text");
    await expect(assistantMsgs).toHaveCount(2, { timeout: 15000 });

    // Verify FSM Inspector displays extracted slots
    const debugPanel = page.locator(".debug-panel");
    await expect(debugPanel).toBeVisible();
    await expect(debugPanel.locator(".state-badge-highlight")).not.toHaveText("START");
  });

  test("3. Quick Prompts: clicking chip buttons automatically submits text turn", async ({ page }) => {
    // Check quick prompt buttons are visible
    const promptChip = page.locator(".chip-btn", { hasText: "What services do you offer?" });
    await expect(promptChip).toBeVisible();
    await promptChip.click();

    // Verify user message was submitted from the chip
    const userMsg = page.locator(".message-bubble.user .message-text");
    await expect(userMsg.last()).toContainText("What services do you offer?");

    // Assistant reply received
    const assistantMsgs = page.locator(".message-bubble.assistant .message-text");
    await expect(assistantMsgs).toHaveCount(2, { timeout: 15000 });
  });

  test("4. Multi-turn booking dialog flow via text", async ({ page }) => {
    const inputField = page.locator('.text-input-group input[type="text"]');
    const sendBtn = page.locator(".send-btn");

    // Turn 1: request booking
    await inputField.fill("I want to book an appointment");
    await sendBtn.click();
    await expect(page.locator(".message-bubble.assistant .message-text")).toHaveCount(2, { timeout: 15000 });

    // Turn 2: specify service
    await inputField.fill("Teeth cleaning");
    await sendBtn.click();
    await expect(page.locator(".message-bubble.assistant .message-text")).toHaveCount(3, { timeout: 15000 });

    // Assistant should advance to asking for date
    const latestReply = page.locator(".message-bubble.assistant .message-text").last();
    await expect(latestReply).toContainText(/What day would you like to come in/i);

    // Verify DebugPanel reflects FSM state transition to COLLECT_DATE
    const stateBadge = page.locator(".state-badge-highlight");
    await expect(stateBadge).toContainText("COLLECT_DATE");
  });
});

test.describe("Dental Voice Agent — Speech & Audio Interaction Suite", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("1. Push-to-Talk button: disabled when call is idle and enabled when call connects", async ({ page }) => {
    // When idle, push-to-talk button is not rendered yet, only Start Call
    const startCallBtn = page.locator(".start-btn");
    await expect(startCallBtn).toBeVisible();
    await expect(page.locator(".push-to-talk-btn")).toHaveCount(0);

    // Start Call
    await startCallBtn.click();

    // Button should appear and become enabled once connected
    const micBtn = page.locator(".push-to-talk-btn");
    await expect(micBtn).toBeVisible();
    await expect(micBtn).toBeEnabled();
    await expect(micBtn).toContainText("Hold to Speak");
    await expect(micBtn.locator(".btn-icon")).toContainText("🎙️");
  });

  test("2. Speech hold-to-speak: simulates pressing microphone button and releasing", async ({ page }) => {
    // Start Call
    await page.locator(".start-btn").click();

    // Wait for connection and greeting turn
    await expect(page.locator(".message-bubble.assistant")).toHaveCount(1, { timeout: 15000 });

    const micBtn = page.locator(".push-to-talk-btn");
    await expect(micBtn).toBeEnabled();

    // Trigger mousedown (start recording audio)
    await micBtn.dispatchEvent("mousedown");

    // Verify UI reflects listening / recording state
    await expect(micBtn).toHaveClass(/recording/);
    await expect(micBtn).toContainText("Listening... (Release to send)");
    await expect(micBtn.locator(".btn-icon")).toContainText("🔴");

    // Verify status pill reflects listening
    const statusPill = page.locator(".status-pill");
    await expect(statusPill).toContainText("Listening 🎙️");

    // Hold for 600ms of simulated speech audio
    await page.waitForTimeout(600);

    // Release mouse (stop recording and send audio)
    await micBtn.dispatchEvent("mouseup");

    // Verify returns to standard push-to-talk state
    await expect(micBtn).not.toHaveClass(/recording/);
    await expect(micBtn).toContainText("Hold to Speak");
  });

  test("3. Voice latency timing inspection: displays STT, NLU and TTS stage metrics", async ({ page }) => {
    await page.locator(".start-btn").click();

    // Wait for greeting
    await expect(page.locator(".message-bubble.assistant")).toHaveCount(1, { timeout: 15000 });

    // Send a turn to trigger full pipeline latency timing
    const inputField = page.locator('.text-input-group input[type="text"]');
    await inputField.fill("Book a cleaning tomorrow at 10 AM");
    await inputField.press("Enter");

    // Wait for assistant reply turn
    await expect(page.locator(".message-bubble.assistant")).toHaveCount(2, { timeout: 15000 });

    // Verify timing chip metrics are rendered in the transcript bubble
    const timingNote = page.locator(".timing-note").last();
    await expect(timingNote).toBeVisible();
    await expect(timingNote).toContainText(/Total:\s*\d+ms/i);
    await expect(timingNote).toContainText(/TTS:\s*\d+ms/i);

    // Verify latency breakdown in DebugPanel
    const debugTimings = page.locator(".timings-section");
    await expect(debugTimings).toBeVisible();
    await expect(debugTimings).toContainText("Latency Breakdown");
    await expect(debugTimings).toContainText("Brain (FSM NLU)");
    await expect(debugTimings).toContainText("TTS (Voice)");
  });

  test("4. Hang Up button cleanly terminates the session and resets UI", async ({ page }) => {
    await page.locator(".start-btn").click();
    await expect(page.locator(".message-bubble.assistant")).toHaveCount(1, { timeout: 15000 });

    // Hang up
    const endBtn = page.locator(".end-btn");
    await expect(endBtn).toBeVisible();
    await endBtn.click();

    // Call panel returns to initial Ready to Call with Start Call button
    const startCallBtn = page.locator(".start-btn");
    await expect(startCallBtn).toBeVisible();
    await expect(page.locator(".status-pill")).toContainText("Ready to Call");
  });
});
