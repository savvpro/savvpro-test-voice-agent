import { afterEach, describe, expect, it, vi } from "vitest";
import { transcribeAudio } from "../src/api/speech";

afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe("server-side speech boundary", () => {
  it("uses the browser fetch implementation and defaults unknown recording types to WebM", async () => {
    let contentType: unknown;
    vi.stubGlobal("fetch", async (_url: unknown, init: RequestInit) => {
      contentType = init.headers;
      return Response.json({ text: "a black bag" });
    });
    expect(await transcribeAudio(new Blob(["audio"]))).toBe("a black bag");
    expect(contentType).toEqual({ "Content-Type": "audio/webm" });
  });
  it("uses a safe message for malformed provider errors and transport failures", async () => {
    await expect(transcribeAudio(new Blob(["audio"]), undefined, async () => new Response("PRIVATE ERROR", { status: 503 }))).rejects.toThrow(/Voice input/);
    await expect(transcribeAudio(new Blob(["audio"]), undefined, async () => Response.json({}, { status: 503 }))).rejects.toThrow(/Voice input/);
    await expect(transcribeAudio(new Blob(["audio"]), undefined, async () => { throw new TypeError("offline"); })).rejects.toMatchObject({ code: "NETWORK_ERROR" });
  });

  it("aborts cancelled uploads without returning a transcript", async () => {
    const controller = new AbortController();
    const fetcher: typeof fetch = (_url, init) => new Promise((_resolve, reject) => {
      if (init?.signal?.aborted) reject(new DOMException("cancelled", "AbortError"));
      else init?.signal?.addEventListener("abort", () => reject(new DOMException("cancelled", "AbortError")));
    });
    const pending = transcribeAudio(new Blob(["audio"]), controller.signal, fetcher);
    controller.abort();
    await expect(pending).rejects.toMatchObject({ code: "CANCELLED" });
    await expect(transcribeAudio(new Blob(["audio"]), controller.signal, fetcher)).rejects.toMatchObject({ code: "CANCELLED" });
  });

  it("times out a speech provider that never responds", async () => {
    vi.useFakeTimers();
    const fetcher: typeof fetch = (_url, init) => new Promise((_resolve, reject) => {
      init?.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
    });
    const pending = expect(transcribeAudio(new Blob(["audio"]), undefined, fetcher)).rejects.toMatchObject({ code: "SPEECH_TIMEOUT" });
    await vi.advanceTimersByTimeAsync(55000);
    await pending;
  });
  it("sends audio to our API without any browser-side Groq key", async () => {
    const requests: RequestInit[] = [];
    const text = await transcribeAudio(
      new Blob(["audio"], { type: "audio/webm" }),
      undefined,
      async (url, init) => {
        expect(url).toBe("/api/v1/transcriptions");
        requests.push(init!);
        return Response.json({ text: "A black bag." });
      },
    );
    expect(text).toBe("A black bag.");
    expect(requests[0].body).toBeInstanceOf(Blob);
    expect(requests[0].headers).toEqual({ "Content-Type": "audio/webm" });
    expect(requests[0].credentials).toBe("same-origin");
  });
  it("surfaces provider recovery messages without submitting a turn", async () => {
    await expect(
      transcribeAudio(new Blob(["audio"]), undefined, async () =>
        Response.json(
          { error: { code: "NO_SPEECH", message: "Please speak again." } },
          { status: 422 },
        ),
      ),
    ).rejects.toThrow("Please speak again.");
  });
  it("rejects malformed transcripts", async () => {
    await expect(
      transcribeAudio(new Blob(["audio"]), undefined, async () =>
        Response.json({ text: "" }),
      ),
    ).rejects.toThrow(/speech/i);
  });
});
