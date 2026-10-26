export interface UtterancePort {
  text: string;
  onend: (() => void) | null;
  onerror: (() => void) | null;
}
interface SynthesisPort {
  cancel(): void;
  speak(utterance: UtterancePort): void;
}

export class SynthesisAdapter {
  readonly supported: boolean;
  private generation = 0;
  private readonly port: SynthesisPort | null;
  private readonly utterance: ((text: string) => UtterancePort) | null;
  constructor(
    port: SynthesisPort | null,
    utterance: ((text: string) => UtterancePort) | null,
  ) {
    this.port = port;
    this.utterance = utterance;
    this.supported = Boolean(port && utterance);
  }
  speak(
    text: string,
    ended: () => void,
    failed: (message: string) => void,
  ): void {
    this.stop();
    if (!this.port || !this.utterance) {
      failed(
        "Spoken replies are unavailable. The reply remains visible in the transcript.",
      );
      return;
    }
    const generation = this.generation;
    try {
      const utterance = this.utterance(text);
      utterance.onend = () => {
        if (generation === this.generation) ended();
      };
      utterance.onerror = () => {
        if (generation === this.generation)
          failed(
            "The spoken reply stopped. You can still read it or replay it.",
          );
      };
      this.port.speak(utterance);
    } catch {
      failed(
        "The spoken reply could not start. You can still read the transcript.",
      );
    }
  }
  stop(): void {
    this.generation++;
    this.port?.cancel();
  }
}

export function browserSynthesis(): SynthesisAdapter {
  if (!("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window))
    return new SynthesisAdapter(null, null);
  return new SynthesisAdapter(
    {
      cancel: () => window.speechSynthesis.cancel(),
      speak: (utterance) =>
        window.speechSynthesis.speak(utterance as SpeechSynthesisUtterance),
    },
    (text) => {
      const value = new SpeechSynthesisUtterance(text);
      value.lang = "en-GB";
      value.rate = 0.97;
      return value as unknown as UtterancePort;
    },
  );
}
