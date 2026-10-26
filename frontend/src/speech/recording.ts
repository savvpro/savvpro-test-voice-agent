export interface StreamPort {
  getTracks(): { stop(): void }[];
}
export interface RecorderPort {
  state: string;
  mimeType: string;
  ondataavailable: ((event: { data: Blob }) => void) | null;
  onstop: (() => void) | null;
  onerror: (() => void) | null;
  start(): void;
  stop(): void;
}
export interface RecorderPlatform {
  stream(): Promise<StreamPort>;
  recorder(stream: StreamPort): RecorderPort;
}
export type RecordingState = "idle" | "requesting" | "recording";
interface Callbacks {
  audio(blob: Blob): void;
  error(message: string): void;
  state(value: RecordingState): void;
}

export function canRecord(): boolean {
  return (
    typeof MediaRecorder !== "undefined" &&
    Boolean(navigator.mediaDevices?.getUserMedia)
  );
}
export function browserRecording(): RecorderPlatform | null {
  if (!canRecord()) return null;
  return {
    stream: () =>
      navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          channelCount: 1,
        },
        video: false,
      }),
    recorder: (stream) => {
      const mimeType = [
        "audio/webm;codecs=opus",
        "audio/webm",
        "audio/mp4",
        "audio/ogg;codecs=opus",
      ].find((type) => MediaRecorder.isTypeSupported(type));
      return new MediaRecorder(stream as MediaStream, {
        ...(mimeType ? { mimeType } : {}),
        audioBitsPerSecond: 64000,
      }) as unknown as RecorderPort;
    },
  };
}

export class RecordingAdapter {
  readonly supported: boolean;
  private generation = 0;
  private stream: StreamPort | null = null;
  private recorder: RecorderPort | null = null;
  private chunks: Blob[] = [];
  private timer: ReturnType<typeof setTimeout> | undefined;
  private readonly platform: RecorderPlatform | null;
  private readonly callbacks: Callbacks;
  constructor(platform: RecorderPlatform | null, callbacks: Callbacks) {
    this.platform = platform;
    this.callbacks = callbacks;
    this.supported = platform !== null;
  }
  async start(): Promise<void> {
    this.cancel();
    if (!this.platform) {
      this.callbacks.error(
        "Microphone recording is unavailable here. Please type your message.",
      );
      return;
    }
    const epoch = this.generation;
    this.callbacks.state("requesting");
    try {
      const stream = await this.platform.stream();
      if (epoch !== this.generation) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      this.stream = stream;
      const recorder = this.platform.recorder(stream);
      this.recorder = recorder;
      recorder.ondataavailable = (event) => {
        if (epoch === this.generation && event.data.size) {
          this.chunks.push(event.data);
          if (
            this.chunks.reduce((bytes, chunk) => bytes + chunk.size, 0) >
            8 * 1024 * 1024
          ) {
            this.cancel();
            this.callbacks.error(
              "The recording is too large. Please use a shorter message.",
            );
          }
        }
      };
      recorder.onstop = () => {
        if (epoch !== this.generation) return;
        const audio = new Blob(this.chunks, {
          type: recorder.mimeType || "audio/webm",
        });
        this.cancel();
        if (!audio.size) {
          this.callbacks.error(
            "No audio was recorded. Please try again or type.",
          );
          return;
        }
        this.callbacks.audio(audio);
      };
      recorder.onerror = () => {
        if (epoch !== this.generation) return;
        this.cancel();
        this.callbacks.error(
          "The microphone stopped unexpectedly. Please try again or type.",
        );
      };
      recorder.start();
      this.callbacks.state("recording");
      this.timer = setTimeout(() => this.finish(), 60000);
    } catch (error) {
      if (epoch !== this.generation) return;
      this.cancel();
      this.callbacks.error(
        error instanceof DOMException && error.name === "NotAllowedError"
          ? "Microphone permission was denied. Allow it in browser settings, or type your message."
          : "The microphone could not start. Check your device, or type your message.",
      );
    }
  }
  finish(): void {
    if (this.recorder?.state === "recording") this.recorder.stop();
    else this.cancel();
  }
  cancel(): void {
    this.generation++;
    clearTimeout(this.timer);
    this.timer = undefined;
    if (this.recorder) {
      const recorder = this.recorder;
      this.recorder = null;
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== "inactive") recorder.stop();
    }
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.chunks = [];
    this.callbacks.state("idle");
  }
}
