import { useCallback, useRef, useState } from "react";

export type RecorderStatus = "idle" | "starting" | "recording";

/** Turn a getUserMedia / MediaRecorder failure into something a caller can act on. */
export function micErrorMessage(error: unknown): string {
  const name = error instanceof DOMException || error instanceof Error ? error.name : "";
  switch (name) {
    case "NotAllowedError":
    case "SecurityError":
      return "Microphone permission was denied. Allow microphone access for this site in your browser settings (it only works on localhost or HTTPS), or type your message below.";
    case "NotFoundError":
      return "No microphone was found. Plug one in, or type your message below.";
    case "NotReadableError":
      return "The microphone is being used by another app. Close it, or type your message below.";
    default:
      return "Couldn't start the microphone. You can type your message below instead.";
  }
}

function pickMimeType(): string | undefined {
  if (typeof MediaRecorder === "undefined") return undefined;
  return ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus"].find((t) =>
    MediaRecorder.isTypeSupported(t),
  );
}

/** Push-to-talk recording: start() on press, stop() on release resolves with the clip. */
export function useRecorder() {
  const [status, setStatus] = useState<RecorderStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const stopRequested = useRef(false);

  const start = useCallback(async () => {
    if (status !== "idle") return;
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("This browser can't record audio here (use localhost or HTTPS). Type your message below.");
      return;
    }
    setStatus("starting");
    stopRequested.current = false;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = pickMimeType();
      const rec = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      chunks.current = [];
      rec.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
      recorder.current = rec;
      rec.start();
      setStatus("recording");
      if (stopRequested.current) rec.stop(); // released before the mic was ready
    } catch (e) {
      setStatus("idle");
      setError(micErrorMessage(e));
    }
  }, [status]);

  const stop = useCallback((): Promise<Blob | null> => {
    const rec = recorder.current;
    if (!rec || rec.state === "inactive") {
      stopRequested.current = true;
      return Promise.resolve(null);
    }
    return new Promise((resolve) => {
      rec.onstop = () => {
        rec.stream.getTracks().forEach((t) => t.stop());
        recorder.current = null;
        setStatus("idle");
        const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
        resolve(blob.size ? blob : null);
      };
      rec.stop();
    });
  }, []);

  return { status, error, start, stop, clearError: () => setError(null) };
}
