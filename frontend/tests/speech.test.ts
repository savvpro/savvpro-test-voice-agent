import { describe, expect, it } from "vitest";
import { SynthesisAdapter } from "../src/speech/synthesis";

describe("spoken replies", () => {
  it("cancels the old utterance before speaking a new one", () => {
    const events: string[] = [];
    const adapter = new SynthesisAdapter(
      {
        cancel: () => events.push("cancel"),
        speak: (utterance) => events.push(utterance.text),
      },
      (text) => ({ text, onend: null, onerror: null }),
    );
    adapter.speak(
      "A reply",
      () => {},
      () => {},
    );
    adapter.stop();
    expect(events).toEqual(["cancel", "A reply", "cancel"]);
  });
  it("reports missing synthesis without pretending speech succeeded", () => {
    const errors: string[] = [];
    const adapter = new SynthesisAdapter(null, null);
    adapter.speak(
      "Reply",
      () => {},
      (message) => errors.push(message),
    );
    expect(adapter.supported).toBe(false);
    expect(errors[0]).toMatch(/visible/i);
  });
});
