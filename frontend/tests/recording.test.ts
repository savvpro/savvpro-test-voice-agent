import { afterEach, describe, expect, it, vi } from "vitest";
import { RecordingAdapter } from "../src/speech/recording";
import type { RecorderPort, StreamPort } from "../src/speech/recording";

afterEach(() => vi.useRealTimers());

class Recorder implements RecorderPort {
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: RecorderPort["ondataavailable"] = null;
  onstop: RecorderPort["onstop"] = null;
  onerror: RecorderPort["onerror"] = null;
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.onstop?.();
  }
}
function fixture() {
  let released = false;
  const stream: StreamPort = {
    getTracks: () => [
      {
        stop: () => {
          released = true;
        },
      },
    ],
  };
  const recorder = new Recorder();
  const audio: Blob[] = [],
    errors: string[] = [],
    states: string[] = [];
  const adapter = new RecordingAdapter(
    { stream: async () => stream, recorder: () => recorder },
    {
      audio: (value) => audio.push(value),
      error: (value) => errors.push(value),
      state: (value) => states.push(value),
    },
  );
  return { adapter, recorder, audio, errors, states, released: () => released };
}
describe("microphone recording", () => {
  it("releases the device and rejects an oversized recording", async () => {
    const item = fixture();
    await item.adapter.start();
    item.recorder.ondataavailable?.({ data: new Blob([new Uint8Array(8 * 1024 * 1024 + 1)]) });
    expect(item.errors[0]).toMatch(/too large/);
    expect(item.audio).toEqual([]);
    expect(item.released()).toBe(true);
  });

  it("stops automatically at the sixty-second boundary", async () => {
    vi.useFakeTimers();
    const item = fixture();
    await item.adapter.start();
    item.recorder.ondataavailable?.({ data: new Blob(["audio"]) });
    await vi.advanceTimersByTimeAsync(60000);
    expect(item.audio).toHaveLength(1);
    expect(item.released()).toBe(true);
  });

  it("recovers from device failure without uploading partial audio", async () => {
    const item = fixture();
    await item.adapter.start();
    item.recorder.onerror?.();
    expect(item.errors[0]).toMatch(/stopped unexpectedly/);
    expect(item.audio).toEqual([]);
    expect(item.released()).toBe(true);
  });
  it("uploads a complete recording once and releases every microphone track", async () => {
    const item = fixture();
    await item.adapter.start();
    item.recorder.ondataavailable?.({
      data: new Blob(["recorded audio"], { type: "audio/webm" }),
    });
    item.adapter.finish();
    item.adapter.finish();
    expect(item.audio).toHaveLength(1);
    expect(item.audio[0].type).toBe("audio/webm");
    expect(item.released()).toBe(true);
    expect(item.states.at(-1)).toBe("idle");
  });
  it("never uploads a discarded recording or a late callback", async () => {
    const item = fixture();
    await item.adapter.start();
    const late = item.recorder.onstop!;
    item.recorder.ondataavailable?.({
      data: new Blob(["private discarded audio"]),
    });
    item.adapter.cancel();
    late();
    expect(item.audio).toEqual([]);
    expect(item.released()).toBe(true);
  });
  it("rejects empty recordings without calling the speech provider", async () => {
    const item = fixture();
    await item.adapter.start();
    item.adapter.finish();
    expect(item.audio).toEqual([]);
    expect(item.errors[0]).toMatch(/audio/i);
  });
  it("explains denied microphone permission and remains usable", async () => {
    const errors: string[] = [];
    const adapter = new RecordingAdapter(
      {
        stream: async () => {
          throw new DOMException("denied", "NotAllowedError");
        },
        recorder: () => new Recorder(),
      },
      {
        audio: () => {},
        error: (value) => errors.push(value),
        state: () => {},
      },
    );
    await adapter.start();
    expect(errors[0]).toMatch(/permission/i);
  });
  it("releases permission-granted streams if the caller cancelled while waiting", async () => {
    let resolve: ((stream: StreamPort) => void) | undefined;
    let stopped = false;
    const adapter = new RecordingAdapter(
      {
        stream: () =>
          new Promise((ready) => {
            resolve = ready;
          }),
        recorder: () => new Recorder(),
      },
      { audio: () => {}, error: () => {}, state: () => {} },
    );
    const start = adapter.start();
    adapter.cancel();
    resolve?.({
      getTracks: () => [
        {
          stop: () => {
            stopped = true;
          },
        },
      ],
    });
    await start;
    expect(stopped).toBe(true);
  });
  it("offers typing when recording is unsupported", async () => {
    const errors: string[] = [];
    const adapter = new RecordingAdapter(null, {
      audio: () => {},
      error: (value) => errors.push(value),
      state: () => {},
    });
    await adapter.start();
    expect(adapter.supported).toBe(false);
    expect(errors[0]).toMatch(/type/i);
  });
});
