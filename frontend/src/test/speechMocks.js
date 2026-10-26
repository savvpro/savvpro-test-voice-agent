import { vi } from 'vitest';

export function installRecognition({ prefixed = false, startError = null } = {}) {
  const instances = [];
  class Recognition {
    constructor() {
      this.start = vi.fn(() => { if (startError) throw startError; });
      this.stop = vi.fn();
      this.abort = vi.fn();
      instances.push(this);
    }
  }
  vi.stubGlobal('SpeechRecognition', prefixed ? undefined : Recognition);
  vi.stubGlobal('webkitSpeechRecognition', prefixed ? Recognition : undefined);
  return instances;
}

export function recognitionResult(text, isFinal = true) {
  const result = [{ transcript: text, confidence: 0.9 }];
  result.isFinal = isFinal;
  return result;
}

export function installSynthesis() {
  const utterances = [];
  class Utterance { constructor(text) { this.text = text; } }
  const synthesis = {
    speak: vi.fn((utterance) => utterances.push(utterance)),
    cancel: vi.fn(),
  };
  vi.stubGlobal('SpeechSynthesisUtterance', Utterance);
  vi.stubGlobal('speechSynthesis', synthesis);
  return { synthesis, utterances };
}
