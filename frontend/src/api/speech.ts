import { ApiError } from "./client";

export async function transcribeAudio(
  audio: Blob,
  signal?: AbortSignal,
  fetcher: typeof fetch = (...args) => fetch(...args),
): Promise<string> {
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener("abort", abort, { once: true });
  if (signal?.aborted) controller.abort();
  const timer = setTimeout(abort, 55000);
  try {
    const response = await fetcher("/api/v1/transcriptions", {
      method: "POST",
      credentials: "same-origin",
      body: audio,
      headers: { "Content-Type": audio.type || "audio/webm" },
      signal: controller.signal,
    });
    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new ApiError(
        response.status,
        "SPEECH_UNAVAILABLE",
        "Voice input is unavailable. Please try again or type.",
      );
    }
    if (!response.ok) {
      if (
        data &&
        typeof data === "object" &&
        "error" in data &&
        data.error &&
        typeof data.error === "object" &&
        "message" in data.error &&
        typeof data.error.message === "string"
      ) {
        throw new ApiError(response.status, "SPEECH_ERROR", data.error.message);
      }
      throw new ApiError(
        response.status,
        "SPEECH_UNAVAILABLE",
        "Voice input is unavailable. Please try again or type.",
      );
    }
    if (
      !data ||
      typeof data !== "object" ||
      !("text" in data) ||
      typeof data.text !== "string" ||
      !data.text.trim()
    ) {
      throw new ApiError(
        422,
        "NO_SPEECH",
        "No clear speech was detected. Please try again or type.",
      );
    }
    return data.text.trim();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (signal?.aborted)
      throw new ApiError(0, "CANCELLED", "Recording cancelled.");
    if (controller.signal.aborted)
      throw new ApiError(
        0,
        "SPEECH_TIMEOUT",
        "Transcription took too long. Please record again or type.",
      );
    throw new ApiError(
      0,
      "NETWORK_ERROR",
      "The recording could not be sent. Check your connection or type your message.",
    );
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort", abort);
  }
}
