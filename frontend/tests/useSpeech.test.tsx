import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useSpeech } from "../src/speech/useSpeech";

describe("speech integration", () => {
  it("does not start audio on mount and reports unsupported capabilities", () => {
    const { result } = renderHook(() =>
      useSpeech({
        onTranscript: () => {},
        reply: "hello",
        version: 0,
        busy: false,
      }),
    );
    expect(result.current.listening).toBe(false);
    expect(result.current.speaking).toBe(false);
    expect(result.current.supported).toBe(false);
    expect(result.current.muted).toBe(true);
  });
  it("lets callers stop or mute without requiring speech support", () => {
    const { result } = renderHook(() =>
      useSpeech({
        onTranscript: () => {},
        reply: "hello",
        version: 0,
        busy: false,
      }),
    );
    act(() => result.current.stop());
    act(() => result.current.toggleMute());
    expect(result.current.listening).toBe(false);
  });
});
