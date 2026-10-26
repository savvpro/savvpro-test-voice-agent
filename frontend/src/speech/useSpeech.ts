import { useCallback, useEffect, useRef, useState } from "react";
import { transcribeAudio } from "../api/speech";
import { browserRecording, canRecord, RecordingAdapter } from "./recording";
import type { RecordingState } from "./recording";
import { browserSynthesis, SynthesisAdapter } from "./synthesis";

interface Options {
  onTranscript(text: string): void;
  reply: string;
  version: number;
  busy: boolean;
  transcribe?: typeof transcribeAudio;
}
export function useSpeech({
  onTranscript,
  reply,
  version,
  busy,
  transcribe = transcribeAudio,
}: Options) {
  const [captureState, setCaptureState] = useState<RecordingState>("idle");
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [muted, setMuted] = useState(true);
  const onFinal = useRef(onTranscript);
  const transcriber = useRef(transcribe);
  const lastVersion = useRef(version);
  const cycle = useRef(0);
  const recording = useRef<RecordingAdapter | null>(null);
  const synthesis = useRef<SynthesisAdapter | null>(null);
  const upload = useRef<AbortController | null>(null);
  const supported = canRecord();
  const synthesisSupported =
    "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
  useEffect(() => {
    onFinal.current = onTranscript;
    transcriber.current = transcribe;
  }, [onTranscript, transcribe]);
  const invalidate = useCallback(() => { cycle.current++; }, []);
  useEffect(() => {
    let active = true;
    const recorder = new RecordingAdapter(browserRecording(), {
      audio: (audio) => {
        if (!active) return;
        const epoch = cycle.current;
        const controller = new AbortController();
        upload.current = controller;
        setTranscribing(true);
        void transcriber
          .current(audio, controller.signal)
          .then((text) => {
            if (active && epoch === cycle.current) onFinal.current(text);
          })
          .catch((failure) => {
            if (active && epoch === cycle.current)
              setError(
                failure instanceof Error
                  ? failure.message
                  : "Transcription failed. Please try again or type.",
              );
          })
          .finally(() => {
            if (active && epoch === cycle.current) {
              setTranscribing(false);
              upload.current = null;
            }
          });
      },
      error: (message) => {
        if (active) setError(message);
      },
      state: (state) => {
        if (active) setCaptureState(state);
      },
    });
    const speaker = browserSynthesis();
    recording.current = recorder;
    synthesis.current = speaker;
    return () => {
      active = false;
      invalidate();
      upload.current?.abort();
      recorder.cancel();
      speaker.stop();
      recording.current = null;
      synthesis.current = null;
    };
  }, [invalidate]);
  const stop = useCallback(() => {
    cycle.current++;
    upload.current?.abort();
    upload.current = null;
    recording.current?.cancel();
    synthesis.current?.stop();
    setSpeaking(false);
    setTranscribing(false);
  }, []);
  const speak = useCallback((text: string) => {
    recording.current?.cancel();
    setSpeaking(true);
    setError(null);
    synthesis.current?.speak(
      text,
      () => setSpeaking(false),
      (message) => {
        setSpeaking(false);
        setError(message);
      },
    );
  }, []);
  const start = useCallback(() => {
    stop();
    setError(null);
    setMuted(false);
    void recording.current?.start();
  }, [stop]);
  const finish = useCallback(() => recording.current?.finish(), []);
  const toggleMute = useCallback(() => {
    synthesis.current?.stop();
    setSpeaking(false);
    setMuted((value) => !value);
  }, []);
  useEffect(() => {
    if (version === lastVersion.current || busy) return;
    const previous = lastVersion.current;
    lastVersion.current = version;
    if (version > previous && !muted && reply) speak(reply);
  }, [version, reply, busy, muted, speak]);
  return {
    listening: captureState === "recording",
    requesting: captureState === "requesting",
    transcribing,
    speaking,
    error,
    muted,
    supported,
    synthesisSupported,
    start,
    finish,
    stop,
    toggleMute,
    replay: () => speak(reply),
  };
}
