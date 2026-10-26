import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiClient } from "../src/api/client";
import { App } from "../src/app/App";
import { useConversation } from "../src/features/conversation/useConversation";
import { useSpeech } from "../src/speech/useSpeech";
import type { RecorderPort } from "../src/speech/recording";
import { view } from "./factories";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

class Microphone implements RecorderPort {
  static latest: Microphone;
  static isTypeSupported() {
    return true;
  }
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: RecorderPort["ondataavailable"] = null;
  onstop: RecorderPort["onstop"] = null;
  onerror: RecorderPort["onerror"] = null;
  constructor() {
    Microphone.latest = this;
  }
  start() {
    this.state = "recording";
  }
  stop() {
    this.state = "inactive";
    this.ondataavailable?.({
      data: new Blob(["recorded audio"], { type: this.mimeType }),
    });
    this.onstop?.();
  }
}
class Utterance {
  text: string;
  lang = "";
  rate = 1;
  onend: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(text: string) {
    this.text = text;
  }
}
function speechBrowser(permissionDenied = false) {
  const spoken: Utterance[] = [];
  vi.stubGlobal("MediaRecorder", Microphone);
  vi.stubGlobal("navigator", {
    userAgent: "test",
    mediaDevices: {
      getUserMedia: async () => {
        if (permissionDenied)
          throw new DOMException("denied", "NotAllowedError");
        return { getTracks: () => [{ stop() {} }] };
      },
    },
  });
  vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
  vi.stubGlobal("speechSynthesis", {
    cancel() {},
    speak(utterance: Utterance) {
      spoken.push(utterance);
    },
  });
  return spoken;
}

describe("conversation recovery", () => {
  it("resynchronizes after a stale version without retrying an outdated mutation", async () => {
    const received: number[] = [];
    const fetcher: typeof fetch = async (url, init) => {
      if (String(url).endsWith("/turns")) {
        received.push(
          (JSON.parse(String(init?.body)) as { expected_version: number })
            .expected_version,
        );
        if (received.length === 1)
          return Response.json(
            { error: { code: "VERSION_CONFLICT", message: "Refresh first." } },
            { status: 409 },
          );
      }
      return Response.json(view({ version: init?.method === "GET" ? 5 : 0 }));
    };
    const newClient = new ApiClient(fetcher);
    const { result } = renderHook(() => useConversation(newClient));
    await waitFor(() => expect(result.current.session).not.toBeNull());
    await act(() => result.current.send("black bag"));
    expect(result.current.session?.version).toBe(5);
    expect(result.current.hasRetry).toBe(false);
    await act(() => result.current.send("red bag"));
    expect(received).toEqual([0, 5]);
  });

  it("expires the local snapshot when the server rejects the session", async () => {
    const fetcher: typeof fetch = async (url) =>
      String(url).endsWith("/turns")
        ? Response.json(
            { error: { code: "SESSION_EXPIRED", message: "Start again." } },
            { status: 401 },
          )
        : Response.json(view());
    const client = new ApiClient(fetcher);
    const { result } = renderHook(() => useConversation(client));
    await waitFor(() => expect(result.current.busy).toBe(false));
    await act(() => result.current.send("a bag"));
    expect(result.current.session).toBeNull();
    expect(result.current.error?.code).toBe("SESSION_EXPIRED");
    expect(result.current.hasRetry).toBe(false);
  });

  it("reconnects after initial service failure", async () => {
    let attempts = 0;
    const client = new ApiClient(async () => {
      if (++attempts === 1) throw new TypeError("offline");
      return Response.json(view());
    });
    const { result } = renderHook(() => useConversation(client));
    await waitFor(() => expect(result.current.error).not.toBeNull());
    await act(() => result.current.retry());
    expect(result.current.session?.state).toBe("collecting");
    expect(result.current.error).toBeNull();
  });

  it("erases the old chat before opening a new one", async () => {
    const operations: string[] = [];
    const client = new ApiClient(async (_url, init) => {
      operations.push(init?.method || "GET");
      return init?.method === "DELETE"
        ? new Response(null, { status: 204 })
        : Response.json(view());
    });
    const { result } = renderHook(() => useConversation(client));
    await waitFor(() => expect(result.current.busy).toBe(false));
    await act(() => result.current.erase());
    expect(operations).toEqual(["POST", "DELETE", "POST"]);
    expect(result.current.session?.version).toBe(0);
  });

  it("preserves the chat if erasing fails", async () => {
    const client = new ApiClient(async (_url, init) =>
      init?.method === "DELETE"
        ? new Response(null, { status: 503 })
        : Response.json(view()),
    );
    const { result } = renderHook(() => useConversation(client));
    await waitFor(() => expect(result.current.busy).toBe(false));
    await act(() => result.current.erase());
    expect(result.current.session).not.toBeNull();
    expect(result.current.error?.status).toBe(503);
  });

  it("does not send blank messages or overlapping requests", async () => {
    let release: ((response: Response) => void) | undefined;
    const received: string[] = [];
    const client = new ApiClient(async (url, init) => {
      if (!String(url).endsWith("/turns")) return Response.json(view());
      received.push(String(init?.body));
      return new Promise((resolve) => {
        release = resolve;
      });
    });
    const { result } = renderHook(() => useConversation(client));
    await waitFor(() => expect(result.current.busy).toBe(false));
    await act(() => result.current.send("   "));
    let pending: Promise<boolean>;
    act(() => {
      pending = result.current.send("a bag");
    });
    await act(() => result.current.send("another bag"));
    expect(received).toHaveLength(1);
    await act(async () => {
      release?.(Response.json(view({ version: 1 })));
      await pending!;
    });
  });
});

describe("actual speech adapters connected to React", () => {
  it("submits only the finished recording transcript and reads the resulting reply", async () => {
    const spoken = speechBrowser(),
      transcripts: string[] = [];
    const { result, rerender } = renderHook(
      ({ version, reply }) =>
        useSpeech({
          onTranscript: (text) => transcripts.push(text),
          version,
          reply,
          busy: false,
          transcribe: async () => "black bag",
        }),
      { initialProps: { version: 0, reply: "Welcome" } },
    );
    await act(async () => result.current.start());
    expect(result.current.listening).toBe(true);
    expect(transcripts).toEqual([]);
    await act(async () => result.current.finish());
    expect(transcripts).toEqual(["black bag"]);
    expect(result.current.listening).toBe(false);
    rerender({ version: 1, reply: "Where did you last have it?" });
    await waitFor(() => expect(spoken).toHaveLength(1));
    expect(spoken[0].text).toBe("Where did you last have it?");
    act(() => spoken[0].onend?.());
    expect(result.current.speaking).toBe(false);
    act(() => result.current.replay());
    expect(spoken).toHaveLength(2);
    act(() => spoken[1].onerror?.());
    expect(result.current.error).toMatch(/read|replay/i);
  });

  it("does not submit a captured callback after the chat unmounts", async () => {
    speechBrowser();
    const transcripts: string[] = [];
    const { result, unmount } = renderHook(() =>
      useSpeech({
        onTranscript: (text) => transcripts.push(text),
        version: 0,
        reply: "",
        busy: false,
      }),
    );
    await act(async () => result.current.start());
    const stale = Microphone.latest.onstop!;
    unmount();
    stale();
    expect(transcripts).toEqual([]);
  });

  it("surfaces permission failure while preserving typed input", async () => {
    speechBrowser(true);
    const client = new ApiClient(async () => Response.json(view()));
    render(<App client={client} />);
    await screen.findByText("Tell me what you lost.");
    fireEvent.click(
      screen.getByRole("button", { name: "Talk to the assistant" }),
    );
    expect(
      screen.getByText(/Your recording is sent to Groq/),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep typing" }));
    expect(
      screen.queryByText(/Your recording is sent to Groq/),
    ).not.toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: "Talk to the assistant" }),
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Agree and start microphone" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("permission");
    expect(screen.getByLabelText("Your message")).toBeEnabled();
  });

  it("shows caller details, safe candidate points, and report receipt states", async () => {
    const snapshot = view({
      fields: {
        category: "bag",
        colour: "blue",
        brand: "nike",
        location: "food court",
        lost_date: "2026-10-25",
        description: "backpack",
        uncertain: ["colour"],
        unknown: [],
      },
      candidates: [
        {
          label: "Option 1",
          category: "bag",
          colour: "blue",
          description: "small backpack",
          score: 65,
          signals: { category: 30, colour: 15, location: 10, brand: 10 },
        },
      ],
    });
    const client = new ApiClient(async () => Response.json(snapshot));
    render(<App client={client} />);
    expect(await screen.findByText("small backpack")).toBeInTheDocument();
    expect(screen.getByText("· uncertain")).toBeInTheDocument();
    fireEvent.click(screen.getByText("How the assistant decided"));
    expect(screen.getByText("65 / 100 points")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /Consider this/ }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: /Consider this/ }),
      ).toBeEnabled(),
    );
  });
});
